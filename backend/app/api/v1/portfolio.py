"""
app/api/v1/portfolio.py
--------------------------
Fixes "no way to add shares of a company I hold." Full CRUD for
portfolio holdings, plus automatic weight recalculation — every time a
holding changes, every holding in that portfolio gets its current_weight
recomputed as (position value / total portfolio value) * 100, and current
prices are refreshed from the real market data service so the numbers
you see are live, not the values you entered at purchase time.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.core.entitlements import resolve_entitlements, next_tier
from app.core.config import get_settings
from app.ingestion.market_data import MarketDataService
from app.ingestion.rate_limiter import FallbackExhaustedError

logger = logging.getLogger("aureus.api.portfolio")
router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AddHoldingRequest(BaseModel):
    portfolio_id:       str
    user_id:            str
    ticker:             str = Field(pattern=r"^[A-Za-z.\-]{1,10}$")
    quantity:           float = Field(gt=0)
    average_cost_basis: float = Field(gt=0)


class UpdateHoldingRequest(BaseModel):
    user_id:            str
    quantity:           float | None = Field(default=None, gt=0)
    average_cost_basis: float | None = Field(default=None, gt=0)


class EnsurePortfolioRequest(BaseModel):
    user_id: str
    name:    str = "My Portfolio"
    is_paper: bool = True


# ── Weight recalculation ───────────────────────────────────────────────────────

def _recalculate_portfolio_weights(portfolio_id: str) -> None:
    """
    Re-price every holding in the portfolio via the real market data
    service, then recompute each holding's weight as a % of total value.
    """
    engine = _get_engine()
    svc = MarketDataService()
    try:
        with engine.begin() as conn:
            holdings = conn.execute(
                text("SELECT id, ticker, quantity FROM portfolio_holdings WHERE portfolio_id = :pid"),
                {"pid": portfolio_id},
            ).fetchall()

            if not holdings:
                return

            priced: list[tuple[str, float, float]] = []
            total_value = 0.0
            for h in holdings:
                try:
                    price = svc.fetch_latest_price(h.ticker)
                except FallbackExhaustedError:
                    existing = conn.execute(
                        text("SELECT current_price FROM portfolio_holdings WHERE id = :id"),
                        {"id": h.id},
                    ).fetchone()
                    price = float(existing.current_price) if existing and existing.current_price else 0.0
                    logger.warning("Could not re-price holding, keeping last known price", extra={"ticker": h.ticker})

                value = price * float(h.quantity)
                priced.append((str(h.id), price, value))
                total_value += value

            for holding_id, price, value in priced:
                weight = (value / total_value * 100) if total_value > 0 else 0.0
                conn.execute(
                    text("""
                        UPDATE portfolio_holdings
                        SET current_price = :price, current_weight = :weight, last_priced_at = NOW(), updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"price": price, "weight": round(weight, 4), "id": holding_id},
                )
    finally:
        engine.dispose()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ensure-default")
def ensure_default_portfolio(req: EnsurePortfolioRequest) -> dict:
    """Idempotently ensure the user has at least one portfolio."""
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM portfolios WHERE user_id = :uid LIMIT 1"),
                {"uid": req.user_id},
            ).fetchone()
            if existing:
                return {"portfolio_id": str(existing.id), "created": False}

            new_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO portfolios (id, user_id, name, is_paper, base_currency)
                    VALUES (:id, :uid, :name, :is_paper, 'USD')
                """),
                {"id": new_id, "uid": req.user_id, "name": req.name, "is_paper": req.is_paper},
            )
            return {"portfolio_id": new_id, "created": True}
    finally:
        engine.dispose()


@router.get("/holdings")
def list_holdings(portfolio_id: str) -> dict:
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, ticker, quantity, average_cost_basis, current_price,
                           current_weight, beta, last_priced_at
                    FROM portfolio_holdings
                    WHERE portfolio_id = :pid
                    ORDER BY current_weight DESC NULLS LAST
                """),
                {"pid": portfolio_id},
            ).fetchall()
    finally:
        engine.dispose()

    holdings = [
        {
            "id": str(r.id), "ticker": r.ticker, "quantity": float(r.quantity),
            "average_cost_basis": float(r.average_cost_basis),
            "current_price": float(r.current_price) if r.current_price else None,
            "current_weight": float(r.current_weight) if r.current_weight else None,
            "beta": float(r.beta) if r.beta else None,
            "last_priced_at": r.last_priced_at.isoformat() if r.last_priced_at else None,
        }
        for r in rows
    ]
    total_value = sum((h["current_price"] or 0) * h["quantity"] for h in holdings)
    total_cost  = sum(h["average_cost_basis"] * h["quantity"] for h in holdings)
    return {
        "portfolio_id": portfolio_id,
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_value - total_cost, 2),
        "total_pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0.0,
    }


@router.post("/holdings")
def add_or_update_holding(req: AddHoldingRequest) -> dict:
    """
    Add a new holding, or if the ticker already exists in this portfolio,
    merge the new lot into the existing position with a blended average
    cost basis (standard weighted-average accounting).
    """
    ticker = req.ticker.upper().strip()
    engine = _get_engine()
    ent = resolve_entitlements(req.user_id)

    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id, quantity, average_cost_basis FROM portfolio_holdings WHERE portfolio_id = :pid AND ticker = :ticker"),
                {"pid": req.portfolio_id, "ticker": ticker},
            ).fetchone()

            # The cap applies to DISTINCT positions, so adding to a ticker
            # already held is always allowed even at the limit — otherwise
            # a user at the cap could not average into what they own, which
            # would be a bizarre restriction to hit.
            if existing is None and ent.max_portfolio_holdings is not None:
                held = conn.execute(
                    text("SELECT count(*) FROM portfolio_holdings WHERE portfolio_id = :pid"),
                    {"pid": req.portfolio_id},
                ).scalar() or 0
                if held >= ent.max_portfolio_holdings:
                    raise HTTPException(status_code=402, detail={
                        "error": "limit_exceeded",
                        "resource": "portfolio_holdings",
                        "message": (
                            f"The {ent.display_name} plan holds up to "
                            f"{ent.max_portfolio_holdings} positions per portfolio. "
                            f"Remove one, or upgrade for more."
                        ),
                        "limit": ent.max_portfolio_holdings,
                        "current": held,
                        "current_tier": ent.tier,
                        "suggested_tier": next_tier(ent.tier),
                    })

            if existing:
                old_qty, old_cost = float(existing.quantity), float(existing.average_cost_basis)
                new_qty = old_qty + req.quantity
                blended_cost = ((old_qty * old_cost) + (req.quantity * req.average_cost_basis)) / new_qty
                conn.execute(
                    text("""
                        UPDATE portfolio_holdings
                        SET quantity = :qty, average_cost_basis = :cost, updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"qty": new_qty, "cost": round(blended_cost, 6), "id": existing.id},
                )
                holding_id = str(existing.id)
                action = "merged"
            else:
                holding_id = str(uuid.uuid4())
                conn.execute(
                    text("""
                        INSERT INTO portfolio_holdings
                          (id, portfolio_id, user_id, ticker, quantity, average_cost_basis, current_weight)
                        VALUES (:id, :pid, :uid, :ticker, :qty, :cost, 0)
                    """),
                    {
                        "id": holding_id, "pid": req.portfolio_id, "uid": req.user_id,
                        "ticker": ticker, "qty": req.quantity, "cost": req.average_cost_basis,
                    },
                )
                action = "created"

        _recalculate_portfolio_weights(req.portfolio_id)
        logger.info("Holding added/updated", extra={"ticker": ticker, "action": action})
        return {"holding_id": holding_id, "ticker": ticker, "action": action}

    except Exception as exc:
        logger.error("Add holding failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not add holding: {exc}")
    finally:
        engine.dispose()


@router.put("/holdings/{holding_id}")
def update_holding(holding_id: str, req: UpdateHoldingRequest) -> dict:
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT portfolio_id FROM portfolio_holdings WHERE id = :id AND user_id = :uid"),
                {"id": holding_id, "uid": req.user_id},
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Holding not found")

            updates, params = [], {"id": holding_id}
            if req.quantity is not None:
                updates.append("quantity = :qty"); params["qty"] = req.quantity
            if req.average_cost_basis is not None:
                updates.append("average_cost_basis = :cost"); params["cost"] = req.average_cost_basis
            if updates:
                conn.execute(text(f"UPDATE portfolio_holdings SET {', '.join(updates)}, updated_at = NOW() WHERE id = :id"), params)
            portfolio_id = str(row.portfolio_id)

        _recalculate_portfolio_weights(portfolio_id)
        return {"holding_id": holding_id, "updated": True}
    finally:
        engine.dispose()


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: str, user_id: str) -> dict:
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT portfolio_id FROM portfolio_holdings WHERE id = :id AND user_id = :uid"),
                {"id": holding_id, "uid": user_id},
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Holding not found")
            portfolio_id = str(row.portfolio_id)
            conn.execute(text("DELETE FROM portfolio_holdings WHERE id = :id"), {"id": holding_id})

        _recalculate_portfolio_weights(portfolio_id)
        return {"deleted": True}
    finally:
        engine.dispose()
