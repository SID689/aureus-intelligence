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

from dataclasses import dataclass

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
}


def centre_and_scale(label: str) -> tuple[float, float]:
    """
    The (centre, sd) to standardise `label` against, with both shrunk
    toward the prior according to how many observations backed them.

    An unmeasured label falls back to the prior entirely, which makes
    adding a new sub-signal safe: it behaves exactly as it would have
    under the old arithmetic until someone re-runs the calibration.
    """
    st = _MEASURED.get(label)
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

RHO: dict[str, float] = {
    "technical":   _RHO_WITHIN_TECHNICAL,
    "fundamental": _RHO_WITHIN_FUNDAMENTAL,
    "sentiment":   _RHO_WITHIN_SENTIMENT,
    "ensemble":    _RHO_ACROSS_PILLARS,
}
