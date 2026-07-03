"""
app/analysis/quantitative.py
-----------------------------
Quantitative Module: statistical and ML-based signal generation.

Components:
  1. Rolling 30-day annualised volatility
  2. Beta and Jensen's Alpha vs SPY (S&P 500 proxy)
  3. 12-1 Price Momentum factor (Jegadeesh-Titman, 1993)
  4. Ridge Regression ML signal trained on rolling factors

Sub-score weights:
  Volatility  25%  — regime-adjusted risk score
  Alpha       35%  — excess return vs market (most predictive)
  Momentum    25%  — price trend continuation
  ML signal   15%  — cross-factor regression

The Ridge model is intentionally simple: it regresses next-period return
on [momentum, vol_z, rsi_z] with Ridge regularisation (alpha=10.0) to
prevent overfitting on short windows. The signal is purely informational —
it is NOT used for autonomous execution in Phase 2.
"""

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.analysis.models import QuantitativeScore
from app.ingestion.market_data import MarketDataService

logger = logging.getLogger("aureus.analysis.quantitative")

_TRADING_DAYS_PER_YEAR = 252

# Sub-score weights
_W_VOL      = 0.25
_W_ALPHA    = 0.35
_W_MOMENTUM = 0.25
_W_ML       = 0.15


# ── Volatility ─────────────────────────────────────────────────────────────────

def _rolling_volatility(returns: pd.Series, window: int = 30) -> float | None:
    """
    Annualised rolling standard deviation of log returns.
    Uses log returns (ln(P_t / P_{t-1})) rather than simple returns for
    correct variance scaling.
    """
    if len(returns) < window:
        return None
    log_rets = np.log(1 + returns.replace([np.inf, -np.inf], np.nan).dropna())
    recent_std = log_rets.tail(window).std()
    if pd.isna(recent_std) or recent_std <= 0:
        return None
    return float(recent_std * np.sqrt(_TRADING_DAYS_PER_YEAR))


def _volatility_to_score(vol: float) -> float:
    """
    Convert annualised volatility to a 0–100 score.
    Lower vol = higher score (Sharpe-ratio-like preference for smooth returns).
    Benchmarks:
      Vol < 10%  → 95  (very stable, bond-like)
      Vol = 20%  → 70  (typical large-cap equity)
      Vol = 35%  → 45  (high-growth / small-cap)
      Vol > 60%  → 10  (meme-stock / speculative)
    """
    if vol <= 0.10:
        return 95.0
    if vol <= 0.20:
        return 70.0 + (0.20 - vol) / 0.10 * 25.0
    if vol <= 0.35:
        return 45.0 + (0.35 - vol) / 0.15 * 25.0
    if vol <= 0.60:
        return 10.0 + (0.60 - vol) / 0.25 * 35.0
    return 10.0


# ── Beta and Alpha ─────────────────────────────────────────────────────────────

def _compute_beta_alpha(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    risk_free_rate: float = 0.05,
) -> tuple[float | None, float | None]:
    """
    OLS regression of asset returns on market returns.
    Returns (beta, annualised Jensen's alpha).
    risk_free_rate: current approximate RF rate (5% as of mid-2024).
    """
    aligned = pd.concat(
        [asset_returns.rename("asset"), market_returns.rename("market")],
        axis=1,
        join="inner",
    ).dropna()

    if len(aligned) < 30:
        return None, None

    x = aligned["market"].values
    y = aligned["asset"].values

    # OLS: beta = Cov(r_i, r_m) / Var(r_m)
    cov_matrix = np.cov(x, y, ddof=1)
    var_market = cov_matrix[0, 0]
    if var_market <= 0:
        return None, None

    beta = cov_matrix[0, 1] / var_market
    daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1

    # Alpha = mean(r_i) - RF - beta * (mean(r_m) - RF), annualised
    alpha_daily = (y.mean() - daily_rf) - beta * (x.mean() - daily_rf)
    alpha_annual = (1 + alpha_daily) ** _TRADING_DAYS_PER_YEAR - 1

    return float(beta), float(alpha_annual)


def _alpha_to_score(alpha: float) -> float:
    """
    Convert annualised Jensen's alpha to 0–100.
    Alpha = +10% → 75; +20% → 100; 0% → 50; -10% → 25; -20% → 0
    """
    score = 50.0 + (alpha / 0.20) * 50.0
    return max(0.0, min(100.0, score))


# ── Momentum factor ────────────────────────────────────────────────────────────

def _compute_momentum_12_1(prices: pd.Series) -> float | None:
    """
    Jegadeesh-Titman 12-1 momentum:
    12-month return excluding the most recent month.
    Requires at least 252 trading days of data.
    """
    if len(prices) < 252:
        return None
    price_12m_ago = prices.iloc[-252]
    price_1m_ago  = prices.iloc[-21]
    if price_12m_ago <= 0 or price_1m_ago <= 0:
        return None
    return float((price_1m_ago - price_12m_ago) / price_12m_ago)


def _momentum_to_score(momentum: float) -> float:
    """
    +40% momentum → 100; +0% → 50; -40% → 0
    """
    score = 50.0 + (momentum / 0.40) * 50.0
    return max(0.0, min(100.0, score))


# ── Ridge Regression ML signal ─────────────────────────────────────────────────

def _compute_ml_signal(
    prices: pd.Series,
    vol: float | None,
    momentum: float | None,
    rsi: float | None,
) -> float:
    """
    Ridge regression trained on rolling window of (features → next-period return).

    Features:
      - z-scored 21-day momentum
      - z-scored 30-day volatility
      - z-scored RSI (centred at 50)

    Target:
      - Forward 21-day log return

    A Ridge penalty (L2) with alpha=10.0 prevents overfitting on short
    windows (typically 252 bars). The model is retrained on every call
    (intentional — we have no persistence layer in Phase 2 yet).

    Returns a score 0–100, where 50 is neutral (predicted near-zero alpha).
    """
    # Can't run without sklearn
    try:
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        logger.warning("scikit-learn not available — ML signal defaulting to 50")
        return 50.0

    if len(prices) < 100:
        return 50.0

    log_rets = np.log(prices / prices.shift(1)).dropna()

    # Build feature matrix over rolling 21-day windows
    feat_momentum: list[float] = []
    feat_vol: list[float]      = []
    target: list[float]        = []

    window_calc = 21
    window_vol  = 30
    forward     = 21

    for i in range(window_vol, len(log_rets) - forward):
        w_rets   = log_rets.iloc[i - window_calc: i]
        w_vol    = log_rets.iloc[i - window_vol: i].std() * np.sqrt(_TRADING_DAYS_PER_YEAR)
        fwd_ret  = log_rets.iloc[i: i + forward].sum()

        feat_momentum.append(float(w_rets.sum()))
        feat_vol.append(float(w_vol))
        target.append(float(fwd_ret))

    if len(target) < 30:
        return 50.0

    X_arr = np.column_stack([feat_momentum, feat_vol])
    y_arr = np.array(target)

    # Z-score features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)

    # Train Ridge on all history except the last observation
    model = Ridge(alpha=10.0)
    model.fit(X_scaled[:-1], y_arr[:-1])

    # Predict on the most recent observation
    current_features = X_scaled[-1].reshape(1, -1)
    predicted_return = float(model.predict(current_features)[0])

    # Map predicted 21-day log return to 0–100 score
    # +10% predicted → 100, 0% → 50, -10% → 0
    score = 50.0 + (predicted_return / 0.10) * 50.0
    return max(0.0, min(100.0, score))


# ── Sharpe ratio ───────────────────────────────────────────────────────────────

def _compute_sharpe(
    returns: pd.Series,
    risk_free_rate: float = 0.05,
    window: int = 252,
) -> float | None:
    daily_rf  = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
    recent = returns.dropna().tail(window)
    if len(recent) < 30:
        return None
    excess  = recent - daily_rf
    std_dev = excess.std()
    if std_dev <= 0:
        return None
    return float((excess.mean() / std_dev) * np.sqrt(_TRADING_DAYS_PER_YEAR))


# ── Public API ─────────────────────────────────────────────────────────────────

def run_quantitative_analysis(
    ticker: str,
    bars: pd.DataFrame,
    spy_bars: pd.DataFrame | None = None,
    rsi_value: float | None = None,
) -> QuantitativeScore:
    """
    Run all quantitative sub-analyses and return a QuantitativeScore.

    Args:
        ticker:     Asset symbol.
        bars:       OHLCV DataFrame, same format as from MarketDataService.
        spy_bars:   SPY bars for beta/alpha calculation. If None, alpha defaults to 50.
        rsi_value:  Pre-computed RSI from the technical module (avoids re-computing).
    """
    notes: list[str] = []

    prices  = bars["close"]
    returns = prices.pct_change().dropna()

    # ── Volatility ────────────────────────────────────────────────
    vol_30d = _rolling_volatility(returns, window=30)
    vol_score = _volatility_to_score(vol_30d) if vol_30d is not None else 50.0
    if vol_30d is not None:
        notes.append(f"Annualised 30d vol: {vol_30d*100:.1f}% → score {vol_score:.1f}")

    # ── Beta / Alpha ──────────────────────────────────────────────
    beta: float | None  = None
    alpha: float | None = None
    alpha_score = 50.0

    if spy_bars is not None and not spy_bars.empty:
        spy_returns = spy_bars["close"].pct_change().dropna()
        beta, alpha = _compute_beta_alpha(returns, spy_returns)
        if alpha is not None:
            alpha_score = _alpha_to_score(alpha)
            notes.append(
                f"Jensen's alpha (annualised): {alpha*100:.2f}% | Beta: {beta:.3f} → score {alpha_score:.1f}"
            )
    else:
        notes.append("SPY data unavailable — alpha/beta defaulting to neutral")

    # ── Momentum ──────────────────────────────────────────────────
    momentum_12_1 = _compute_momentum_12_1(prices)
    momentum_score = _momentum_to_score(momentum_12_1) if momentum_12_1 is not None else 50.0
    if momentum_12_1 is not None:
        notes.append(f"12-1 momentum: {momentum_12_1*100:.1f}% → score {momentum_score:.1f}")

    # ── Sharpe ────────────────────────────────────────────────────
    sharpe = _compute_sharpe(returns)

    # ── Ridge ML signal ───────────────────────────────────────────
    ml_score = _compute_ml_signal(
        prices=prices,
        vol=vol_30d,
        momentum=momentum_12_1,
        rsi=rsi_value,
    )
    notes.append(f"Ridge ML signal score: {ml_score:.1f}")

    # ── Weighted composite ────────────────────────────────────────
    composite = (
        _W_VOL      * vol_score      +
        _W_ALPHA    * alpha_score    +
        _W_MOMENTUM * momentum_score +
        _W_ML       * ml_score
    )

    logger.info(
        "Quantitative analysis complete",
        extra={
            "ticker": ticker,
            "score": round(composite, 2),
            "vol": round(vol_score, 2),
            "alpha": round(alpha_score, 2),
            "momentum": round(momentum_score, 2),
            "ml": round(ml_score, 2),
        },
    )

    return QuantitativeScore(
        ticker=ticker,
        score=round(composite, 2),
        volatility_score=round(vol_score, 2),
        alpha_score=round(alpha_score, 2),
        momentum_score=round(momentum_score, 2),
        ml_signal_score=round(ml_score, 2),
        rolling_volatility_30d=round(vol_30d, 4) if vol_30d else None,
        beta_vs_spy=round(beta, 4) if beta else None,
        alpha_vs_spy=round(alpha, 4) if alpha else None,
        sharpe_ratio=round(sharpe, 4) if sharpe else None,
        momentum_12_1=round(momentum_12_1, 4) if momentum_12_1 else None,
        analysis_notes=notes,
    )
