"""
app/billing/credits.py
------------------------
Cost-denominated metering. Every paid vendor call debits the user's
credit balance by what it actually cost.

=====================================================================
WHY CREDITS AND NOT REQUEST COUNTS
=====================================================================
Migration 008 metered requests, which is correct only while every
request costs the same. It stopped being true the moment a paid LLM
entered the path: on this codebase's own prompt sizes, one thesis
synthesis costs ~$0.0016 on Haiku and ~$0.098 on Opus — a 60x spread
that a single "analyses per day" counter cannot express. Counting
requests either starves the cheap case or bankrupts the expensive one.

So the binding limit is now money. Request counts remain as a coarse
abuse guard, not as the economic control.

    1 credit = $0.001 of BILLED value (vendor cost x markup)

Billed rather than raw cost, because the markup carries both the gross
margin and the fixed vendor subscriptions that per-token pricing cannot
express — Polygon costs $199/month whether it serves one call or a
million, and nothing in a per-call rate captures that.

=====================================================================
RESERVE-THEN-SETTLE
=====================================================================
Token cost is not knowable before the call: the output length is
whatever the model produces. Charging afterwards alone would let a user
at 10 credits trigger a 300-credit Opus run and go deeply negative.

So spending is two-phase, like an authorisation hold on a card:

    reserve(estimate)  -> checks balance, debits an estimate
    settle(actual)     -> adjusts the difference once usage is known

If the process dies between the two, the reservation stands. That is
the correct failure direction: the vendor call was made and the money
was really spent, so the user should be charged. Losing the settlement
means the estimate is kept, which is off by a small amount rather than
free.

=====================================================================
CONCURRENCY
=====================================================================
Balance checks use SELECT ... FOR UPDATE. Two simultaneous requests
from the same user must not both read "12 credits left" and both spend
it. The row lock serialises them; the second sees the first's debit.
This is the same lost-update problem the usage counters solved with an
atomic UPSERT, but a check-then-act cannot be expressed that way.
"""

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.billing.credits")

# 1 credit = $0.001 of billed value.
USD_PER_CREDIT = Decimal("0.001")


@lru_cache(maxsize=1)
def _engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


class InsufficientCredits(Exception):
    """Raised when a spend would exceed the user's remaining balance."""

    def __init__(self, required: Decimal, available: Decimal, operation: str):
        self.required = required
        self.available = available
        self.operation = operation
        super().__init__(
            f"{operation} needs {required:.1f} credits; {available:.1f} remaining."
        )


@dataclass
class Balance:
    allowance: Decimal
    consumed: Decimal
    purchased: Decimal

    @property
    def remaining(self) -> Decimal:
        """Allowance not yet consumed, plus anything bought on top."""
        return max(Decimal(0), self.allowance - self.consumed) + self.purchased

    def to_dict(self) -> dict:
        return {
            "allowance": float(self.allowance),
            "consumed": float(self.consumed),
            "purchased": float(self.purchased),
            "remaining": float(self.remaining),
            "usd_value_remaining": round(float(self.remaining * USD_PER_CREDIT), 2),
        }


# ── Rates ─────────────────────────────────────────────────────────────

def get_rate(vendor: str, operation: str, unit: str) -> tuple[Decimal, Decimal] | None:
    """(usd_per_unit, markup) for a vendor unit, or None if unpriced."""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT usd_per_unit, markup_multiplier
                      FROM vendor_cost_rates
                     WHERE vendor = :v AND operation = :o AND unit = :u AND is_active
                     LIMIT 1
                """),
                {"v": vendor, "o": operation, "u": unit},
            ).fetchone()
        return (Decimal(str(row[0])), Decimal(str(row[1]))) if row else None
    except Exception as exc:
        logger.warning("Rate lookup failed", extra={"vendor": vendor, "error": str(exc)})
        return None


def price_units(vendor: str, operation: str, unit: str, quantity: float) -> Decimal:
    """
    Credits for `quantity` units of a vendor operation.

    An unpriced combination returns 0 rather than raising. A missing rate
    row is an operator oversight, and the right response is to serve the
    request and log it — refusing real traffic because a lookup table is
    incomplete would turn a bookkeeping gap into an outage.
    """
    rate = get_rate(vendor, operation, unit)
    if rate is None:
        logger.warning("No rate configured, not charging",
                       extra={"vendor": vendor, "operation": operation, "unit": unit})
        return Decimal(0)
    usd_per_unit, markup = rate
    billed_usd = Decimal(str(quantity)) * usd_per_unit * markup
    return (billed_usd / USD_PER_CREDIT).quantize(Decimal("0.001"))


def price_llm_call(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Credits for one LLM call, priced separately for input and output."""
    return (
        price_units("anthropic", model, "input_token", input_tokens)
        + price_units("anthropic", model, "output_token", output_tokens)
    )


# ── Balances ──────────────────────────────────────────────────────────

def get_balance(user_id: str) -> Balance:
    """Current balance. A user with no account row has no credits."""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text("""SELECT allowance_credits, consumed_credits, purchased_credits
                          FROM credit_accounts WHERE user_id = :u"""),
                {"u": user_id},
            ).fetchone()
    except Exception as exc:
        logger.warning("Balance read failed", extra={"user_id": user_id, "error": str(exc)})
        return Balance(Decimal(0), Decimal(0), Decimal(0))
    if row is None:
        return Balance(Decimal(0), Decimal(0), Decimal(0))
    return Balance(Decimal(str(row[0])), Decimal(str(row[1])), Decimal(str(row[2])))


def grant_allowance(user_id: str, credits: int, reason: str = "subscription_period",
                    period_days: int | None = None) -> None:
    """
    Set the period allowance and reset consumption.

    Called on subscription activation and on each renewal. `consumed` is
    reset to zero rather than the allowance being incremented, so a
    lapsed-then-resumed subscriber starts the new period clean instead of
    inheriting an old overdraft. `purchased_credits` is untouched — those
    were paid for separately and must survive the reset.

    `period_days` overrides the default month. A signup trial runs longer
    than a billing month and is granted once, so its account should say
    so rather than claiming a period that ended weeks ago.
    """
    try:
        with _engine().begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO credit_accounts
                        (user_id, allowance_credits, consumed_credits, period_start, period_end)
                    VALUES (:u, :c, 0, now(), now() + make_interval(days => :days))
                    ON CONFLICT (user_id) DO UPDATE
                       SET allowance_credits = :c,
                           consumed_credits  = 0,
                           period_start      = now(),
                           period_end        = now() + make_interval(days => :days),
                           updated_at        = now()
                """),
                {"u": user_id, "c": credits, "days": period_days or 30},
            )
            conn.execute(
                text("""INSERT INTO credit_transactions
                            (user_id, kind, credits, operation, balance_after, metadata)
                        VALUES (:u, 'grant', :c, :op, :c, :m)"""),
                {"u": user_id, "c": credits, "op": reason,
                 "m": '{"source": "grant_allowance"}'},
            )
        logger.info("Credits granted", extra={"user_id": user_id, "credits": credits})
    except Exception as exc:
        logger.error("Credit grant failed",
                     extra={"user_id": user_id, "error": str(exc)}, exc_info=True)


def revoke_allowance(user_id: str, reason: str = "subscription_cancelled") -> None:
    """Zero the period allowance on cancellation. Purchases are kept."""
    try:
        with _engine().begin() as conn:
            conn.execute(
                text("""UPDATE credit_accounts
                           SET allowance_credits = 0, consumed_credits = 0, updated_at = now()
                         WHERE user_id = :u"""),
                {"u": user_id},
            )
            conn.execute(
                text("""INSERT INTO credit_transactions
                            (user_id, kind, credits, operation, balance_after)
                        VALUES (:u, 'expiry', 0, :op, 0)"""),
                {"u": user_id, "op": reason},
            )
    except Exception as exc:
        logger.error("Credit revoke failed", extra={"user_id": user_id, "error": str(exc)})


# ── Spending ──────────────────────────────────────────────────────────

def reserve(user_id: str, credits: Decimal, vendor: str, operation: str,
            request_id: str | None = None) -> str:
    """
    Check the balance and debit an estimate, atomically.

    Returns a reservation id to pass to `settle`. Raises
    InsufficientCredits if the user cannot afford the estimate — which is
    the only place the "cannot exceed what they paid for" guarantee is
    actually enforced.
    """
    reservation_id = request_id or f"res_{uuid.uuid4().hex[:20]}"
    if credits <= 0:
        return reservation_id

    with _engine().begin() as conn:
        # FOR UPDATE: two concurrent requests must not both see the same
        # remaining balance and both spend it.
        row = conn.execute(
            text("""SELECT allowance_credits, consumed_credits, purchased_credits, allow_overage
                      FROM credit_accounts WHERE user_id = :u FOR UPDATE"""),
            {"u": user_id},
        ).fetchone()

        if row is None:
            raise InsufficientCredits(credits, Decimal(0), operation)

        allowance, consumed, purchased, overage = (
            Decimal(str(row[0])), Decimal(str(row[1])),
            Decimal(str(row[2])), bool(row[3]),
        )
        remaining = max(Decimal(0), allowance - consumed) + purchased

        if credits > remaining and not overage:
            raise InsufficientCredits(credits, remaining, operation)

        # Consume the allowance first, then purchased credits — the
        # allowance expires at period end and purchases do not, so
        # spending the perishable balance first is what the customer
        # would choose.
        from_allowance = min(credits, max(Decimal(0), allowance - consumed))
        from_purchased = credits - from_allowance

        conn.execute(
            text("""UPDATE credit_accounts
                       SET consumed_credits  = consumed_credits + :fa,
                           purchased_credits = purchased_credits - :fp,
                           updated_at = now()
                     WHERE user_id = :u"""),
            {"u": user_id, "fa": from_allowance, "fp": from_purchased},
        )
        new_remaining = remaining - credits
        conn.execute(
            text("""INSERT INTO credit_transactions
                        (user_id, kind, credits, vendor, operation, balance_after,
                         request_id, metadata)
                    VALUES (:u, 'debit', :c, :v, :o, :b, :r, :m)
                    ON CONFLICT (user_id, request_id) WHERE request_id IS NOT NULL
                    DO NOTHING"""),
            {"u": user_id, "c": -credits, "v": vendor, "o": operation,
             "b": new_remaining, "r": reservation_id, "m": '{"phase": "reserve"}'},
        )
    return reservation_id


def settle(user_id: str, reservation_id: str, actual_credits: Decimal,
           vendor: str, operation: str, usd_cost: Decimal | None = None,
           quantity: float | None = None, unit: str | None = None) -> None:
    """
    Reconcile a reservation against what the call really cost.

    Writes only the DIFFERENCE, so the ledger sums correctly: the reserve
    row already carries the estimate. A refund when the call came in
    cheaper is credited back rather than kept, because keeping it would
    bill for tokens that were never generated.
    """
    try:
        with _engine().begin() as conn:
            row = conn.execute(
                text("""SELECT credits FROM credit_transactions
                         WHERE user_id = :u AND request_id = :r AND kind = 'debit'
                         ORDER BY id LIMIT 1"""),
                {"u": user_id, "r": reservation_id},
            ).fetchone()
            reserved = -Decimal(str(row[0])) if row else Decimal(0)
            delta = actual_credits - reserved
            if delta == 0:
                return

            conn.execute(
                text("""UPDATE credit_accounts
                           SET consumed_credits = GREATEST(0, consumed_credits + :d),
                               updated_at = now()
                         WHERE user_id = :u"""),
                {"u": user_id, "d": delta},
            )
            conn.execute(
                text("""INSERT INTO credit_transactions
                            (user_id, kind, credits, vendor, operation, usd_cost,
                             quantity, unit, request_id, metadata)
                        VALUES (:u, :k, :c, :v, :o, :usd, :q, :un, :r, :m)"""),
                {"u": user_id,
                 "k": "debit" if delta > 0 else "refund",
                 "c": -delta, "v": vendor, "o": operation,
                 "usd": usd_cost, "q": quantity, "un": unit,
                 "r": f"{reservation_id}:settle",
                 "m": '{"phase": "settle"}'},
            )
    except Exception as exc:
        # Never fail a served request because settlement bookkeeping
        # failed. The reservation already stands, so the user was charged
        # the estimate — an approximation, not free usage.
        logger.warning("Credit settle failed: reservation stands",
                       extra={"user_id": user_id, "reservation": reservation_id,
                              "error": str(exc)})


def recent_transactions(user_id: str, limit: int = 50) -> list[dict]:
    try:
        with _engine().connect() as conn:
            rows = conn.execute(
                text("""SELECT kind, credits, vendor, operation, usd_cost,
                               quantity, unit, balance_after, created_at
                          FROM credit_transactions
                         WHERE user_id = :u
                         ORDER BY id DESC LIMIT :l"""),
                {"u": user_id, "l": limit},
            ).fetchall()
        return [{
            "kind": r[0], "credits": float(r[1]), "vendor": r[2], "operation": r[3],
            "usd_cost": float(r[4]) if r[4] is not None else None,
            "quantity": float(r[5]) if r[5] is not None else None,
            "unit": r[6],
            "balance_after": float(r[7]) if r[7] is not None else None,
            "at": r[8].isoformat() if r[8] else None,
        } for r in rows]
    except Exception:
        return []


# ── Platform API keys ─────────────────────────────────────────────────

_KEY_PREFIX = "aur"


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_api_key(user_id: str, name: str = "Default key",
                  environment: str = "live",
                  scopes: list[str] | None = None) -> dict:
    """
    Mint a platform API key.

    The plaintext is returned exactly once and never stored — only its
    SHA-256. If the user loses it they rotate, the same as a password.
    Storing it recoverably would mean a database read exposes every
    customer's credentials.

    This key authenticates against AUREUS. It is deliberately not an
    upstream vendor key: those are non-redistributable under Anthropic's
    and Polygon's terms, and handing one out would bill the platform
    owner without attribution or limit.
    """
    raw = f"{_KEY_PREFIX}_{environment}_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw)
    display = f"{raw[:16]}…{raw[-4:]}"

    with _engine().begin() as conn:
        allowed = conn.execute(
            text("""SELECT st.api_keys_allowed
                      FROM active_user_subscriptions us
                      JOIN subscription_tiers st ON st.id = us.tier_id
                     WHERE us.user_id = :u
                     LIMIT 1"""),
            {"u": user_id},
        ).scalar()
        allowed = int(allowed or 0)
        if allowed <= 0:
            raise PermissionError("Your plan does not include programmatic API access.")

        live = conn.execute(
            text("SELECT count(*) FROM api_keys WHERE user_id = :u AND revoked_at IS NULL"),
            {"u": user_id},
        ).scalar() or 0
        if live >= allowed:
            raise PermissionError(
                f"Your plan allows {allowed} active API key(s). Revoke one first."
            )

        row = conn.execute(
            text("""INSERT INTO api_keys (user_id, key_hash, key_prefix, name, environment, scopes)
                    VALUES (:u, :h, :p, :n, :e, :s)
                    RETURNING id, created_at"""),
            {"u": user_id, "h": key_hash, "p": display, "n": name,
             "e": environment, "s": scopes or ["analysis:read"]},
        ).fetchone()

    logger.info("API key issued", extra={"user_id": user_id, "key_id": str(row[0])})
    return {
        "id": str(row[0]),
        "api_key": raw,          # shown once
        "key_prefix": display,
        "name": name,
        "environment": environment,
        "created_at": row[1].isoformat(),
        "warning": "Store this now, it cannot be retrieved again.",
    }


def verify_api_key(raw_key: str) -> str | None:
    """
    Resolve a presented key to a user id, or None.

    Also bumps last_used_at and the request counter, which is what makes
    an unused key visible for cleanup and a compromised one traceable.
    """
    if not raw_key or not raw_key.startswith(f"{_KEY_PREFIX}_"):
        return None
    try:
        with _engine().begin() as conn:
            row = conn.execute(
                text("""SELECT id, user_id FROM api_keys
                         WHERE key_hash = :h
                           AND revoked_at IS NULL
                           AND (expires_at IS NULL OR expires_at > now())"""),
                {"h": _hash_key(raw_key)},
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                text("""UPDATE api_keys
                           SET last_used_at = now(), request_count = request_count + 1
                         WHERE id = :i"""),
                {"i": row[0]},
            )
            return str(row[1])
    except Exception as exc:
        logger.warning("API key verification failed", extra={"error": str(exc)})
        return None


def list_api_keys(user_id: str) -> list[dict]:
    try:
        with _engine().connect() as conn:
            rows = conn.execute(
                text("""SELECT id, key_prefix, name, environment, scopes, last_used_at,
                               request_count, revoked_at, created_at
                          FROM api_keys WHERE user_id = :u ORDER BY created_at DESC"""),
                {"u": user_id},
            ).fetchall()
        return [{
            "id": str(r[0]), "key_prefix": r[1], "name": r[2], "environment": r[3],
            "scopes": list(r[4] or []),
            "last_used_at": r[5].isoformat() if r[5] else None,
            "request_count": int(r[6]),
            "revoked": r[7] is not None,
            "created_at": r[8].isoformat() if r[8] else None,
        } for r in rows]
    except Exception:
        return []


def revoke_api_key(user_id: str, key_id: str, reason: str = "user_revoked") -> bool:
    try:
        with _engine().begin() as conn:
            res = conn.execute(
                text("""UPDATE api_keys
                           SET revoked_at = now(), revoked_reason = :r
                         WHERE id = :i AND user_id = :u AND revoked_at IS NULL"""),
                {"i": key_id, "u": user_id, "r": reason},
            )
            return res.rowcount > 0
    except Exception:
        return False


def revoke_all_keys(user_id: str, reason: str) -> int:
    """Used on cancellation: a lapsed plan must not keep live API access."""
    try:
        with _engine().begin() as conn:
            res = conn.execute(
                text("""UPDATE api_keys SET revoked_at = now(), revoked_reason = :r
                         WHERE user_id = :u AND revoked_at IS NULL"""),
                {"u": user_id, "r": reason},
            )
            return res.rowcount
    except Exception:
        return 0
