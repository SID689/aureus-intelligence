"""
app/billing/treasury.py
-------------------------
Revenue against real vendor cost, and the break-even arithmetic that
decides when a vendor subscription can be afforded.

=====================================================================
THE HONEST ANSWER TO "ZERO OUT-OF-POCKET"
=====================================================================
The goal is that Stripe revenue pays the Anthropic/Polygon/Finnhub bills
so the owner never funds them personally. Half of that is a plumbing
problem and half of it is not, and the half that is not is the half that
decides whether it works.

VENDOR COSTS COME IN TWO SHAPES:

  VARIABLE — Anthropic, OpenAI. Billed per token or per minute. These
  genuinely are self-funding: a user's own credit spend is what triggers
  the cost, so revenue and cost move together and the margin is whatever
  markup was set. Nothing needs to be timed.

  FIXED — Polygon ($29-199/mo), Finnhub (~$150/mo), X API ($100/mo),
  Reddit (~$100/mo), Alpha Vantage (~$50/mo). These bill the same amount
  whether the platform has zero subscribers or a thousand. They are a
  floor, not a variable cost, and no payment routing makes them disappear.

Total fixed floor if every premium source is enabled: about $628/month.
Until monthly gross profit exceeds that, the difference is paid by the
owner. That is a business milestone, not a code path — Stripe Issuing can
ROUTE money that already exists, it cannot create revenue that does not.

There is also a TIMING gap even after break-even. Stripe holds funds on a
rolling payout schedule (commonly 2-7 days for a new account), while
vendor bills fall due on fixed dates. So the account needs roughly one
month of fixed costs as working capital regardless of margin.

WHAT THIS MODULE THEREFORE DOES:
  - tracks every dollar in and out, so margin is measured rather than
    assumed;
  - computes, per vendor, how many subscribers of each tier are needed
    before subscribing to it is self-funding;
  - flags when the platform is running at a loss, early enough to act.

WHAT IT DELIBERATELY DOES NOT DO:
  - move money. No card is created, no payout is triggered, no vendor is
    charged from here. Those actions need the owner's own credentials in
    Stripe and on each vendor's billing page. The application's job is to
    tell them what to do and when; performing it would mean holding
    financial credentials the application has no business holding.
"""

import logging
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.billing.treasury")

# Stripe's standard online card rate in the US. Used to convert gross
# subscription revenue into what actually lands in the balance, because
# budgeting against gross overstates available cash by ~3%.
STRIPE_PCT_FEE = Decimal("0.029")
STRIPE_FLAT_FEE = Decimal("0.30")


@lru_cache(maxsize=1)
def _engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=3)


def net_of_stripe_fees(gross_usd: Decimal, transactions: int = 1) -> Decimal:
    """What actually reaches the Stripe balance after processing fees."""
    return (gross_usd * (1 - STRIPE_PCT_FEE)) - (STRIPE_FLAT_FEE * transactions)


@dataclass
class VendorPosition:
    vendor: str
    plan_name: str
    cost_type: str
    monthly_usd: Decimal
    required_for_tier: str | None
    is_subscribed: bool
    # Subscribers of the gating tier needed before this vendor pays for
    # itself out of that tier's gross profit alone.
    subscribers_to_break_even: int | None
    affordable_now: bool

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor,
            "plan_name": self.plan_name,
            "cost_type": self.cost_type,
            "monthly_usd": float(self.monthly_usd),
            "required_for_tier": self.required_for_tier,
            "is_subscribed": self.is_subscribed,
            "subscribers_to_break_even": self.subscribers_to_break_even,
            "affordable_now": self.affordable_now,
        }


def _tier_gross_profit() -> dict[str, Decimal]:
    """
    Monthly gross profit per subscriber, by tier.

    Price minus the REAL vendor cost the allowance represents. The
    allowance is denominated in billed credits, so the underlying cost is
    the allowance divided by the markup — billing the full allowance as
    cost would understate margin by the markup factor.
    """
    out: dict[str, Decimal] = {}
    try:
        with _engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT tier_name, price_cents, monthly_credits FROM subscription_tiers
            """)).fetchall()
            markup = conn.execute(text("""
                SELECT COALESCE(AVG(markup_multiplier), 3.0)
                  FROM vendor_cost_rates
                 WHERE vendor = 'anthropic' AND is_active
            """)).scalar() or Decimal("3.0")
    except Exception as exc:
        logger.warning("Tier profit read failed", extra={"error": str(exc)})
        return {}

    markup = Decimal(str(markup))
    for tier, price_cents, credits in rows:
        price = Decimal(price_cents or 0) / 100
        billed_allowance = Decimal(credits or 0) / 1000      # credits -> USD billed
        real_cost = billed_allowance / markup if markup > 0 else billed_allowance
        out[str(tier)] = price - real_cost
    return out


def vendor_positions() -> list[VendorPosition]:
    """Every vendor, with the subscriber count that makes it self-funding."""
    profits = _tier_gross_profit()
    counts = subscriber_counts()

    try:
        with _engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT vendor, plan_name, cost_type, monthly_usd,
                       required_for_tier, is_subscribed
                  FROM vendor_subscriptions
                 ORDER BY monthly_usd DESC
            """)).fetchall()
    except Exception as exc:
        logger.warning("Vendor read failed", extra={"error": str(exc)})
        return []

    out: list[VendorPosition] = []
    for vendor, plan, cost_type, monthly, tier, subscribed in rows:
        monthly = Decimal(str(monthly or 0))
        need: int | None = None
        if monthly > 0 and tier:
            gp = profits.get(tier, Decimal(0))
            # A tier whose gross profit is <= 0 can never fund anything,
            # however many subscribers it has. None communicates that
            # honestly rather than printing a huge finite number.
            #
            # math.ceil, NOT the -(-a // b) integer idiom: Decimal's //
            # truncates toward zero rather than flooring, so that idiom
            # returns 0 for any cost smaller than one subscriber's gross
            # profit — reporting "needs 0 subscribers" for a $199/month
            # bill.
            need = math.ceil(monthly / gp) if gp > 0 else None
        have = counts.get(tier or "", 0)
        out.append(VendorPosition(
            vendor=vendor, plan_name=plan, cost_type=cost_type,
            monthly_usd=monthly, required_for_tier=tier,
            is_subscribed=bool(subscribed),
            subscribers_to_break_even=need,
            affordable_now=(need is not None and have >= need) or monthly == 0,
        ))
    return out


def subscriber_counts() -> dict[str, int]:
    """Active subscribers per tier."""
    try:
        with _engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT st.tier_name, count(*)
                  FROM active_user_subscriptions us
                  JOIN subscription_tiers st ON st.id = us.tier_id
                 GROUP BY st.tier_name
            """)).fetchall()
        return {str(r[0]): int(r[1]) for r in rows}
    except Exception:
        return {}


def monthly_recurring_revenue() -> Decimal:
    """Gross MRR from active paid subscriptions."""
    try:
        with _engine().connect() as conn:
            total = conn.execute(text("""
                SELECT COALESCE(SUM(st.price_cents), 0)
                  FROM active_user_subscriptions us
                  JOIN subscription_tiers st ON st.id = us.tier_id
                 WHERE us.status = 'active'
                   AND us.stripe_subscription_id IS NOT NULL
            """)).scalar() or 0
        return Decimal(total) / 100
    except Exception:
        return Decimal(0)


def variable_spend_this_month() -> Decimal:
    """
    Real (pre-markup) vendor cost incurred this month, from the credit
    ledger. This is what the usage-billed vendors will actually invoice.
    """
    try:
        with _engine().connect() as conn:
            billed = conn.execute(text("""
                SELECT COALESCE(SUM(-credits), 0) / 1000.0
                  FROM credit_transactions
                 WHERE kind = 'debit'
                   AND created_at >= date_trunc('month', now())
            """)).scalar() or 0
            markup = conn.execute(text("""
                SELECT COALESCE(AVG(markup_multiplier), 3.0)
                  FROM vendor_cost_rates WHERE is_active
            """)).scalar() or 3
        return Decimal(str(billed)) / Decimal(str(markup))
    except Exception:
        return Decimal(0)


def fixed_spend_monthly() -> Decimal:
    """Committed monthly cost of vendors currently subscribed to."""
    try:
        with _engine().connect() as conn:
            total = conn.execute(text("""
                SELECT COALESCE(SUM(monthly_usd), 0)
                  FROM vendor_subscriptions WHERE is_subscribed
            """)).scalar() or 0
        return Decimal(str(total))
    except Exception:
        return Decimal(0)


def treasury_summary() -> dict:
    """
    The whole picture: revenue, both cost shapes, margin, runway posture.

    `out_of_pocket_usd` is the number the owner actually cares about — it
    is what they will personally fund this month if nothing changes.
    """
    mrr = monthly_recurring_revenue()
    counts = subscriber_counts()
    paid_subs = sum(v for k, v in counts.items() if k != "sovereign")
    net_revenue = net_of_stripe_fees(mrr, max(1, paid_subs)) if mrr > 0 else Decimal(0)

    fixed = fixed_spend_monthly()
    variable = variable_spend_this_month()
    total_cost = fixed + variable
    margin = net_revenue - total_cost

    positions = vendor_positions()
    unsubscribed_total = sum(
        (p.monthly_usd for p in positions if not p.is_subscribed), Decimal(0)
    )

    return {
        "mrr_gross_usd": float(mrr),
        "mrr_net_of_stripe_fees_usd": float(net_revenue),
        "subscribers": counts,
        "cost": {
            "fixed_monthly_usd": float(fixed),
            "variable_month_to_date_usd": float(variable),
            "total_usd": float(total_cost),
        },
        "margin_usd": float(margin),
        "margin_pct": float(round(margin / net_revenue * 100, 1)) if net_revenue > 0 else None,
        # Positive means the owner funds this much personally this month.
        "out_of_pocket_usd": float(max(Decimal(0), -margin)),
        "self_funding": margin >= 0,
        "if_all_vendors_enabled": {
            "additional_fixed_usd": float(unsubscribed_total),
            "total_fixed_usd": float(fixed + unsubscribed_total),
            "margin_would_be_usd": float(net_revenue - (fixed + unsubscribed_total) - variable),
        },
        "vendors": [p.to_dict() for p in positions],
        "guidance": _guidance(margin, net_revenue, fixed, unsubscribed_total, counts),
    }


def _guidance(margin: Decimal, net_revenue: Decimal, fixed: Decimal,
              pending_fixed: Decimal, counts: dict[str, int]) -> list[str]:
    """Plain statements about what the numbers mean for the next action."""
    notes: list[str] = []
    paid = sum(v for k, v in counts.items() if k != "sovereign")

    if paid == 0:
        notes.append(
            "No paying subscribers yet. Every vendor subscription taken now is funded "
            "entirely out of pocket: subscribe to a premium API only when the tier that "
            "needs it has customers."
        )
    if margin < 0:
        notes.append(
            f"Running at a loss of ${-margin:.2f}/month. This is covered personally until "
            "revenue rises or a vendor is dropped."
        )
    elif net_revenue > 0:
        notes.append(
            f"Self-funding: ${margin:.2f}/month remains after all vendor costs and Stripe fees."
        )
    if pending_fixed > 0:
        notes.append(
            f"Enabling every remaining premium API would add ${pending_fixed:.2f}/month of "
            "FIXED cost, owed whether or not anyone uses it."
        )
    notes.append(
        "Stripe pays out on a rolling schedule while vendor bills fall due on fixed dates, "
        "so roughly one month of fixed costs is needed as working capital even at a healthy "
        "margin."
    )
    return notes


def record_treasury_entry(direction: str, category: str, usd_amount: Decimal,
                          vendor: str | None = None,
                          stripe_reference: str | None = None,
                          notes: str | None = None) -> None:
    """Append an actual money movement, for reconciliation against Stripe."""
    try:
        with _engine().begin() as conn:
            conn.execute(
                text("""INSERT INTO treasury_ledger
                            (direction, category, vendor, usd_amount, stripe_reference, notes)
                        VALUES (:d, :c, :v, :a, :s, :n)"""),
                {"d": direction, "c": category, "v": vendor,
                 "a": usd_amount, "s": stripe_reference, "n": notes},
            )
    except Exception as exc:
        logger.warning("Treasury entry failed", extra={"error": str(exc)})
