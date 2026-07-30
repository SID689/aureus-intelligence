"""
app/analysis/quantitative.py  (Phase 6 rewrite — dynamic reweighting)
"""

import logging
import numpy as np
import pandas as pd

from app.analysis.models import QuantitativeScore
from app.analysis.reweighting import WeightedSignal, reweight

logger = logging.getLogger("aureus.analysis.quantitative")

_TRADING_DAYS_PER_YEAR = 252
_W_VOL, _W_ALPHA, _W_MOMENTUM, _W_ML = 0.25, 0.35, 0.25, 0.15


def _rolling_volatility(returns: pd.Series, window: int = 30) -> float | None:
    if len(returns) < window:
        return None
    log_rets = np.log(1 + returns.replace([np.inf, -np.inf], np.nan).dropna())
    recent_std = log_rets.tail(window).std()
    if pd.isna(recent_std) or recent_std <= 0:
        return None
    return float(recent_std * np.sqrt(_TRADING_DAYS_PER_YEAR))


def _volatility_to_score(vol: float) -> float:
    if vol <= 0.10: return 95.0
    if vol <= 0.20: return 70.0 + (0.20 - vol) / 0.10 * 25.0
    if vol <= 0.35: return 45.0 + (0.35 - vol) / 0.15 * 25.0
    if vol <= 0.60: return 10.0 + (0.60 - vol) / 0.25 * 35.0
    return 10.0


def _compute_beta_alpha(asset_returns: pd.Series, market_returns: pd.Series, risk_free_rate: float = 0.05) -> tuple[float | None, float | None]:
    aligned = pd.concat([asset_returns.rename("asset"), market_returns.rename("market")], axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return None, None
    x, y = aligned["market"].values, aligned["asset"].values
    cov_matrix = np.cov(x, y, ddof=1)
    var_market = cov_matrix[0, 0]
    if var_market <= 0:
        return None, None
    beta = cov_matrix[0, 1] / var_market
    daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
    alpha_daily = (y.mean() - daily_rf) - beta * (x.mean() - daily_rf)
    alpha_annual = (1 + alpha_daily) ** _TRADING_DAYS_PER_YEAR - 1
    return float(beta), float(alpha_annual)


def _alpha_to_score(alpha: float) -> float:
    return max(0.0, min(100.0, 50.0 + (alpha / 0.20) * 50.0))


def _compute_momentum_12_1(prices: pd.Series) -> float | None:
    if len(prices) < 252:
        return None
    p12, p1 = prices.iloc[-252], prices.iloc[-21]
    if p12 <= 0 or p1 <= 0:
        return None
    return float((p1 - p12) / p12)


def _momentum_to_score(momentum: float) -> float:
    return max(0.0, min(100.0, 50.0 + (momentum / 0.40) * 50.0))


def _compute_ml_signal(prices: pd.Series) -> tuple[float, bool]:
    try:
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return 50.0, False

    if len(prices) < 100:
        return 50.0, False

    log_rets = np.log(prices / prices.shift(1)).dropna()
    feat_momentum, feat_vol, target = [], [], []
    window_calc, window_vol, forward = 21, 30, 21

    for i in range(window_vol, len(log_rets) - forward):
        w_rets  = log_rets.iloc[i - window_calc:i]
        w_vol   = log_rets.iloc[i - window_vol:i].std() * np.sqrt(_TRADING_DAYS_PER_YEAR)
        fwd_ret = log_rets.iloc[i:i + forward].sum()
        feat_momentum.append(float(w_rets.sum()))
        feat_vol.append(float(w_vol))
        target.append(float(fwd_ret))

    if len(target) < 30:
        return 50.0, False

    X = np.column_stack([feat_momentum, feat_vol])
    y = np.array(target)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = Ridge(alpha=10.0)
    model.fit(X_scaled[:-1], y[:-1])
    predicted_return = float(model.predict(X_scaled[-1].reshape(1, -1))[0])
    score = 50.0 + (predicted_return / 0.10) * 50.0
    return max(0.0, min(100.0, score)), True


def _compute_sharpe(returns: pd.Series, risk_free_rate: float = 0.05, window: int = 252) -> float | None:
    daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
    recent = returns.dropna().tail(window)
    if len(recent) < 30:
        return None
    excess = recent - daily_rf
    std_dev = excess.std()
    if std_dev <= 0:
        return None
    return float((excess.mean() / std_dev) * np.sqrt(_TRADING_DAYS_PER_YEAR))


def run_quantitative_analysis(
    ticker: str,
    bars: pd.DataFrame,
    spy_bars: pd.DataFrame | None = None,
    rsi_value: float | None = None,
) -> QuantitativeScore:
    notes: list[str] = []
    signals: list[dict] = []
    prices  = bars["close"]
    returns = prices.pct_change().dropna()

    vol_30d = _rolling_volatility(returns, window=30)
    vol_computed = vol_30d is not None
    vol_score = _volatility_to_score(vol_30d) if vol_computed else 50.0
    if vol_computed:
        notes.append(f"30-day annualized volatility {vol_30d*100:.1f}% → risk component {vol_score:.0f}/100")
        signals.append({"label": "30-Day Volatility", "score": vol_score, "detail": f"Annualized volatility of {vol_30d*100:.0f}%" + (" is elevated relative to typical large-caps" if vol_score < 40 else " is unusually stable" if vol_score > 80 else "")})
    else:
        notes.append("Insufficient history for volatility (need 30+ days) — excluded from composite")

    beta: float | None = None
    alpha: float | None = None
    alpha_computed = False
    alpha_score = 50.0
    if spy_bars is not None and not spy_bars.empty:
        spy_returns = spy_bars["close"].pct_change().dropna()
        beta, alpha = _compute_beta_alpha(returns, spy_returns)
        if alpha is not None:
            alpha_computed = True
            alpha_score = _alpha_to_score(alpha)
            notes.append(f"Annualized alpha vs S&P 500 {alpha*100:+.2f}% (beta {beta:.2f}) → alpha component {alpha_score:.0f}/100")
            signals.append({"label": "Alpha vs S&P 500", "score": alpha_score, "detail": f"{alpha*100:+.1f}% annualized alpha (beta {beta:.2f})" + (" — underperforming the market on a risk-adjusted basis" if alpha_score < 40 else " — genuine outperformance beyond market exposure" if alpha_score > 75 else "")})
        else:
            notes.append("Insufficient overlapping history vs S&P 500 for alpha/beta — excluded from composite")
    else:
        notes.append("Benchmark (SPY) data unavailable — alpha/beta excluded from composite")

    momentum_12_1 = _compute_momentum_12_1(prices)
    momentum_computed = momentum_12_1 is not None
    momentum_score = _momentum_to_score(momentum_12_1) if momentum_computed else 50.0
    if momentum_computed:
        notes.append(f"12-month minus 1-month momentum {momentum_12_1*100:+.1f}% → momentum component {momentum_score:.0f}/100")
        signals.append({"label": "12-1 Momentum", "score": momentum_score, "detail": f"{momentum_12_1*100:+.1f}% momentum over the trailing year (excluding the most recent month)"})
    else:
        notes.append("Insufficient history for 12-1 momentum (need 252+ days) — excluded from composite")

    sharpe = _compute_sharpe(returns)

    ml_score, ml_computed = _compute_ml_signal(prices)
    if ml_computed:
        notes.append(f"Ridge regression forward-return signal → ML component {ml_score:.0f}/100")
    else:
        notes.append("Insufficient history for ML signal (need 100+ days) — excluded from composite")

    result = reweight([
        WeightedSignal("volatility_score", vol_score,      _W_VOL,      vol_computed),
        WeightedSignal("alpha_score",      alpha_score,    _W_ALPHA,    alpha_computed),
        WeightedSignal("momentum_score",   momentum_score, _W_MOMENTUM, momentum_computed),
        WeightedSignal("ml_signal_score",  ml_score,       _W_ML,       ml_computed),
    ])
    if result.dropped_signals:
        notes.append(f"Excluded from scoring (no real data): {', '.join(result.dropped_signals)}")

    logger.info("Quantitative analysis complete", extra={
        "ticker": ticker, "score": result.composite_score, "data_completeness": result.data_completeness,
    })

    return QuantitativeScore(
        ticker=ticker, score=result.composite_score,
        volatility_score=round(vol_score, 2), alpha_score=round(alpha_score, 2),
        momentum_score=round(momentum_score, 2), ml_signal_score=round(ml_score, 2),
        rolling_volatility_30d=round(vol_30d, 4) if vol_30d else None,
        beta_vs_spy=round(beta, 4) if beta else None,
        alpha_vs_spy=round(alpha, 4) if alpha else None,
        sharpe_ratio=round(sharpe, 4) if sharpe else None,
        momentum_12_1=round(momentum_12_1, 4) if momentum_12_1 else None,
        data_completeness=result.data_completeness,
        effective_weights=result.effective_weights,
        signal_breakdown=signals,
        analysis_notes=notes,
    )
