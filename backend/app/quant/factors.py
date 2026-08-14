"""
app/quant/factors.py
----------------------
Fama-French factor exposures: how much of a stock's return is explained by
known systematic risk factors, and how much is genuinely idiosyncratic.

=====================================================================
WHAT THIS ANSWERS THAT A SINGLE BETA DOES NOT
=====================================================================
"Beta vs SPY" collapses every source of systematic risk into one number.
That is fine as a summary and useless as a decomposition: two stocks with
identical market betas can have completely opposite exposures to company
size and to value-versus-growth, and will behave nothing alike in a
rotation.

The Fama-French model separates them:

    Mkt-RF   the market's excess return          (market risk)
    SMB      Small Minus Big                     (size tilt)
    HML      High Minus Low book-to-market       (value vs growth tilt)
    RMW      Robust Minus Weak profitability     (quality tilt, 5-factor)
    CMA      Conservative Minus Aggressive inv.  (investment tilt, 5-factor)

Regressing a stock's excess returns on these gives a loading per factor
plus an intercept. That intercept is ALPHA in the strict sense: return
unexplained by any of the known factors. It is a far higher bar than
"alpha vs SPY", which credits a stock for a small-cap value tilt as
though it were skill.

=====================================================================
DATA SOURCE
=====================================================================
Ken French's data library at Dartmouth. Free, no key, no registration —
the canonical academic source for these series.

Format quirks handled below: a multi-line prose preamble before the real
header, dates as bare YYYYMMDD integers, and values in PERCENT rather
than decimal (0.09 means 0.09%, not 9%). Getting that last one wrong
inflates every loading by 100x, so the conversion is explicit.
"""

import io
import json
import logging
import zipfile

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger("aureus.quant.factors")

_FF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
_FF3_URL = f"{_FF_BASE}/F-F_Research_Data_Factors_daily_CSV.zip"
_FF5_URL = f"{_FF_BASE}/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"

# The factor series are appended to monthly, never revised. A week of
# cache costs nothing in accuracy and saves a multi-megabyte download.
_CACHE_TTL = 60 * 60 * 24 * 7
_CACHE_KEY = "ff_factors:"

_MIN_OBSERVATIONS = 60   # below ~3 months a 5-factor regression is noise

FACTOR_LABELS = {
    "Mkt-RF": "Market",
    "SMB": "Size (small minus big)",
    "HML": "Value (high minus low book/market)",
    "RMW": "Profitability (robust minus weak)",
    "CMA": "Investment (conservative minus aggressive)",
}

FACTOR_MEANING = {
    "Mkt-RF": "Sensitivity to the overall market. 1.0 moves with the index; above 1.0 amplifies it.",
    "SMB": "Positive means the stock behaves like a small-cap; negative like a large-cap.",
    "HML": "Positive means it behaves like a value stock; negative like a growth stock.",
    "RMW": "Positive means it trades like a highly profitable company; negative like a weak one.",
    "CMA": "Positive means it trades like a conservative investor of capital; negative like an aggressive one.",
}


def _cache_get(key: str):
    try:
        from app.core.redis_client import get_redis_client
        raw = get_redis_client().get(f"{_CACHE_KEY}{key}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_put(key: str, value) -> None:
    try:
        from app.core.redis_client import get_redis_client
        get_redis_client().setex(f"{_CACHE_KEY}{key}", _CACHE_TTL, json.dumps(value))
    except Exception:
        pass


def _parse_ff_csv(raw: str) -> pd.DataFrame:
    """
    Parse a Ken French daily CSV.

    The file opens with several lines of prose, then the real header row
    (which starts with a bare comma because the date column is unnamed).
    Anything after the daily block that isn't an 8-digit date is dropped.
    """
    lines = raw.split("\n")
    header_idx = next(
        (i for i, l in enumerate(lines) if l.strip().startswith(",") and "Mkt-RF" in l),
        None,
    )
    if header_idx is None:
        raise ValueError("Could not locate the factor header row")

    columns = [c.strip() for c in lines[header_idx].strip().split(",")]
    columns[0] = "date"

    rows: list[list] = []
    for line in lines[header_idx + 1:]:
        parts = [p.strip() for p in line.strip().split(",")]
        if len(parts) != len(columns) or not parts[0].isdigit() or len(parts[0]) != 8:
            continue
        try:
            rows.append([parts[0]] + [float(p) for p in parts[1:]])
        except ValueError:
            continue

    df = pd.DataFrame(rows, columns=columns)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.set_index("date").sort_index()
    # Ken French publishes PERCENT. Everything downstream works in
    # decimal returns; skipping this scales every loading by 100.
    return df / 100.0


def load_factors(model: str = "ff5") -> pd.DataFrame | None:
    """Daily factor returns as decimals. Cached for a week."""
    url = _FF5_URL if model == "ff5" else _FF3_URL
    cached = _cache_get(model)
    if cached:
        try:
            df = pd.DataFrame(cached["data"], columns=cached["columns"])
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date").sort_index()
        except Exception:
            pass

    try:
        r = httpx.get(url, timeout=90.0, follow_redirects=True)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        raw = z.read(z.namelist()[0]).decode("latin-1")
        df = _parse_ff_csv(raw)
    except Exception as exc:
        logger.warning("Fama-French factor load failed",
                       extra={"model": model, "error": str(exc)})
        return None

    # Cache only the recent tail — the series runs to 1926 and the whole
    # thing is megabytes of JSON for data no regression here will use.
    tail = df.tail(2600)   # ~10 years of trading days
    out = tail.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    _cache_put(model, {"columns": list(out.columns), "data": out.values.tolist()})
    logger.info("Fama-French factors loaded",
                extra={"model": model, "rows": len(df),
                       "last": str(df.index[-1].date())})
    return df


def _ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Least squares with an intercept. Returns (coefficients, t-stats, R^2).

    t-stats are computed rather than just the point estimates because a
    factor loading without a significance test invites reading noise as a
    tilt — with five factors and a few hundred observations, some loading
    will always look non-zero.
    """
    n, k = X.shape
    Xd = np.column_stack([np.ones(n), X])
    coef, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    resid = y - Xd @ coef
    dof = n - k - 1
    if dof <= 0:
        return coef, np.zeros_like(coef), 0.0
    sigma2 = float(resid @ resid) / dof
    try:
        cov = sigma2 * np.linalg.inv(Xd.T @ Xd)
        se = np.sqrt(np.diag(cov))
        tstats = np.divide(coef, se, out=np.zeros_like(coef), where=se > 0)
    except np.linalg.LinAlgError:
        tstats = np.zeros_like(coef)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot > 0 else 0.0
    return coef, tstats, r2


def factor_exposures(prices: pd.Series, model: str = "ff5") -> dict | None:
    """
    Regress a price series' excess returns on the factor set.

    Returns loadings with t-stats, annualised alpha, and R^2 — or None if
    the factor data or the overlap is insufficient.
    """
    factors = load_factors(model)
    if factors is None or factors.empty:
        return None

    returns = prices.pct_change().dropna()
    if returns.empty:
        return None

    # Both sides must be tz-naive dates to align; provider bars carry a
    # timezone and the factor index does not.
    ret = returns.copy()
    ret.index = pd.to_datetime(ret.index).tz_localize(None).normalize()
    ret = ret[~ret.index.duplicated(keep="last")]

    joined = pd.concat([ret.rename("r"), factors], axis=1, join="inner").dropna()
    if len(joined) < _MIN_OBSERVATIONS:
        logger.info("Insufficient factor overlap",
                    extra={"rows": len(joined), "needed": _MIN_OBSERVATIONS})
        return None

    factor_cols = [c for c in factors.columns if c != "RF"]
    y = (joined["r"] - joined["RF"]).values      # excess return
    X = joined[factor_cols].values

    coef, tstats, r2 = _ols(X, y)
    alpha_daily = float(coef[0])
    # Compound the daily intercept; 252 * daily materially understates it.
    alpha_annual = (1.0 + alpha_daily) ** 252 - 1.0

    loadings = []
    for i, name in enumerate(factor_cols):
        beta = float(coef[i + 1])
        t = float(tstats[i + 1])
        loadings.append({
            "factor": name,
            "label": FACTOR_LABELS.get(name, name),
            "meaning": FACTOR_MEANING.get(name, ""),
            "loading": round(beta, 4),
            "t_stat": round(t, 2),
            # |t| > 1.96 is the conventional 5% threshold. Below it the
            # loading is not distinguishable from zero and the UI says so
            # rather than inviting a story about a tilt that isn't there.
            "significant": abs(t) >= 1.96,
        })

    return {
        "model": "Fama-French 5-Factor" if model == "ff5" else "Fama-French 3-Factor",
        "observations": len(joined),
        "start": str(joined.index[0].date()),
        "end": str(joined.index[-1].date()),
        "alpha_daily": round(alpha_daily, 6),
        "alpha_annualised": round(alpha_annual, 4),
        "alpha_t_stat": round(float(tstats[0]), 2),
        "alpha_significant": abs(float(tstats[0])) >= 1.96,
        "r_squared": round(r2, 4),
        "loadings": loadings,
    }


def rolling_factor_betas(prices: pd.Series, window: int = 126,
                         model: str = "ff3") -> list[dict]:
    """
    Factor loadings through time, on a rolling window (default ~6 months).

    A single full-sample loading hides regime change: a stock can be a
    growth name for two years and a value name after a de-rating, and the
    full-sample number would report the meaningless average of the two.
    Defaults to the 3-factor model — five factors on a 126-day window is
    not enough data per parameter to be stable.
    """
    factors = load_factors(model)
    if factors is None or factors.empty:
        return []

    returns = prices.pct_change().dropna()
    ret = returns.copy()
    ret.index = pd.to_datetime(ret.index).tz_localize(None).normalize()
    ret = ret[~ret.index.duplicated(keep="last")]

    joined = pd.concat([ret.rename("r"), factors], axis=1, join="inner").dropna()
    if len(joined) < window + 20:
        return []

    factor_cols = [c for c in factors.columns if c != "RF"]
    out: list[dict] = []
    # Step by a fortnight: daily re-estimation on overlapping windows
    # produces a near-identical series at ten times the payload size.
    for end in range(window, len(joined), 10):
        chunk = joined.iloc[end - window:end]
        y = (chunk["r"] - chunk["RF"]).values
        X = chunk[factor_cols].values
        coef, _, _ = _ols(X, y)
        row = {"date": str(chunk.index[-1].date())}
        for i, name in enumerate(factor_cols):
            row[name] = round(float(coef[i + 1]), 4)
        out.append(row)
    return out
