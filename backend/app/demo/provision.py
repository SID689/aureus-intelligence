"""
app/demo/provision.py
---------------------
Creates the account a visitor lands in when they enter the demo.

=====================================================================
ONE ACCOUNT PER DEVICE, NOT ONE ACCOUNT FOR THE ROOM
=====================================================================
The obvious implementation is a single shared demo login. It breaks the
moment two people use it: the portfolio is shared state, so one person
deleting a position changes what everybody else is looking at, and the
next tap re-renders somebody else's edit as if the app had glitched.

So each device gets its own account, provisioned on first arrival from
a `device` token the browser keeps. Everyone has their own book to edit,
while the expensive shared things — the scanner board, the catalyst
timeline, the cached analyses — stay global, because those are read-only
and are exactly what should be shared.

=====================================================================
WHAT A DEMO ACCOUNT IS
=====================================================================
  * A real users row, `auth_provider = 'demo'`, no password hash. It
    cannot be signed into through the login form, because there is no
    password to verify and the login endpoint refuses an empty hash.
  * An active subscription on the demo tier, so entitlements resolve
    from the database exactly like a paying customer's. Nothing in the
    app special-cases a demo session to unlock a feature; the plan does
    it, which is the only way the demo proves the real gating works.
  * A recorded risk_disclosure consent, so the onboarding wizard does
    not stand between a scanned QR code and the dashboard.
  * The showcase portfolio, seeded so the tape, the allocation and the
    risk readouts have something to say on the first screen.

Demo rows are disposable and marked as such by their email domain, so
`purge_demo_users` can clear them between events.
"""

import logging
import re
import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.core.config import get_settings
from app.demo.showcase import (
    DEMO_DISPLAY_NAME, DEMO_EMAIL_DOMAIN, SHOWCASE_PORTFOLIO, SHOWCASE_PORTFOLIO_NAME,
)

logger = logging.getLogger("aureus.demo.provision")

_DEVICE_RE = re.compile(r"[^a-z0-9]+")


def _engine() -> Engine:
    from sqlalchemy import create_engine
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def normalise_device(device: str | None) -> str:
    """
    A device token reduced to something safe to put in an email local part.

    The token comes from the browser, so it is untrusted input that ends
    up in a database string. Anything outside [a-z0-9] is collapsed, the
    result is length-capped, and an empty or missing token becomes a fresh
    random one rather than a shared default: two visitors arriving with no
    token must not land in the same account.
    """
    slug = _DEVICE_RE.sub("", (device or "").lower())[:24]
    return slug or secrets.token_hex(8)


def demo_email(device: str) -> str:
    return f"demo-{device}@{DEMO_EMAIL_DOMAIN}"


def _tier_id(conn: Connection, tier_name: str) -> str | None:
    row = conn.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = :t"), {"t": tier_name}
    ).fetchone()
    return str(row.id) if row else None


def _seed_portfolio(conn: Connection, user_id: str) -> None:
    """
    Give the account the showcase book, once, already priced.

    Pricing here rather than leaving it to the first refresh is not a
    nicety. Holdings are priced by the add/update path, so rows inserted
    directly arrive with current_price NULL, and the dashboard renders
    that faithfully: portfolio value $0, return -100%, an empty tape. The
    first screen of the demo would be a loss column.

    Quotes come from the shared price cache, so the first visitor of the
    event pays six provider calls and everyone after them pays none.
    A ticker nobody can price is left NULL, which the UI already renders
    as "not priced" rather than as zero.
    """
    existing = conn.execute(
        text("SELECT id FROM portfolios WHERE user_id = :uid LIMIT 1"), {"uid": user_id}
    ).fetchone()
    if existing:
        return

    portfolio_id = str(uuid.uuid4())
    conn.execute(
        text("""INSERT INTO portfolios (id, user_id, name, is_paper, base_currency)
                VALUES (:id, :uid, :name, true, 'USD')"""),
        {"id": portfolio_id, "uid": user_id, "name": SHOWCASE_PORTFOLIO_NAME},
    )

    try:
        from app.ingestion.price_cache import get_prices
        quotes = get_prices([p.ticker for p in SHOWCASE_PORTFOLIO])
    except Exception as exc:                                      # noqa: BLE001
        logger.warning("Could not price the showcase book", extra={"error": str(exc)})
        quotes = {}

    total = sum(quotes.get(p.ticker, 0.0) * p.quantity for p in SHOWCASE_PORTFOLIO)
    for pos in SHOWCASE_PORTFOLIO:
        price = quotes.get(pos.ticker)
        weight = round(price * pos.quantity / total * 100, 4) if price and total > 0 else None
        conn.execute(
            text("""INSERT INTO portfolio_holdings
                        (id, portfolio_id, user_id, ticker, quantity, average_cost_basis,
                         current_price, current_weight, last_priced_at)
                    VALUES (gen_random_uuid(), :pid, :uid, :t, :q, :c, :price, :weight,
                            CASE WHEN :price IS NULL THEN NULL ELSE now() END)
                    ON CONFLICT (portfolio_id, ticker) DO NOTHING"""),
            {"pid": portfolio_id, "uid": user_id, "t": pos.ticker,
             "q": pos.quantity, "c": pos.cost_basis, "price": price, "weight": weight},
        )


def _record_consent(conn: Connection, user_id: str) -> None:
    """
    Pre-sign the risk disclosure.

    The onboarding wizard is a real part of the product and is shown on
    the normal sign-up path. Standing it in front of a demo session would
    mean a room of people filling in a questionnaire instead of looking at
    the app, so the demo account arrives with the acknowledgment already
    recorded. The row is genuine and auditable, and it names itself as a
    demo grant rather than pretending a person signed it.
    """
    already = conn.execute(
        text("""SELECT 1 FROM consent_records
                 WHERE user_id = :uid AND consent_type = 'risk_disclosure' AND granted = true
                 LIMIT 1"""),
        {"uid": user_id},
    ).fetchone()
    if already:
        return
    conn.execute(
        text("""INSERT INTO consent_records (id, user_id, consent_type, version, granted, granted_at)
                VALUES (gen_random_uuid(), :uid, 'risk_disclosure', 'demo', true, now())"""),
        {"uid": user_id},
    )
    conn.execute(
        text("""UPDATE profiles
                   SET risk_disclosure_acknowledged_at = now(),
                       terms_version_accepted = 'demo',
                       updated_at = now()
                 WHERE user_id = :uid"""),
        {"uid": user_id},
    )


def ensure_demo_session(device: str | None = None) -> dict:
    """
    The demo account for this device, created if it does not exist yet.

    Idempotent: a returning visitor with the same token gets the same
    account and the edits they made a minute ago.
    """
    settings = get_settings()
    if not settings.demo_mode:
        raise PermissionError("Demo mode is not enabled in this environment")

    slug = normalise_device(device)
    email = demo_email(slug)
    engine = _engine()
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("""SELECT u.id, u.email, p.display_name, st.tier_name
                          FROM users u
                          LEFT JOIN profiles p ON p.user_id = u.id
                          LEFT JOIN user_subscriptions us
                                 ON us.user_id = u.id AND us.status IN ('active', 'trialing')
                          LEFT JOIN subscription_tiers st ON st.id = us.tier_id
                         WHERE u.email = :email AND u.deleted_at IS NULL"""),
                {"email": email},
            ).fetchone()

            if existing:
                user_id = str(existing.id)
                # Re-seed anything a previous partial run left out, so a
                # half-provisioned account repairs itself instead of
                # landing someone on an empty dashboard.
                _record_consent(conn, user_id)
                _seed_portfolio(conn, user_id)
                tier = existing.tier_name or settings.demo_tier
                created = False
            else:
                user_id = str(uuid.uuid4())
                conn.execute(
                    text("""INSERT INTO users (id, email, password_hash, auth_provider, role, is_active)
                            VALUES (:id, :email, NULL, 'demo', 'owner', true)"""),
                    {"id": user_id, "email": email},
                )
                conn.execute(
                    text("""INSERT INTO profiles (user_id, display_name, country_code)
                            VALUES (:uid, :name, 'US')"""),
                    {"uid": user_id, "name": DEMO_DISPLAY_NAME},
                )
                tier_id = _tier_id(conn, settings.demo_tier)
                if tier_id:
                    conn.execute(
                        text("""INSERT INTO user_subscriptions
                                    (id, user_id, tier_id, stripe_customer_id, status)
                                VALUES (gen_random_uuid(), :uid, :tid, :cust, 'active')"""),
                        {"uid": user_id, "tid": tier_id, "cust": f"demo_{slug}"},
                    )
                _record_consent(conn, user_id)
                _seed_portfolio(conn, user_id)
                tier = settings.demo_tier
                created = True

        # Outside the transaction: a failed credit grant must not undo a
        # perfectly good account. Credits only affect whether theses are
        # LLM-polished, and the analysis path already falls back to
        # deterministic prose when they run out.
        if created and settings.demo_credit_allowance > 0:
            from app.billing.credits import grant_allowance
            grant_allowance(user_id, settings.demo_credit_allowance, reason="demo_session")

        # `created` is a reserved LogRecord attribute — passing it in extra
        # raises rather than logging.
        logger.info("Demo session ready",
                    extra={"user_id": user_id, "device": slug, "provisioned": created})
        return {
            "user_id": user_id,
            "email": email,
            "display_name": DEMO_DISPLAY_NAME,
            "tier": tier,
            "device": slug,
            "created": created,
            "demo": True,
            "stripe_customer_id": "",
        }
    finally:
        engine.dispose()


def purge_demo_users(older_than_hours: int = 0) -> int:
    """
    Delete demo accounts. Returns the number removed.

    Everything a demo account owns is reachable by ON DELETE CASCADE from
    users, so this is a single statement. `older_than_hours = 0` clears
    them all, which is what you want between two events on the same day.
    """
    engine = _engine()
    try:
        with engine.begin() as conn:
            res = conn.execute(
                text("""DELETE FROM users
                          WHERE auth_provider = 'demo'
                            AND email LIKE :pattern
                            AND created_at < now() - make_interval(hours => :h)"""),
                {"pattern": f"%@{DEMO_EMAIL_DOMAIN}", "h": older_than_hours},
            )
            return res.rowcount or 0
    finally:
        engine.dispose()
