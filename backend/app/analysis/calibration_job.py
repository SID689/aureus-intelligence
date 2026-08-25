"""
app/analysis/calibration_job.py
---------------------------------
Re-measure every sub-signal's centre and dispersion, and persist them.

WHY THIS RUNS ON A SCHEDULE
The aggregator standardises each 0-100 sub-signal against its measured
behaviour before pooling it (see aggregation.py and calibration.py).
Those statistics are cross-sectional: they describe how a signal behaves
across a universe at a point in time, and they drift. A gross-margin
centre measured in one regime quietly mis-scores every company once the
regime changes, and nothing in the system would complain.

Left as literals in a source file the numbers are only as fresh as the
last time someone remembered. This job re-measures them, and
calibration.py prefers whichever measurement is newer.

WHAT IT DELIBERATELY DOES NOT DO
It does not touch rho. How correlated the signals are decides how much
pooling them should raise confidence, and measuring it correctly needs
judgement that a cron job does not have: the first attempt measured
correlation in score space and got ~0.0, an artifact of clipped scorers,
where the raw-metric answer is ~0.35. Automating that would
re-introduce the error every month and inflate confidence across the
platform. rho stays a reviewed constant.
"""

import logging
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.analysis.calibration_job")

# Spans sectors, market caps and momentum regimes on purpose. A universe
# drawn from megacap tech would report that every signal is bullish and
# barely moves, and the centres would inherit that.
UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "INTC", "MU", "ORCL",
    "JPM", "BAC", "GS", "V", "AXP",
    "JNJ", "PFE", "MRK", "LLY", "UNH",
    "XOM", "CVX", "COP",
    "CAT", "DE", "HON", "GE",
    "WMT", "COST", "TGT", "NKE", "SBUX",
    "T", "VZ", "CMCSA",
    "F", "GM", "DAL",
    "TSLA", "COIN", "PLTR", "SHOP",
]

# 730 days, not 365. Some signals need more than a year of history to
# compute at all — 12-1 momentum silently never fires at a 365-day
# lookback — and this is the window the backtester replays.
WINDOW_DAYS = 730

# Below this many observations a statistic is not worth storing; the
# loader would reject it anyway.
_MIN_OBSERVATIONS = 8


@dataclass
class CalibrationRun:
    rows_written: int
    signals_measured: int
    universe_size: int
    failures: list[str]


def measure(
    universe: list[str] | None = None,
    window_days: int = WINDOW_DAYS,
) -> tuple[dict[str, tuple[str, list[float]]], list[str]]:
    """
    Collect every sub-signal score across the universe.

    Returns (label -> (group, [scores]), failures). Never raises on a
    single ticker: one delisted symbol or one provider timeout must not
    cost the whole run, because a partial refresh still beats a stale one.
    """
    # Imported here rather than at module scope: this module is imported
    # by the Celery task registry at worker boot, and the analysis stack
    # pulls in pandas, numpy and every provider client.
    from app.analysis.fundamental import run_fundamental_analysis
    from app.analysis.quantitative import run_quantitative_analysis
    from app.analysis.sector_peers import compare_to_sector
    from app.analysis.sentiment import run_sentiment_analysis
    from app.analysis.technical import run_technical_analysis
    from app.ingestion.fundamentals import FundamentalDataService
    from app.ingestion.market_data import MarketDataService

    tickers = universe or UNIVERSE
    market_svc, fund_svc = MarketDataService(), FundamentalDataService()
    end = date.today()
    start = end - timedelta(days=window_days)

    collected: dict[str, tuple[str, list[float]]] = {}
    failures: list[str] = []

    def add(group: str, label: str, score: float) -> None:
        collected.setdefault(label, (group, []))[1].append(float(score))

    try:
        spy_bars = market_svc.fetch_bars("SPY", start, end, frequency="1d").bars
    except Exception as exc:  # noqa: BLE001
        logger.warning("Benchmark fetch failed — alpha will not be recalibrated", extra={"error": str(exc)})
        spy_bars = None

    for ticker in tickers:
        bars = None
        tech = None
        try:
            bars = market_svc.fetch_bars(ticker, start, end, frequency="1d").bars
            tech = run_technical_analysis(ticker, bars)
            for sig in tech.signal_breakdown:
                add("technical", sig["label"], sig["score"])
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{ticker}:technical:{exc}")

        if bars is not None:
            try:
                quant = run_quantitative_analysis(
                    ticker, bars, spy_bars=spy_bars,
                    rsi_value=getattr(tech, "rsi_14", None),
                )
                for sig in quant.signal_breakdown:
                    add("quantitative", sig["label"], sig["score"])
                # The ML leg scores but never appends a labelled entry.
                add("quantitative", "ML Forward-Return Signal", quant.ml_signal_score)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{ticker}:quantitative:{exc}")

        try:
            fd = fund_svc.fetch_fundamentals(ticker)
            sector_cmp = compare_to_sector(ticker, fd.sector, {
                "pe_ratio": fd.pe_ratio, "price_to_sales": fd.price_to_sales, "pb_ratio": fd.pb_ratio,
                "gross_margin": (fd.gross_margin * 100) if fd.gross_margin is not None else None,
                "operating_margin": (fd.operating_margin * 100) if fd.operating_margin is not None else None,
                "return_on_equity": (fd.return_on_equity * 100) if fd.return_on_equity is not None else None,
                "roic": (fd.roic * 100) if fd.roic is not None else None,
                "debt_to_equity": fd.debt_to_equity,
            })
            fund = run_fundamental_analysis(ticker, fd, "medium_term", sector_comparison=sector_cmp)
            for sig in fund.signal_breakdown:
                # The CAGR label carries a variable year count; normalise
                # it so four years and five years are one distribution.
                label = "4-Year Revenue CAGR" if "Revenue CAGR" in sig["label"] else sig["label"]
                add("fundamental", label, sig["score"])
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{ticker}:fundamental:{exc}")

        try:
            sent = run_sentiment_analysis(ticker)
            for sig in sent.signal_breakdown:
                add("sentiment", sig["label"], sig["score"])
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{ticker}:sentiment:{exc}")

    if failures:
        logger.info("Calibration measurement had partial failures",
                    extra={"count": len(failures), "sample": failures[:5]})
    return collected, failures


def persist(
    collected: dict[str, tuple[str, list[float]]],
    window_days: int,
    universe_size: int,
    failures: list[str] | None = None,
) -> CalibrationRun:
    """
    Upsert one row per signal that cleared the observation floor.

    Written in a single transaction: a half-applied calibration would
    leave some signals on the new regime and some on the old, which is
    worse than either.
    """
    rows = []
    for label, (group, scores) in sorted(collected.items()):
        if len(scores) < _MIN_OBSERVATIONS:
            logger.info("Signal skipped — too few observations",
                        extra={"label": label, "n": len(scores)})
            continue
        sd = statistics.pstdev(scores)
        if sd <= 0:
            logger.info("Signal skipped — no dispersion", extra={"label": label})
            continue
        rows.append({
            "label": label, "signal_group": group, "n": len(scores),
            "mean": round(statistics.fmean(scores), 4), "sd": round(sd, 4),
            "universe_size": universe_size, "window_days": window_days,
        })

    if not rows:
        logger.error("Calibration produced no usable rows — leaving existing values in place")
        return CalibrationRun(0, len(collected), universe_size, ["no usable rows"])

    engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=1)
    try:
        with engine.begin() as conn:
            for r in rows:
                conn.execute(text("""
                    INSERT INTO signal_calibration
                        (label, signal_group, n, mean, sd, universe_size, window_days, measured_at)
                    VALUES
                        (:label, :signal_group, :n, :mean, :sd, :universe_size, :window_days, now())
                    ON CONFLICT (label) DO UPDATE SET
                        signal_group  = EXCLUDED.signal_group,
                        n             = EXCLUDED.n,
                        mean          = EXCLUDED.mean,
                        sd            = EXCLUDED.sd,
                        universe_size = EXCLUDED.universe_size,
                        window_days   = EXCLUDED.window_days,
                        measured_at   = now()
                """), r)
    finally:
        engine.dispose()

    # Drop the in-process cache so the new numbers take effect without a
    # restart. Other workers pick them up when their own TTL expires.
    from app.analysis.calibration import invalidate_cache
    invalidate_cache()

    logger.info("Signal calibration refreshed",
                extra={"rows": len(rows), "window_days": window_days})
    return CalibrationRun(len(rows), len(collected), universe_size, failures or [])


def run(universe: list[str] | None = None, window_days: int = WINDOW_DAYS) -> CalibrationRun:
    tickers = universe or UNIVERSE
    collected, failures = measure(tickers, window_days)
    return persist(collected, window_days, len(tickers), failures)
