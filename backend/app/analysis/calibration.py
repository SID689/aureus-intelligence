"""
app/analysis/calibration.py
-----------------------------
Measured behaviour of every sub-signal, so the aggregator can convert an
ad-hoc 0-100 score into a standardised z-score.

WHY THIS IS NECESSARY
Each scorer in fundamental.py / technical.py / sentiment.py maps a raw
indicator onto 0-100 using a hand-drawn curve, and those curves were
never checked against real data. Measuring them across a 40-name
universe showed two problems that quietly distorted every analysis:

  1. "50" is not neutral for most signals. Gross Margin averages 89.7
     across large caps, Return on Equity 78.1, Revenue Growth 74.7 —
     while Current Ratio averages 23.6 and Valuation vs Sector 32.3. A
     stock scoring 70 on gross margin is BELOW average, but the old
     aggregator read it as "20 points bullish". The fundamental pillar
     inherited a permanent bullish tilt (measured mean 67.8) purely from
     this.

  2. Signals differ enormously in how much they move. MA Alignment has
     sd 28.2; MACD has sd 9.9. Averaging them raw lets the widest scorer
     dominate for no reason other than the shape of its curve.

Centring on the measured mean and dividing by the measured sd fixes
both: every signal then contributes in units of "how unusual is this
reading", which is the only basis on which independent evidence can
legitimately be combined.

PROVENANCE
Measured 2026-08-24 over a 40-name universe spanning sectors, market
caps and momentum regimes (see scripts/calibrate_signals.py, which
regenerates these numbers and prints them in this exact form).

These are cross-sectional statistics, not eternal truths. Re-run the
calibration if the scorers change, and periodically regardless — a
market-wide regime shift moves the centres. The shrinkage below limits
the damage from a stale or thin estimate in the meantime.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("aureus.analysis.calibration")

# Prior for a signal we have not measured, or have barely measured.
# sd 18 is roughly the median measured dispersion; centre 50 is the
# scorers' own stated neutral.
_PRIOR_MEAN = 50.0
_PRIOR_SD = 18.0

# Shrinkage strength, in pseudo-observations. A signal measured on 40
# names keeps ~80% of its measured statistics; one measured on 8 keeps
# ~44%. This is what stops an 8-observation sd from being taken at face
# value, without discarding the information it does carry.
_SHRINK_K = 10.0

# Floor on the sd actually used. A signal that genuinely never moves
# would otherwise divide by ~0 and dominate the composite on rounding
# noise alone.
_MIN_SD = 4.0


@dataclass(frozen=True)
class SignalStats:
    n: int
    mean: float
    sd: float


# Measured 2026-08-24. Keys are the `label` each pillar puts in its
# signal_breakdown, so lookup is by the same string the UI displays.
_MEASURED: dict[str, SignalStats] = {
    # ── Technical ──────────────────────────────────────────────────
    "Bollinger %B":               SignalStats(40, 46.28, 20.71),
    "MA Alignment (20/50/200)":   SignalStats(40, 69.38, 28.22),
    "MACD":                       SignalStats(40, 49.59,  9.90),
    "On-Balance Volume":          SignalStats(40, 56.00, 13.75),
    "RSI (14)":                   SignalStats(40, 44.32, 16.72),
    "Support/Resistance":         SignalStats(40, 38.31, 15.42),
    "VWAP Position":              SignalStats(40, 51.50,  9.89),
    "Volume Trend":               SignalStats(11, 59.92, 31.06),

    # ── Fundamental ────────────────────────────────────────────────
    "4-Year Revenue CAGR":        SignalStats(36, 75.76, 21.78),
    "Current Ratio":              SignalStats(38, 23.63, 32.48),
    "Debt-to-Equity":             SignalStats(32, 74.76, 22.96),
    "Earnings Consistency":       SignalStats(8,  74.38,  8.45),
    "Gross Margin":               SignalStats(37, 89.65, 19.04),
    "Operating Margin":           SignalStats(40, 76.13, 26.75),
    "Return on Equity":           SignalStats(40, 78.07, 30.21),
    "Revenue Growth (YoY)":       SignalStats(40, 74.74, 20.13),
    "Valuation vs Sector":        SignalStats(12, 32.33, 19.93),

    # ── Sentiment ──────────────────────────────────────────────────
    "News Sentiment":             SignalStats(38, 55.32,  6.29),
    "SEC Filing Tone":            SignalStats(35, 53.03,  7.89),
    "Social Sentiment":           SignalStats(40, 61.78,  9.66),

    # ── Quantitative (backtest leg only; see backtesting/engine.py) ─
    # Measured over a 730-day window rather than 365, because that is
    # the window the backtester actually replays and because 12-1
    # momentum needs more than a year of history to compute at all —
    # at a 365-day lookback it silently never fires.
    #
    # Two of these are badly centred in the same way the fundamental
    # scorers were: 12-1 Momentum averages 70.3 and Alpha vs S&P 500
    # averages 71.7, so a typical stock was scoring "clearly bullish" on
    # both. That is what tilted backtest signals 15 BUY to 1 SELL.
    "12-1 Momentum":              SignalStats(40, 70.34, 31.77),
    "30-Day Volatility":          SignalStats(40, 44.57, 20.82),
    "Alpha vs S&P 500":           SignalStats(40, 71.72, 29.38),
    "ML Forward-Return Signal":   SignalStats(40, 57.61, 13.66),
}


# ── Where the numbers come from at runtime ──────────────────────────────
#
# The literals above are a FALLBACK, not the source of truth. A scheduled
# job (app.workers.analysis_tasks.recalibrate_signals) re-measures the
# universe and writes to the signal_calibration table; this loader
# prefers those rows whenever they are newer than the literals.
#
# Preferring "newer" rather than "database always wins" matters: if the
# job has not run in a year but someone re-measured and updated the
# literals last week, the literals are the better estimate and should
# win. Whichever measurement is more recent is used, and staleness is
# logged either way.

_BAKED_IN_MEASURED_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)

# Beyond this, warn. Cross-sectional centres drift with the market
# regime; a centre measured two quarters ago is describing a different
# market from the one being scored.
_STALE_AFTER_DAYS = 120

# Cache TTL. These change monthly at most, and the loader runs on every
# analysis, so re-reading the table per request is pure waste.
_CACHE_TTL_SECONDS = 3600

_cache: dict[str, SignalStats] | None = None
_cache_measured_at: datetime | None = None
_cache_loaded_at: float = 0.0


def _row_is_sane(label: str, n: int, mean: float, sd: float) -> bool:
    """
    Reject a row rather than let a bad measurement poison every score
    that uses it. A scorer that broke mid-run, or a universe that
    returned two usable tickers, can produce statistics that are
    arithmetically valid and analytically worthless.
    """
    if n < 8:
        logger.warning("Calibration row rejected: too few observations", extra={"label": label, "n": n})
        return False
    if not (0.0 <= mean <= 100.0):
        logger.warning("Calibration row rejected: mean out of range", extra={"label": label, "mean": mean})
        return False
    if not (_MIN_SD <= sd <= 60.0):
        # sd above 60 on a 0-100 scale means the signal is bimodal at the
        # extremes, which no scorer here should produce.
        logger.warning("Calibration row rejected: implausible sd", extra={"label": label, "sd": sd})
        return False
    return True


def _load_measured() -> tuple[dict[str, SignalStats], datetime]:
    """
    Merge database rows over the baked-in literals, newest wins.

    Never raises. A database that is down, missing the table, or full of
    rejected rows degrades to the literals — which is the whole point of
    keeping them.
    """
    global _cache, _cache_measured_at, _cache_loaded_at

    now = time.monotonic()
    if _cache is not None and (now - _cache_loaded_at) < _CACHE_TTL_SECONDS:
        return _cache, _cache_measured_at or _BAKED_IN_MEASURED_AT

    merged = dict(_MEASURED)
    newest = _BAKED_IN_MEASURED_AT

    try:
        from sqlalchemy import create_engine, text
        from app.core.config import get_settings

        engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=1)
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT label, n, mean, sd, measured_at FROM signal_calibration"
            )).fetchall()
        engine.dispose()

        applied = 0
        for label, n, mean, sd, measured_at in rows:
            if not _row_is_sane(label, int(n), float(mean), float(sd)):
                continue
            if measured_at.tzinfo is None:
                measured_at = measured_at.replace(tzinfo=timezone.utc)
            if measured_at <= _BAKED_IN_MEASURED_AT:
                # The literals are at least as fresh; keep them.
                continue
            merged[label] = SignalStats(int(n), float(mean), float(sd))
            newest = max(newest, measured_at)
            applied += 1

        if applied:
            logger.info("Signal calibration loaded from database",
                        extra={"rows_applied": applied, "measured_at": newest.isoformat()})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Signal calibration table unavailable, using baked-in literals",
                       extra={"error": str(exc)})

    age_days = (datetime.now(timezone.utc) - newest).days
    if age_days > _STALE_AFTER_DAYS:
        logger.warning(
            "Signal calibration is stale: centres may no longer describe the current market",
            extra={"age_days": age_days, "measured_at": newest.isoformat(),
                   "remedy": "run app.workers.analysis_tasks.recalibrate_signals"},
        )

    _cache, _cache_measured_at, _cache_loaded_at = merged, newest, now
    return merged, newest


def calibration_status() -> dict:
    """Provenance for health checks and the admin surface."""
    stats, measured_at = _load_measured()
    age = (datetime.now(timezone.utc) - measured_at).days
    return {
        "signals": len(stats),
        "measured_at": measured_at.isoformat(),
        "age_days": age,
        "stale": age > _STALE_AFTER_DAYS,
        "stale_after_days": _STALE_AFTER_DAYS,
    }


def invalidate_cache() -> None:
    """Called by the refresh job so a new measurement takes effect at once."""
    global _cache, _cache_loaded_at
    _cache, _cache_loaded_at = None, 0.0


def centre_and_scale(label: str) -> tuple[float, float]:
    """
    The (centre, sd) to standardise `label` against, with both shrunk
    toward the prior according to how many observations backed them.

    An unmeasured label falls back to the prior entirely, which makes
    adding a new sub-signal safe: it behaves exactly as it would have
    under the old arithmetic until someone re-runs the calibration.
    """
    stats, _ = _load_measured()
    st = stats.get(label)
    if st is None:
        return _PRIOR_MEAN, _PRIOR_SD

    w = st.n / (st.n + _SHRINK_K)
    centre = w * st.mean + (1.0 - w) * _PRIOR_MEAN
    sd = w * st.sd + (1.0 - w) * _PRIOR_SD
    return centre, max(_MIN_SD, sd)


# ── Correlation between signals ────────────────────────────────────────
#
# How redundant the evidence is decides how much combining it should
# raise confidence, so this number does more work than any other in the
# system. Getting it wrong in either direction is a real failure:
# too high and the engine cannot form a view, too low and it manufactures
# certainty it has not earned.
#
# FIRST MEASUREMENT, AND WHY IT WAS WRONG
# Mean pairwise correlation of the 0-100 SCORES came back near zero:
#
#     within technical    -0.022
#     within fundamental  +0.069
#     within sentiment    -0.053
#     across pillars      +0.077
#
# Taken at face value that says the signals are independent. They are
# not. Correlation between two variables is attenuated when both are
# clipped at a bound, and several of these scorers saturate hard —
# Gross Margin averages 89.7 against a ceiling of 100, Return on Equity
# 78.1. Measuring score-space correlation was largely measuring the
# clipping.
#
# SECOND MEASUREMENT, ON THE RAW METRICS
# Correlating the underlying financials instead of their scores, over
# the same universe:
#
#     return_on_equity  x roic                +0.886
#     operating_margin  x roic                +0.741
#     operating_margin  x revenue_growth_yoy  +0.679
#     gross_margin      x operating_margin    +0.646
#     operating_margin  x return_on_equity    +0.566
#     revenue_growth    x current_ratio       +0.519
#     ...
#     mean |r| over 21 raw pairs              +0.348
#
# ROE and ROIC at 0.886 are very nearly the same measurement wearing two
# names. The profitability metrics form one tight cluster. Treating them
# as independent evidence would triple-count a single fact about the
# business.
#
# WHAT IS USED, AND WHY
# Fundamental sits above the raw mean because a flat average understates
# a tight cluster: five of the nine metrics load on profitability.
#
# Technical is lower on purpose, and this is a genuine property rather
# than an allowance. The technical scorers deliberately mix
# mean-reversion (RSI and %B score oversold as bullish) with
# trend-following (MA alignment scores an uptrend as bullish). Those two
# families disagree by construction, so the pillar carries real internal
# diversification — while remaining redundant WITHIN each family.
#
# Sentiment's three streams read different sources but track one public
# narrative. Across pillars is lowest: fundamentals, price and narrative
# are genuinely different lenses, though all three point at one company.
_RHO_WITHIN_TECHNICAL = 0.30
_RHO_WITHIN_FUNDAMENTAL = 0.40
_RHO_WITHIN_SENTIMENT = 0.30
_RHO_ACROSS_PILLARS = 0.20

# The quantitative leg exists only inside the backtester. Its signals are
# volatility, alpha against SPY, 12-1 momentum and a ridge-regression
# forward-return estimate — every one of them a function of the same
# price series, so internal redundancy is high.
_RHO_WITHIN_QUANTITATIVE = 0.40

# Technical against quantitative, the backtest's two legs. Measured at
# r = +0.406 on the pillar scores; set above that because both legs are
# pure price derivatives (12-1 momentum and MA alignment are two ways of
# asking the same question) and because score-space attenuation applies
# here as everywhere else.
_RHO_BACKTEST_PILLARS = 0.50

RHO: dict[str, float] = {
    "technical":    _RHO_WITHIN_TECHNICAL,
    "fundamental":  _RHO_WITHIN_FUNDAMENTAL,
    "sentiment":    _RHO_WITHIN_SENTIMENT,
    "ensemble":     _RHO_ACROSS_PILLARS,
    "quantitative": _RHO_WITHIN_QUANTITATIVE,
    "backtest":     _RHO_BACKTEST_PILLARS,
}
