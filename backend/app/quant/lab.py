"""
app/quant/lab.py
------------------
Orchestration for the Quant Lab: fetches the price history once and runs
every analysis module against it.

Everything here is derived from price series the platform already has, so
the only network cost is the bar fetch plus a weekly-cached factor file.
Each section is independently guarded — a factor-library outage costs the
factor panel, not the whole page.
"""

import logging
from datetime import date, timedelta

import pandas as pd

from app.core.config import get_settings
from app.ingestion.market_data import MarketDataService
from app.quant import factors as fac
from app.quant import mean_reversion as mr
from app.quant import risk as rk

logger = logging.getLogger("aureus.quant.lab")

# Default peer set for the correlation panel: liquid, sector-spanning
# names plus the index itself. Broad on purpose — a pairs candidate is
# only interesting if it is NOT in the same sector, since two names in one
# sector are correlated for a reason that offers no relative-value edge.
_DEFAULT_PEERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "JPM", "XOM", "JNJ", "WMT", "GLD"]

_LOOKBACK_DAYS = 365 * 3


def run_quant_lab(
    ticker: str,
    benchmark: str = "SPY",
    peers: list[str] | None = None,
    monte_carlo_horizon: int = 21,
) -> dict:
    """
    Full Quant Lab report for one ticker.

    Raises only if the target's own price history is unavailable — every
    other component degrades to an explicit null with a reason attached,
    so the UI can distinguish "not computed" from "computed as zero".
    """
    settings = get_settings()
    ticker = ticker.upper().strip()
    end = date.today()
    start = end - timedelta(days=_LOOKBACK_DAYS)

    svc = MarketDataService()
    bars = svc.fetch_bars(ticker, start, end, frequency="1d").bars
    prices = bars["close"]

    bench_prices: pd.Series | None = None
    try:
        bench_prices = svc.fetch_bars(benchmark, start, end, frequency="1d").bars["close"]
    except Exception as exc:
        logger.warning("Benchmark fetch failed",
                       extra={"benchmark": benchmark, "error": str(exc)})

    report: dict = {
        "ticker": ticker,
        "benchmark": benchmark,
        "start_date": str(start),
        "end_date": str(end),
        "observations": int(len(prices)),
        "current_price": round(float(prices.iloc[-1]), 2),
        "notes": [],
    }

    def _section(name: str, fn):
        try:
            return fn()
        except Exception as exc:
            logger.warning("Quant Lab section failed",
                           extra={"ticker": ticker, "section": name, "error": str(exc)})
            report["notes"].append(f"{name} could not be computed: {exc}")
            return None

    # ── Factor models ─────────────────────────────────────────────────
    report["factor_model_5"] = _section(
        "Fama-French 5-factor", lambda: fac.factor_exposures(prices, "ff5"))
    report["factor_model_3"] = _section(
        "Fama-French 3-factor", lambda: fac.factor_exposures(prices, "ff3"))
    report["rolling_factor_betas"] = _section(
        "Rolling factor betas", lambda: fac.rolling_factor_betas(prices)) or []
    if report["factor_model_5"] is None and report["factor_model_3"] is None:
        report["notes"].append(
            "Fama-French factor data was unavailable, so factor exposures and true alpha "
            "could not be estimated. The remaining panels are unaffected."
        )

    # ── Risk ──────────────────────────────────────────────────────────
    report["performance"] = _section("Risk-adjusted performance",
                                     lambda: rk.sharpe_sortino(prices))
    report["var_1d"] = _section(
        "1-day VaR",
        lambda: rk.value_at_risk(prices, settings.quant_var_confidence, 1))
    report["var_10d"] = _section(
        "10-day VaR",
        lambda: rk.value_at_risk(prices, settings.quant_var_confidence, 10))
    report["monte_carlo"] = _section("Monte Carlo", lambda: rk.monte_carlo(
        prices, horizon_days=monte_carlo_horizon,
        paths=settings.quant_monte_carlo_paths,
        confidence=settings.quant_var_confidence))
    report["max_drawdown"] = _section("Max drawdown", lambda: rk.max_drawdown(prices))

    if bench_prices is not None:
        report["beta_stability"] = _section(
            "Beta stability", lambda: rk.beta_stability(prices, bench_prices))
    else:
        report["beta_stability"] = None
        report["notes"].append(
            f"Benchmark ({benchmark}) history was unavailable, so beta stability could not "
            "be computed."
        )

    # ── Mean reversion ────────────────────────────────────────────────
    report["zscore"] = _section("Z-score", lambda: mr.zscore_signal(prices))
    report["half_life"] = _section("Mean-reversion half-life",
                                   lambda: mr.mean_reversion_half_life(prices))
    report["volatility_term_structure"] = _section(
        "Volatility term structure", lambda: mr.volatility_term_structure(prices))

    # ── Pairs ─────────────────────────────────────────────────────────
    candidate_list = [p for p in (peers or _DEFAULT_PEERS) if p.upper() != ticker]
    candidates: dict[str, pd.Series] = {}
    for p in candidate_list:
        try:
            candidates[p] = svc.fetch_bars(p, start, end, frequency="1d").bars["close"]
        except Exception:
            continue
    report["pairs"] = _section(
        "Pairs correlation",
        lambda: mr.pairs_correlation(prices, candidates)) or []
    if not candidates:
        report["notes"].append(
            "No peer price history was retrievable, so the correlation panel is empty."
        )

    logger.info("Quant Lab complete", extra={
        "ticker": ticker, "observations": len(prices),
        "sections_failed": len(report["notes"]),
    })
    return report
