"""
app/quant/mean_reversion.py
-----------------------------
Statistical deviation signals: z-score versus a moving mean, pairs
correlation for relative-value work, and realised-volatility term
structure.

=====================================================================
WHAT A Z-SCORE IS AND IS NOT
=====================================================================
The z-score here answers one narrow question: how unusual is today's
price relative to its own recent distribution, measured in standard
deviations of that distribution?

    z = (price - rolling mean) / rolling standard deviation

|z| > 2 means the price sits outside roughly 95% of its recent range.
That is a statement about the DISTRIBUTION, not a forecast. A stock can
be at z = -3 because it is oversold, or because the business has
permanently deteriorated and the mean has not caught up yet. The second
case is where naive mean-reversion strategies lose money, and no z-score
can distinguish them — which is why this module reports a HALF-LIFE
alongside it.

=====================================================================
HALF-LIFE: THE PART THAT MAKES THE Z-SCORE ACTIONABLE
=====================================================================
Estimated from an Ornstein-Uhlenbeck fit — regress the daily change in
price on the prior level:

    Δp(t) = α + β·p(t-1) + ε

A negative β means deviations pull back toward the mean, and the
half-life of that pull is -ln(2)/ln(1+β). A short half-life (days) means
the series genuinely mean-reverts and a z-score has predictive content. A
long or undefined half-life (β ≥ 0) means the series is trending or a
random walk, where trading a z-score is trading noise. Reporting the
z-score without it would be presenting the seductive half of the analysis
and hiding the half that says whether to believe it.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("aureus.quant.mean_reversion")

_TRADING_DAYS = 252


def zscore_signal(prices: pd.Series, window: int = 60) -> dict | None:
    """Current price expressed in standard deviations from its rolling mean."""
    p = prices.dropna()
    if len(p) < window + 5:
        return None

    rolling_mean = p.rolling(window).mean()
    rolling_std = p.rolling(window).std(ddof=1)
    z = (p - rolling_mean) / rolling_std
    z = z.replace([np.inf, -np.inf], np.nan).dropna()
    if z.empty:
        return None

    current = float(z.iloc[-1])
    if current <= -2.0:
        interp = "Statistically stretched to the downside — outside ~95% of its recent range."
    elif current >= 2.0:
        interp = "Statistically stretched to the upside — outside ~95% of its recent range."
    elif abs(current) >= 1.0:
        interp = "Moderately displaced from its recent mean, but inside normal variation."
    else:
        interp = "Trading close to its recent mean; no statistical displacement."

    return {
        "window_days": window,
        "z_score": round(current, 3),
        "rolling_mean": round(float(rolling_mean.iloc[-1]), 2),
        "rolling_std": round(float(rolling_std.iloc[-1]), 2),
        "current_price": round(float(p.iloc[-1]), 2),
        "percentile_in_window": round(
            float((p.tail(window) <= p.iloc[-1]).mean() * 100), 1
        ),
        "interpretation": interp,
        "series": [
            {"date": str(pd.Timestamp(d).date()), "z": round(float(v), 3)}
            for d, v in z.tail(180).items()
        ],
    }


def mean_reversion_half_life(prices: pd.Series) -> dict:
    """
    Ornstein-Uhlenbeck half-life of mean reversion.

    Returns half_life_days=None when β ≥ 0, which means the series is
    trending or random-walking and there is no reversion to time. That is
    a genuine finding, not a failure — see the module docstring.
    """
    p = prices.dropna()
    if len(p) < 60:
        return {"half_life_days": None, "reverting": False,
                "note": "Not enough history to estimate mean reversion."}

    lagged = p.shift(1).dropna()
    delta = (p - p.shift(1)).dropna()
    n = min(len(lagged), len(delta))
    x, y = lagged.values[-n:], delta.values[-n:]

    X = np.column_stack([np.ones(n), x])
    try:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return {"half_life_days": None, "reverting": False,
                "note": "Regression did not converge."}

    beta = float(coef[1])
    if beta >= 0 or (1 + beta) <= 0:
        return {
            "half_life_days": None, "beta": round(beta, 6), "reverting": False,
            "note": ("No mean reversion detected — the series trends or random-walks over this "
                     "sample, so a z-score here carries no reversion signal."),
        }

    half_life = -np.log(2) / np.log(1 + beta)
    if not np.isfinite(half_life) or half_life <= 0 or half_life > 500:
        return {
            "half_life_days": None, "beta": round(beta, 6), "reverting": False,
            "note": "Estimated reversion is too slow to be usable.",
        }

    return {
        "half_life_days": round(float(half_life), 1),
        "beta": round(beta, 6),
        "reverting": True,
        "note": (f"Deviations from the mean decay by half in roughly {half_life:.0f} trading days, "
                 f"so a displacement has a measurable tendency to close."),
    }


def pairs_correlation(target: pd.Series, candidates: dict[str, pd.Series],
                      min_overlap: int = 100) -> list[dict]:
    """
    Correlation of daily RETURNS against candidate tickers, for
    relative-value and hedge construction.

    Returns, never prices. Two trending price series correlate near 1.0
    almost regardless of relationship — that is the classic spurious
    regression, and it would rank every large-cap as a perfect pair.
    Return correlation measures co-movement, which is what a hedge or a
    spread trade actually depends on.
    """
    def _naive(s: pd.Series) -> pd.Series:
        """
        Normalise an index to tz-naive dates.

        Provider bars arrive tz-aware in UTC (index name "timestamp");
        anything derived from them must be aligned on the same basis. The
        spread z-score below silently returned None for every pair until
        this was applied to the PRICE series too — reindexing a tz-aware
        series onto a tz-naive index matches nothing and yields all-NaN,
        which then failed the length check rather than raising.
        """
        out = s.copy()
        idx = pd.to_datetime(out.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        out.index = idx.normalize()
        return out[~out.index.duplicated(keep="last")]

    target_px = _naive(target)
    t = _naive(target.pct_change().dropna())

    out: list[dict] = []
    for name, series in candidates.items():
        cand_px = _naive(series)
        c = _naive(series.pct_change().dropna())
        joined = pd.concat([t.rename("a"), c.rename("b")], axis=1, join="inner").dropna()
        if len(joined) < min_overlap:
            continue
        corr = float(joined["a"].corr(joined["b"]))
        if not np.isfinite(corr):
            continue

        # Spread z-score on the log price ratio: the standard construction
        # for a pairs trade, and the thing you would actually trade.
        spread_z = None
        try:
            pa = target_px.reindex(joined.index).ffill()
            pb = cand_px.reindex(joined.index).ffill()
            ratio = np.log(pa / pb).dropna()
            if len(ratio) >= 60:
                sd = float(ratio.tail(60).std(ddof=1))
                if sd > 0:
                    spread_z = round(
                        float((ratio.iloc[-1] - ratio.tail(60).mean()) / sd), 3
                    )
        except Exception:
            spread_z = None

        out.append({
            "ticker": name,
            "return_correlation": round(corr, 4),
            "observations": len(joined),
            "spread_z_score": spread_z,
        })

    out.sort(key=lambda r: abs(r["return_correlation"]), reverse=True)
    return out


def volatility_term_structure(prices: pd.Series) -> dict:
    """
    Realised volatility over several lookbacks.

    Short-window vol above long-window vol means volatility is currently
    ELEVATED relative to its own norm — a regime signal that options desks
    read as the realised analogue of an inverted vol surface.

    Named "skew" in the brief; this is deliberately the realised term
    structure instead, because true volatility skew is a property of the
    options surface across strikes, and no free source provides an options
    chain. Reporting a realised term structure and saying so is honest;
    labelling it "skew" would not be.
    """
    r = prices.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    out: dict = {"windows": {}}
    for w in (10, 21, 63, 126, 252):
        if len(r) >= w:
            out["windows"][f"{w}d"] = round(
                float(r.tail(w).std(ddof=1) * np.sqrt(_TRADING_DAYS)), 4
            )

    short = out["windows"].get("21d")
    long = out["windows"].get("252d")
    if short and long and long > 0:
        ratio = short / long
        out["short_vs_long_ratio"] = round(ratio, 3)
        if ratio >= 1.3:
            out["regime"] = "Elevated"
            out["note"] = ("Recent volatility runs well above the one-year norm — the market is "
                           "repricing something, and position sizes calibrated to the calm period "
                           "are now larger in risk terms than intended.")
        elif ratio <= 0.75:
            out["regime"] = "Compressed"
            out["note"] = ("Recent volatility sits well below the one-year norm. Compressed "
                           "volatility tends not to persist indefinitely.")
        else:
            out["regime"] = "Normal"
            out["note"] = "Recent volatility is in line with the one-year norm."
    return out
