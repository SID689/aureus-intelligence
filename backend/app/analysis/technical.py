"""
app/analysis/technical.py
--------------------------
Technical Module: computes RSI, MACD, volume profile, and explicit
support/resistance coordinate matrices from OHLCV bar data.

All calculations use pandas-ta (pure Python, no C compiler required).
TA-Lib is an acceptable drop-in replacement — just swap `import pandas_ta`
calls for `import talib` and map the function signatures.

Sub-score weights:
  RSI    30%  — momentum oscillator
  MACD   30%  — trend direction and acceleration
  S/R    25%  — where is price relative to key levels?
  Volume 15%  — is a move confirmed by volume?
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
    _PANDAS_TA_AVAILABLE = True
except ImportError:
    _PANDAS_TA_AVAILABLE = False

from app.analysis.models import SupportResistanceLevel, TechnicalScore

logger = logging.getLogger("aureus.analysis.technical")

# Sub-score weights
_W_RSI    = 0.30
_W_MACD   = 0.30
_W_SR     = 0.25
_W_VOLUME = 0.15

# Minimum bars required for reliable indicator calculation
_MIN_BARS = 60


# ── RSI ────────────────────────────────────────────────────────────────────────

def _compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    """
    Wilder's smoothed RSI.
    Returns the most recent RSI value or None if insufficient data.
    pandas-ta uses an exponential moving average that matches the
    original Wilder smoothing (alpha = 1/period).
    """
    if len(close) < period + 5:
        return None

    if _PANDAS_TA_AVAILABLE:
        rsi_series = ta.rsi(close, length=period)
    else:
        # Manual implementation as fallback if pandas-ta install fails
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))

    if rsi_series is None or rsi_series.empty:
        return None
    val = rsi_series.iloc[-1]
    return float(val) if pd.notna(val) else None


def _rsi_to_score(rsi: float) -> float:
    """
    Non-linear RSI → score mapping capturing oversold/overbought extremes:
      RSI ≤ 25  →  92  (deeply oversold — mean reversion candidate)
      RSI = 30  →  80  (classically oversold)
      RSI = 50  →  50  (neutral)
      RSI = 70  →  25  (classically overbought)
      RSI ≥ 75  →  10  (deeply overbought)
    """
    if rsi <= 25:
        return 92.0
    if rsi <= 30:
        # interpolate 92 → 80
        return 80.0 + (30.0 - rsi) / 5.0 * 12.0
    if rsi <= 50:
        # interpolate 80 → 50
        return 50.0 + (50.0 - rsi) / 20.0 * 30.0
    if rsi <= 70:
        # interpolate 50 → 25
        return 50.0 - (rsi - 50.0) / 20.0 * 25.0
    if rsi <= 75:
        # interpolate 25 → 10
        return 25.0 - (rsi - 70.0) / 5.0 * 15.0
    return 10.0


# ── MACD ───────────────────────────────────────────────────────────────────────

def _compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[float | None, float | None, float | None]:
    """
    Returns (macd_line, signal_line, histogram) as the most recent values.
    Histogram = macd_line - signal_line.
    """
    if len(close) < slow + signal + 5:
        return None, None, None

    if _PANDAS_TA_AVAILABLE:
        result = ta.macd(close, fast=fast, slow=slow, signal=signal)
        if result is None or result.empty:
            return None, None, None
        macd_col = f"MACD_{fast}_{slow}_{signal}"
        hist_col = f"MACDh_{fast}_{slow}_{signal}"
        sig_col  = f"MACDs_{fast}_{slow}_{signal}"
        last = result.iloc[-1]
        return (
            float(last[macd_col]) if pd.notna(last.get(macd_col)) else None,
            float(last[sig_col])  if pd.notna(last.get(sig_col))  else None,
            float(last[hist_col]) if pd.notna(last.get(hist_col)) else None,
        )
    else:
        # Manual fallback
        ema_fast   = close.ewm(span=fast, adjust=False).mean()
        ema_slow   = close.ewm(span=slow, adjust=False).mean()
        macd_line  = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram  = macd_line - signal_line
        return (
            float(macd_line.iloc[-1])  if pd.notna(macd_line.iloc[-1])  else None,
            float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else None,
            float(histogram.iloc[-1])  if pd.notna(histogram.iloc[-1])  else None,
        )


def _macd_to_score(
    macd_line: float,
    signal_line: float,
    histogram: float,
    close_prices: pd.Series,
) -> float:
    """
    MACD score from three signals:
    1. Histogram sign  (+/-) → bullish/bearish
    2. Histogram direction (increasing/decreasing) → momentum strength
    3. MACD vs signal crossover recency → entry/exit timing
    """
    components: list[float] = []

    # 1. Sign of histogram
    sign_score = 65.0 if histogram > 0 else 35.0
    components.append(sign_score)

    # 2. Histogram increasing (gaining momentum)
    if _PANDAS_TA_AVAILABLE:
        hist_series = ta.macd(close_prices)
        if hist_series is not None and not hist_series.empty:
            hist_col = [c for c in hist_series.columns if c.startswith("MACDh")]
            if hist_col:
                recent_hist = hist_series[hist_col[0]].dropna().tail(3)
                if len(recent_hist) >= 2:
                    increasing = recent_hist.iloc[-1] > recent_hist.iloc[-2]
                    if histogram > 0:
                        components.append(80.0 if increasing else 55.0)
                    else:
                        components.append(20.0 if not increasing else 45.0)

    # 3. Distance from zero normalised by price (strong vs weak signal)
    price_range = close_prices.tail(52).max() - close_prices.tail(52).min()
    if price_range > 0:
        normalised_hist = abs(histogram) / price_range * 100
        strength_bonus = min(10.0, normalised_hist * 2)
        components.append(50.0 + (strength_bonus if histogram > 0 else -strength_bonus))

    return sum(components) / len(components) if components else 50.0


# ── Support / Resistance ───────────────────────────────────────────────────────

def _find_support_resistance(
    df: pd.DataFrame,
    lookback_periods: int = 120,
    n_levels: int = 5,
) -> list[SupportResistanceLevel]:
    """
    Identify support and resistance levels using pivot-point clustering.

    Method: find local minima/maxima (price doesn't go lower/higher for
    `window` bars on each side), then cluster nearby pivots into levels.
    Each level's strength is the number of pivots within the cluster.
    """
    if len(df) < lookback_periods:
        lookback_periods = len(df)

    recent = df.tail(lookback_periods)
    highs  = recent["high"].values
    lows   = recent["low"].values
    window = 5  # local extrema window

    support_pivots: list[float]    = []
    resistance_pivots: list[float] = []

    for i in range(window, len(lows) - window):
        # Local minimum → support
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            support_pivots.append(float(lows[i]))
        # Local maximum → resistance
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            resistance_pivots.append(float(highs[i]))

    def _cluster(pivots: list[float], level_type: str) -> list[SupportResistanceLevel]:
        if not pivots:
            return []
        levels: list[SupportResistanceLevel] = []
        pivots_sorted = sorted(pivots)
        current_cluster = [pivots_sorted[0]]

        for price in pivots_sorted[1:]:
            tolerance = current_cluster[0] * 0.015  # 1.5% cluster window
            if price - current_cluster[-1] <= tolerance:
                current_cluster.append(price)
            else:
                centroid = sum(current_cluster) / len(current_cluster)
                levels.append(SupportResistanceLevel(
                    price=round(centroid, 2),
                    level_type=level_type,  # type: ignore[arg-type]
                    strength=float(len(current_cluster)),
                ))
                current_cluster = [price]

        if current_cluster:
            centroid = sum(current_cluster) / len(current_cluster)
            levels.append(SupportResistanceLevel(
                price=round(centroid, 2),
                level_type=level_type,  # type: ignore[arg-type]
                strength=float(len(current_cluster)),
            ))

        # Return strongest levels
        return sorted(levels, key=lambda l: l.strength, reverse=True)[:n_levels]

    supports    = _cluster(support_pivots, "support")
    resistances = _cluster(resistance_pivots, "resistance")
    return supports + resistances


def _sr_to_score(
    current_price: float,
    levels: list[SupportResistanceLevel],
) -> float:
    """
    Score based on price proximity to support/resistance.
    Close to support → bullish. Close to resistance → bearish.
    """
    if not levels or current_price <= 0:
        return 50.0

    supports    = [l for l in levels if l.level_type == "support"]
    resistances = [l for l in levels if l.level_type == "resistance"]

    # Nearest support below current price
    support_below  = [l for l in supports    if l.price < current_price]
    resistance_above = [l for l in resistances if l.price > current_price]

    score = 50.0
    if support_below:
        nearest_support = max(support_below, key=lambda l: l.price)
        pct_above_support = (current_price - nearest_support.price) / nearest_support.price
        # Within 2% of support → very bullish; more than 15% above → neutral from support
        support_score = max(50.0, 95.0 - (pct_above_support / 0.15) * 45.0)
        score = (score + support_score) / 2

    if resistance_above:
        nearest_resistance = min(resistance_above, key=lambda l: l.price)
        pct_below_resistance = (nearest_resistance.price - current_price) / nearest_resistance.price
        # Within 2% of resistance → bearish; more than 15% below → neutral from resistance
        resistance_penalty = max(0.0, 45.0 - (pct_below_resistance / 0.15) * 45.0)
        score -= resistance_penalty

    return max(0.0, min(100.0, score))


# ── Volume profile ─────────────────────────────────────────────────────────────

def _compute_volume_score(df: pd.DataFrame) -> float:
    """
    Compare recent volume (5-day avg) to medium-term volume (20-day avg).
    Rising price + above-average volume = bullish confirmation.
    Rising price + below-average volume = unconfirmed move.
    """
    if len(df) < 25:
        return 50.0

    vol_5d  = df["volume"].tail(5).mean()
    vol_20d = df["volume"].tail(20).mean()
    price_trend_5d = df["close"].iloc[-1] - df["close"].iloc[-5]

    if vol_20d <= 0:
        return 50.0

    volume_ratio = vol_5d / vol_20d  # > 1 = above-average volume

    if price_trend_5d > 0 and volume_ratio > 1.1:
        # Bullish price + above-average volume: strong confirmation
        score = min(100.0, 65.0 + (volume_ratio - 1.0) * 50.0)
    elif price_trend_5d > 0 and volume_ratio <= 1.0:
        # Rising price on low volume: weak signal
        score = 50.0
    elif price_trend_5d < 0 and volume_ratio > 1.1:
        # Falling price + high volume: bearish confirmation
        score = max(0.0, 35.0 - (volume_ratio - 1.0) * 30.0)
    else:
        score = 50.0

    return score


# ── Public API ─────────────────────────────────────────────────────────────────

def run_technical_analysis(
    ticker: str,
    bars: pd.DataFrame,
) -> TechnicalScore:
    """
    Run all technical sub-analyses and return a TechnicalScore.

    Args:
        ticker:   Asset symbol.
        bars:     OHLCV DataFrame with DatetimeIndex and float64 columns.
                  Minimum 60 bars recommended for reliable indicator output.
    """
    notes: list[str] = []

    if len(bars) < _MIN_BARS:
        notes.append(
            f"Only {len(bars)} bars available ({_MIN_BARS} recommended) — "
            "indicator reliability is reduced"
        )

    close   = bars["close"]
    current_price = float(close.iloc[-1])

    # ── RSI ──────────────────────────────────────────────────────
    rsi_14 = _compute_rsi(close, period=14)
    rsi_score = _rsi_to_score(rsi_14) if rsi_14 is not None else 50.0
    if rsi_14 is not None:
        notes.append(f"RSI(14): {rsi_14:.1f} → score {rsi_score:.1f}")

    # ── MACD ─────────────────────────────────────────────────────
    macd_line, signal_line, macd_histogram = _compute_macd(close)
    if macd_histogram is not None and macd_line is not None and signal_line is not None:
        macd_score = _macd_to_score(macd_line, signal_line, macd_histogram, close)
        notes.append(f"MACD histogram: {macd_histogram:.4f} → score {macd_score:.1f}")
    else:
        macd_score = 50.0
        notes.append("MACD unavailable (insufficient bars) — neutral 50")

    # ── Support / Resistance ──────────────────────────────────────
    sr_levels = _find_support_resistance(bars)
    sr_score  = _sr_to_score(current_price, sr_levels)
    supports    = [l for l in sr_levels if l.level_type == "support"]
    resistances = [l for l in sr_levels if l.level_type == "resistance"]
    if sr_levels:
        nearest_support    = max((l.price for l in supports if l.price < current_price), default=None)
        nearest_resistance = min((l.price for l in resistances if l.price > current_price), default=None)
        notes.append(
            f"Price: {current_price:.2f} | "
            f"Nearest support: {nearest_support or 'N/A'} | "
            f"Nearest resistance: {nearest_resistance or 'N/A'}"
        )

    # ── Volume ────────────────────────────────────────────────────
    volume_score = _compute_volume_score(bars)

    # ── Weighted composite ────────────────────────────────────────
    composite = (
        _W_RSI    * rsi_score    +
        _W_MACD   * macd_score   +
        _W_SR     * sr_score     +
        _W_VOLUME * volume_score
    )

    logger.info(
        "Technical analysis complete",
        extra={
            "ticker": ticker,
            "score": round(composite, 2),
            "rsi": round(rsi_score, 2),
            "macd": round(macd_score, 2),
            "sr": round(sr_score, 2),
            "volume": round(volume_score, 2),
        },
    )

    return TechnicalScore(
        ticker=ticker,
        score=round(composite, 2),
        rsi_score=round(rsi_score, 2),
        macd_score=round(macd_score, 2),
        sr_score=round(sr_score, 2),
        volume_score=round(volume_score, 2),
        rsi_14=round(rsi_14, 2) if rsi_14 is not None else None,
        macd_histogram=round(macd_histogram, 6) if macd_histogram is not None else None,
        macd_line=round(macd_line, 6) if macd_line is not None else None,
        signal_line=round(signal_line, 6) if signal_line is not None else None,
        current_price=round(current_price, 2),
        support_levels=supports,
        resistance_levels=resistances,
        analysis_notes=notes,
    )
