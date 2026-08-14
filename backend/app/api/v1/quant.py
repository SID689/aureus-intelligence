"""
app/api/v1/quant.py
---------------------
The Advanced Quant Lab API. Elite and Institutional tiers only.

GET /api/v1/quant/lab/{ticker}      full report (factors, risk, reversion, pairs)
GET /api/v1/quant/factors/{ticker}  factor exposures alone (cheaper)
GET /api/v1/quant/access            what the caller's tier permits

Tier enforcement is a real server-side check (app/core/tiers.py), not a
hidden nav link. Every gated route returns 402 with the caller's current
and required tier so the client can render an upgrade prompt rather than
a generic error.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.entitlements import (
    Entitlements, current_entitlements, require_feature, resolve_entitlements,
)

logger = logging.getLogger("aureus.api.quant")

router = APIRouter(prefix="/api/v1/quant", tags=["quant-lab"])

_REQUIRED_TIER = "elite"

DISCLAIMER = (
    "Statistical output only. Factor loadings, VaR, CVaR and simulated return "
    "distributions are estimates derived from historical data and carry model risk. "
    "They are not forecasts, not guarantees, and not investment advice. Value at Risk "
    "in particular describes a threshold, not a worst case — losses beyond it are "
    "possible and, in stressed markets, correlated across positions."
)


@router.get("/access")
def quant_access(user_id: Annotated[str, Query(min_length=1)]) -> dict:
    """
    Whether this user can use the Quant Lab.

    Deliberately NOT gated: the frontend calls it to decide between
    rendering the lab and rendering an upgrade prompt, so gating it would
    make the upgrade path itself unreachable for the users who need it.
    """
    ent = resolve_entitlements(user_id)
    return {
        "user_id": user_id,
        "tier": ent.tier,
        "display_name": ent.display_name,
        "has_access": ent.quant_lab_enabled,
        "required_tier": _REQUIRED_TIER,
        # Surfaced so the lab can show what this plan's run actually used,
        # rather than presenting Elite's 10k-path simulation as if it were
        # the same analysis Institutional receives.
        "history_years": ent.quant_history_years,
        "monte_carlo_paths": ent.quant_monte_carlo_paths,
        "custom_peers": ent.quant_custom_peers,
    }


@router.get("/lab/{ticker}")
def quant_lab(
    ticker: str,
    ent: Annotated[Entitlements, Depends(require_feature("quant_lab_enabled", "The Quant Lab"))],
    benchmark: str = Query(default="SPY", max_length=10),
    monte_carlo_horizon: int = Query(default=21, ge=1, le=252),
    peers: str | None = Query(default=None, description="Comma-separated tickers"),
) -> dict:
    """
    Full Quant Lab report.

    Runs inline rather than through Celery: the heavy step is the bar
    fetch, the factor file is cached weekly, and everything after that is
    numpy on a few thousand rows. Measured end-to-end well inside a
    request budget.
    """
    from app.ingestion.rate_limiter import FallbackExhaustedError
    from app.quant.lab import run_quant_lab

    ticker_clean = ticker.upper().strip()

    # Custom peer sets are an Institutional feature. A lower plan asking
    # for one falls back to the default basket rather than erroring — the
    # report is still fully valid, just not bespoke, and failing the whole
    # request over an optional refinement would be worse than ignoring it.
    peer_list = None
    if peers and ent.quant_custom_peers:
        peer_list = [p.strip().upper() for p in peers.split(",") if p.strip()][:12]

    try:
        report = run_quant_lab(
            ticker_clean, benchmark=benchmark.upper().strip(),
            peers=peer_list, monte_carlo_horizon=monte_carlo_horizon,
            history_years=ent.quant_history_years,
            monte_carlo_paths=ent.quant_monte_carlo_paths,
        )
    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=503,
            detail=(f"Market data unavailable for {ticker_clean}. "
                    f"Providers tried: {', '.join(exc.attempted_providers)}"),
        )
    except Exception as exc:
        logger.error("Quant Lab failed",
                     extra={"ticker": ticker_clean, "error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Quant Lab engine error")

    report["tier"] = ent.tier
    report["plan"] = {
        "display_name": ent.display_name,
        "history_years": ent.quant_history_years,
        "monte_carlo_paths": ent.quant_monte_carlo_paths,
        "custom_peers": ent.quant_custom_peers,
        "custom_peers_ignored": bool(peers) and not ent.quant_custom_peers,
    }
    report["disclaimer"] = DISCLAIMER
    return report


@router.get("/factors/{ticker}")
def quant_factors(
    ticker: str,
    ent: Annotated[Entitlements, Depends(require_feature("quant_lab_enabled", "The Quant Lab"))],
    model: str = Query(default="ff5", pattern="^(ff3|ff5)$"),
) -> dict:
    """Factor exposures alone — no Monte Carlo, no peer fetches."""
    from datetime import date, timedelta

    from app.ingestion.market_data import MarketDataService
    from app.quant.factors import factor_exposures, rolling_factor_betas

    ticker_clean = ticker.upper().strip()
    end = date.today()
    start = end - timedelta(days=365 * (ent.quant_history_years or 3))

    try:
        bars = MarketDataService().fetch_bars(ticker_clean, start, end, frequency="1d").bars
        exposures = factor_exposures(bars["close"], model)
        rolling = rolling_factor_betas(bars["close"])
    except Exception as exc:
        logger.error("Factor exposure failed",
                     extra={"ticker": ticker_clean, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Factor model error")

    if exposures is None:
        raise HTTPException(
            status_code=503,
            detail=("Fama-French factor data is unavailable or the price history does not "
                    "overlap it sufficiently to estimate exposures."),
        )

    return {
        "ticker": ticker_clean, "tier": ent.tier,
        "exposures": exposures, "rolling_betas": rolling,
        "disclaimer": DISCLAIMER,
    }
