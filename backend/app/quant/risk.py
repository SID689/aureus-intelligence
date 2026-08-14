"""
app/quant/risk.py
-------------------
Distributional risk: Monte Carlo return paths, Value at Risk, Conditional
VaR, Sharpe/Sortino, and beta stability.

=====================================================================
WHY BOTH HISTORICAL AND MONTE CARLO VaR
=====================================================================
VaR at 95% is the loss threshold that a bad-but-not-extreme day exceeds
one time in twenty. There are two honest ways to estimate it and they
disagree in an informative way, so both are reported:

  HISTORICAL   the empirical 5th percentile of realised returns. Makes no
               distributional assumption, so it captures the fat tails and
               skew that actually exist. Limited to what happened in the
               sample — it cannot produce a loss worse than the worst day
               observed.

  MONTE CARLO  simulated from a bootstrap of the same returns. Because it
               resamples with replacement over multi-day horizons, it can
               produce sequences worse than any single historical path.

The simulation BOOTSTRAPS rather than drawing from a fitted normal. Equity
returns are decisively not normal — they are fat-tailed and negatively
skewed, and a Gaussian Monte Carlo understates tail risk by exactly the
amount that matters. Resampling actual returns keeps the real shape.

=====================================================================
WHY CVaR IS REPORTED NEXT TO VaR
=====================================================================
VaR says how bad a 1-in-20 day is. It says nothing about the nineteenth
of those — the distribution beyond the threshold could be mild or
catastrophic and VaR reads identically. CVaR (expected shortfall) is the
average loss GIVEN that the threshold was breached, which is the number
that describes what actually happens in the tail.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("aureus.quant.risk")

_TRADING_DAYS = 252
_MIN_RETURNS = 60


def _clean_returns(prices: pd.Series) -> np.ndarray:
    r = prices.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return r.values.astype(float)


def sharpe_sortino(prices: pd.Series, risk_free_rate: float = 0.05) -> dict:
    """
    Both ratios, because they disagree in a way that matters.

    Sharpe divides excess return by TOTAL volatility, penalising upside
    and downside identically — which is wrong for anyone who only
    dislikes one of them. Sortino divides by downside deviation only. A
    strategy with violent upside and calm downside is punished by Sharpe
    and rewarded by Sortino; the gap between them is itself a description
    of the return shape.
    """
    r = _clean_returns(prices)
    if len(r) < _MIN_RETURNS:
        return {"sharpe_ratio": None, "sortino_ratio": None,
                "annualised_return": None, "annualised_volatility": None}

    daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS) - 1
    excess = r - daily_rf

    ann_return = (1 + r.mean()) ** _TRADING_DAYS - 1
    ann_vol = r.std(ddof=1) * np.sqrt(_TRADING_DAYS)

    sd = excess.std(ddof=1)
    sharpe = float(excess.mean() / sd * np.sqrt(_TRADING_DAYS)) if sd > 0 else None

    downside = excess[excess < 0]
    dd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    sortino = float(excess.mean() / dd * np.sqrt(_TRADING_DAYS)) if dd > 0 else None

    return {
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "sortino_ratio": round(sortino, 3) if sortino is not None else None,
        "annualised_return": round(float(ann_return), 4),
        "annualised_volatility": round(float(ann_vol), 4),
    }


def value_at_risk(prices: pd.Series, confidence: float = 0.95,
                  horizon_days: int = 1) -> dict:
    """
    Historical VaR and CVaR at the given confidence, for a holding period.

    Multi-day horizons are computed from OVERLAPPING realised windows
    rather than by scaling the 1-day figure by sqrt(t). The square-root
    rule assumes returns are independent across days; they are not —
    volatility clusters, and drawdowns string bad days together, which is
    precisely the behaviour a multi-day risk estimate needs to capture.
    """
    r = _clean_returns(prices)
    if len(r) < _MIN_RETURNS:
        return {"var_pct": None, "cvar_pct": None, "confidence": confidence,
                "horizon_days": horizon_days, "observations": len(r)}

    if horizon_days > 1:
        series = pd.Series(r)
        window = series.rolling(horizon_days).apply(lambda w: np.prod(1 + w) - 1, raw=True)
        sample = window.dropna().values
    else:
        sample = r

    if len(sample) < 20:
        return {"var_pct": None, "cvar_pct": None, "confidence": confidence,
                "horizon_days": horizon_days, "observations": len(sample)}

    q = np.percentile(sample, (1 - confidence) * 100)
    tail = sample[sample <= q]
    cvar = float(tail.mean()) if len(tail) else float(q)

    return {
        # Reported as positive magnitudes of LOSS, which is how a risk
        # figure is read: "VaR 2.4%" means a 2.4% loss, not a -2.4% return.
        "var_pct": round(abs(float(q)), 4),
        "cvar_pct": round(abs(cvar), 4),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "observations": int(len(sample)),
        "worst_observed_pct": round(abs(float(sample.min())), 4),
    }


def monte_carlo(prices: pd.Series, horizon_days: int = 21,
                paths: int = 10_000, confidence: float = 0.95,
                seed: int | None = 42) -> dict | None:
    """
    Bootstrap simulation of the return distribution over `horizon_days`.

    `seed` is fixed by default so the same request returns the same
    numbers. A risk figure that changes on every page refresh is
    indistinguishable from a bug to the person reading it, and the
    stability costs nothing — the sampling error at 10,000 paths is far
    below the model error already present in the historical sample.
    """
    r = _clean_returns(prices)
    if len(r) < _MIN_RETURNS:
        return None

    rng = np.random.default_rng(seed)
    # Resample actual returns rather than draw from a fitted normal —
    # see the module docstring on why a Gaussian understates the tail.
    draws = rng.choice(r, size=(paths, horizon_days), replace=True)
    terminal = np.prod(1.0 + draws, axis=1) - 1.0

    pct = lambda p: round(float(np.percentile(terminal, p)), 4)  # noqa: E731
    q = np.percentile(terminal, (1 - confidence) * 100)
    tail = terminal[terminal <= q]

    return {
        "horizon_days": horizon_days,
        "paths": paths,
        "method": "bootstrap (resampled historical returns)",
        "mean_return": round(float(terminal.mean()), 4),
        "median_return": pct(50),
        "percentiles": {
            "p5": pct(5), "p10": pct(10), "p25": pct(25),
            "p50": pct(50), "p75": pct(75), "p90": pct(90), "p95": pct(95),
        },
        "var_pct": round(abs(float(q)), 4),
        "cvar_pct": round(abs(float(tail.mean())) if len(tail) else abs(float(q)), 4),
        "probability_of_loss": round(float((terminal < 0).mean()), 4),
        # Histogram for the UI, pre-binned server-side so the browser
        # never receives 10,000 raw floats.
        "histogram": _histogram(terminal, bins=40),
    }


def _histogram(values: np.ndarray, bins: int = 40) -> list[dict]:
    counts, edges = np.histogram(values, bins=bins)
    return [
        {"lower": round(float(edges[i]), 4),
         "upper": round(float(edges[i + 1]), 4),
         "mid": round(float((edges[i] + edges[i + 1]) / 2), 4),
         "count": int(counts[i])}
        for i in range(len(counts))
    ]


def beta_stability(prices: pd.Series, benchmark: pd.Series,
                   window: int = 63) -> dict | None:
    """
    Rolling beta and how much it moves.

    A single full-sample beta implies a constant that does not exist. A
    stock whose beta has ranged 0.6 to 1.8 has a "beta of 1.2" in the
    same sense that someone with one foot in ice and one in fire is on
    average comfortable. The dispersion is the point: unstable beta means
    hedge ratios computed from it will be wrong most of the time.
    """
    a = prices.pct_change().dropna()
    b = benchmark.pct_change().dropna()
    a.index = pd.to_datetime(a.index).tz_localize(None).normalize()
    b.index = pd.to_datetime(b.index).tz_localize(None).normalize()
    a = a[~a.index.duplicated(keep="last")]
    b = b[~b.index.duplicated(keep="last")]

    joined = pd.concat([a.rename("asset"), b.rename("mkt")], axis=1, join="inner").dropna()
    if len(joined) < window + 20:
        return None

    betas: list[dict] = []
    for end in range(window, len(joined), 5):
        chunk = joined.iloc[end - window:end]
        var_m = float(chunk["mkt"].var(ddof=1))
        if var_m <= 0:
            continue
        cov = float(chunk[["mkt", "asset"]].cov().iloc[0, 1])
        betas.append({"date": str(chunk.index[-1].date()), "beta": round(cov / var_m, 4)})

    if len(betas) < 3:
        return None

    values = np.array([x["beta"] for x in betas])
    full_var = float(joined["mkt"].var(ddof=1))
    full_beta = (float(joined[["mkt", "asset"]].cov().iloc[0, 1]) / full_var
                 if full_var > 0 else None)

    return {
        "window_days": window,
        "full_sample_beta": round(full_beta, 4) if full_beta is not None else None,
        "rolling_mean": round(float(values.mean()), 4),
        "rolling_std": round(float(values.std(ddof=1)), 4),
        "rolling_min": round(float(values.min()), 4),
        "rolling_max": round(float(values.max()), 4),
        # Coefficient of variation: dispersion relative to level, so a
        # high-beta name isn't automatically flagged as unstable.
        "instability": round(float(values.std(ddof=1) / abs(values.mean())), 4)
                       if values.mean() != 0 else None,
        "series": betas,
    }


def max_drawdown(prices: pd.Series) -> dict:
    """Deepest peak-to-trough decline, with dates and recovery status."""
    p = prices.dropna()
    if len(p) < 2:
        return {"max_drawdown_pct": None}
    running_max = p.cummax()
    dd = (p / running_max) - 1.0
    trough_idx = dd.idxmin()
    peak_idx = p.loc[:trough_idx].idxmax()
    after = p.loc[trough_idx:]
    peak_value = float(p.loc[peak_idx])
    recovered = after[after >= peak_value]
    return {
        "max_drawdown_pct": round(abs(float(dd.min())), 4),
        "peak_date": str(pd.Timestamp(peak_idx).date()),
        "trough_date": str(pd.Timestamp(trough_idx).date()),
        "recovered": bool(len(recovered) > 0),
        "recovery_date": str(pd.Timestamp(recovered.index[0]).date()) if len(recovered) else None,
    }
