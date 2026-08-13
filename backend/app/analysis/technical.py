"""
app/analysis/technical.py  (Phase 6 rewrite — dynamic reweighting)
"""

import logging
import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
    _PANDAS_TA_AVAILABLE = True
except ImportError:
    _PANDAS_TA_AVAILABLE = False

from app.analysis.models import SupportResistanceLevel, TechnicalScore
from app.analysis.reweighting import WeightedSignal, reweight

logger = logging.getLogger("aureus.analysis.technical")

# Six sub-signals spanning momentum, trend structure, volatility position
# and participation. Weights sum to 1.0; the dynamic reweighting in
# reweighting.py redistributes any that can't be computed.
_W_RSI, _W_MACD, _W_SR, _W_VOLUME = 0.18, 0.22, 0.15, 0.10
_W_MA_ALIGN, _W_BBANDS = 0.23, 0.12
_MIN_BARS = 60


def _compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 5:
        return None
    if _PANDAS_TA_AVAILABLE:
        rsi_series = ta.rsi(close, length=period)
    else:
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
    if rsi <= 25: return 92.0
    if rsi <= 30: return 80.0 + (30.0 - rsi) / 5.0 * 12.0
    if rsi <= 50: return 50.0 + (50.0 - rsi) / 20.0 * 30.0
    if rsi <= 70: return 50.0 - (rsi - 50.0) / 20.0 * 25.0
    if rsi <= 75: return 25.0 - (rsi - 70.0) / 5.0 * 15.0
    return 10.0


def _compute_macd(close: pd.Series, fast=12, slow=26, signal=9) -> tuple[float | None, float | None, float | None]:
    if len(close) < slow + signal + 5:
        return None, None, None
    if _PANDAS_TA_AVAILABLE:
        result = ta.macd(close, fast=fast, slow=slow, signal=signal)
        if result is None or result.empty:
            return None, None, None
        macd_col, hist_col, sig_col = f"MACD_{fast}_{slow}_{signal}", f"MACDh_{fast}_{slow}_{signal}", f"MACDs_{fast}_{slow}_{signal}"
        last = result.iloc[-1]
        return (
            float(last[macd_col]) if pd.notna(last.get(macd_col)) else None,
            float(last[sig_col])  if pd.notna(last.get(sig_col))  else None,
            float(last[hist_col]) if pd.notna(last.get(hist_col)) else None,
        )
    ema_fast, ema_slow = close.ewm(span=fast, adjust=False).mean(), close.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return (
        float(macd_line.iloc[-1])  if pd.notna(macd_line.iloc[-1])  else None,
        float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else None,
        float(histogram.iloc[-1])  if pd.notna(histogram.iloc[-1])  else None,
    )


def _macd_to_score(macd_line: float, signal_line: float, histogram: float, close_prices: pd.Series) -> float:
    components: list[float] = [65.0 if histogram > 0 else 35.0]
    if _PANDAS_TA_AVAILABLE:
        hist_series = ta.macd(close_prices)
        if hist_series is not None and not hist_series.empty:
            hist_col = [c for c in hist_series.columns if c.startswith("MACDh")]
            if hist_col:
                recent = hist_series[hist_col[0]].dropna().tail(3)
                if len(recent) >= 2:
                    increasing = recent.iloc[-1] > recent.iloc[-2]
                    components.append(80.0 if (histogram > 0 and increasing) else 55.0 if histogram > 0
                                       else 20.0 if not increasing else 45.0)
    price_range = close_prices.tail(52).max() - close_prices.tail(52).min()
    if price_range > 0:
        strength_bonus = min(10.0, (abs(histogram) / price_range * 100) * 2)
        components.append(50.0 + (strength_bonus if histogram > 0 else -strength_bonus))
    return sum(components) / len(components)


def _find_support_resistance(df: pd.DataFrame, lookback_periods: int = 120, n_levels: int = 5) -> list[SupportResistanceLevel]:
    if len(df) < lookback_periods:
        lookback_periods = len(df)
    recent = df.tail(lookback_periods)
    highs, lows, window = recent["high"].values, recent["low"].values, 5
    support_pivots, resistance_pivots = [], []
    for i in range(window, len(lows) - window):
        if all(lows[i] <= lows[i-j] for j in range(1, window+1)) and all(lows[i] <= lows[i+j] for j in range(1, window+1)):
            support_pivots.append(float(lows[i]))
        if all(highs[i] >= highs[i-j] for j in range(1, window+1)) and all(highs[i] >= highs[i+j] for j in range(1, window+1)):
            resistance_pivots.append(float(highs[i]))

    def _cluster(pivots, level_type):
        if not pivots: return []
        levels, sorted_p, cluster = [], sorted(pivots), None
        cluster = [sorted_p[0]]
        for price in sorted_p[1:]:
            tolerance = cluster[0] * 0.015
            if price - cluster[-1] <= tolerance:
                cluster.append(price)
            else:
                c = sum(cluster) / len(cluster)
                levels.append(SupportResistanceLevel(price=round(c, 2), level_type=level_type, strength=float(len(cluster))))
                cluster = [price]
        if cluster:
            c = sum(cluster) / len(cluster)
            levels.append(SupportResistanceLevel(price=round(c, 2), level_type=level_type, strength=float(len(cluster))))
        return sorted(levels, key=lambda l: l.strength, reverse=True)[:n_levels]

    return _cluster(support_pivots, "support") + _cluster(resistance_pivots, "resistance")


def _sr_to_score(current_price: float, levels: list[SupportResistanceLevel]) -> float:
    if not levels or current_price <= 0:
        return 50.0
    supports    = [l for l in levels if l.level_type == "support"]
    resistances = [l for l in levels if l.level_type == "resistance"]
    support_below    = [l for l in supports if l.price < current_price]
    resistance_above = [l for l in resistances if l.price > current_price]
    score = 50.0
    if support_below:
        nearest = max(support_below, key=lambda l: l.price)
        pct = (current_price - nearest.price) / nearest.price
        score = (score + max(50.0, 95.0 - (pct / 0.15) * 45.0)) / 2
    if resistance_above:
        nearest = min(resistance_above, key=lambda l: l.price)
        pct = (nearest.price - current_price) / nearest.price
        score -= max(0.0, 45.0 - (pct / 0.15) * 45.0)
    return max(0.0, min(100.0, score))


def _compute_ma_alignment(close: pd.Series) -> tuple[float | None, dict]:
    """
    Score the 20/50/200 SMA stack.

    A textbook bullish alignment is price > SMA20 > SMA50 > SMA200: every
    horizon of buyer is in profit and each shorter average supports the next.
    Full bearish inversion is the mirror. Scoring the STACK rather than a
    single crossover is what makes this robust — an isolated crossover
    whipsaws constantly, whereas the ordering of all three only flips when a
    trend genuinely changes.
    """
    if len(close) < 200:
        # Fall back to the two averages we can compute, rather than dropping
        # the signal entirely on a stock with under a year of history.
        if len(close) < 50:
            return None, {}
        sma20, sma50 = close.rolling(20).mean().iloc[-1], close.rolling(50).mean().iloc[-1]
        px = float(close.iloc[-1])
        if any(pd.isna(v) for v in (sma20, sma50)):
            return None, {}
        score = 50.0 + (12.5 if px > sma20 else -12.5) + (12.5 if sma20 > sma50 else -12.5)
        return score, {"sma20": round(float(sma20), 2), "sma50": round(float(sma50), 2)}

    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])
    px = float(close.iloc[-1])
    if any(pd.isna(v) for v in (sma20, sma50, sma200)):
        return None, {}

    # Four independent orderings, each worth 12.5 points around a neutral 50.
    checks = [px > sma20, sma20 > sma50, sma50 > sma200, px > sma200]
    score = 50.0 + sum(12.5 if c else -12.5 for c in checks)
    return max(0.0, min(100.0, score)), {
        "sma20": round(sma20, 2), "sma50": round(sma50, 2), "sma200": round(sma200, 2),
    }


def _compute_bollinger_pctb(close: pd.Series, period: int = 20, k: float = 2.0) -> float | None:
    """
    Bollinger %B — where price sits inside its own volatility envelope.
    0 = lower band, 1 = upper band. Self-normalising, so it's comparable
    across tickers in a way a raw distance-from-average is not.
    """
    if len(close) < period + 2:
        return None
    ma = close.rolling(period).mean().iloc[-1]
    sd = close.rolling(period).std().iloc[-1]
    if pd.isna(ma) or pd.isna(sd) or sd == 0:
        return None
    upper, lower = ma + k * sd, ma - k * sd
    return float((float(close.iloc[-1]) - lower) / (upper - lower))


def _pctb_to_score(pctb: float) -> float:
    """
    Mean-reversion reading, matching how RSI is scored in this module:
    riding the lower band is the opportunity, the upper band is the risk.
    """
    if pctb <= 0.0:  return 90.0
    if pctb <= 0.2:  return 75.0 + (0.2 - pctb) / 0.2 * 15.0
    if pctb <= 0.8:  return 60.0 - (pctb - 0.2) / 0.6 * 20.0
    if pctb <= 1.0:  return 40.0 - (pctb - 0.8) / 0.2 * 25.0
    return 12.0


def _compute_atr_pct(df: pd.DataFrame, period: int = 14) -> float | None:
    """Average True Range as a % of price — comparable across tickers."""
    if len(df) < period + 2:
        return None
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    px = float(close.iloc[-1])
    if pd.isna(atr) or px <= 0:
        return None
    return float(atr) / px


def _compute_obv_trend(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """
    On-Balance Volume slope, normalised.

    OBV accumulates volume signed by the day's direction. Its SLOPE is the
    useful part: rising OBV while price is flat means accumulation is
    happening under the surface. The raw level is meaningless on its own
    because it depends entirely on an arbitrary starting point.
    """
    if len(df) < lookback + 5:
        return None
    direction = np.sign(df["close"].diff().fillna(0.0))
    obv = (direction * df["volume"]).cumsum()
    window = obv.iloc[-lookback:]
    if window.std() == 0:
        return None
    x = np.arange(len(window), dtype=float)
    slope = float(np.polyfit(x, window.to_numpy(float), 1)[0])
    denom = float(df["volume"].iloc[-lookback:].mean())
    return slope / denom if denom else None


def _compute_vwap_position(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """Price relative to rolling VWAP, as a fraction above/below."""
    if len(df) < lookback:
        return None
    seg = df.iloc[-lookback:]
    typical = (seg["high"] + seg["low"] + seg["close"]) / 3.0
    vol = seg["volume"]
    if vol.sum() <= 0:
        return None
    vwap = float((typical * vol).sum() / vol.sum())
    px = float(df["close"].iloc[-1])
    return (px - vwap) / vwap if vwap else None


def _compute_volume_score(df: pd.DataFrame) -> float:
    if len(df) < 25:
        return 50.0
    vol_5d, vol_20d = df["volume"].tail(5).mean(), df["volume"].tail(20).mean()
    price_trend_5d = df["close"].iloc[-1] - df["close"].iloc[-5]
    if vol_20d <= 0:
        return 50.0
    ratio = vol_5d / vol_20d
    if price_trend_5d > 0 and ratio > 1.1:
        return min(100.0, 65.0 + (ratio - 1.0) * 50.0)
    if price_trend_5d > 0:
        return 50.0
    if price_trend_5d < 0 and ratio > 1.1:
        return max(0.0, 35.0 - (ratio - 1.0) * 30.0)
    return 50.0


def run_technical_analysis(ticker: str, bars: pd.DataFrame) -> TechnicalScore:
    notes: list[str] = []
    signals: list[dict] = []
    if len(bars) < _MIN_BARS:
        notes.append(f"Only {len(bars)} bars available ({_MIN_BARS} recommended) — indicator reliability reduced")

    close = bars["close"]
    current_price = float(close.iloc[-1])

    rsi_14 = _compute_rsi(close, period=14)
    rsi_computed = rsi_14 is not None
    rsi_score = _rsi_to_score(rsi_14) if rsi_computed else 50.0
    if rsi_computed:
        notes.append(f"RSI(14) {rsi_14:.1f} → momentum component {rsi_score:.0f}/100")
        rsi_desc = "deeply oversold, a classic mean-reversion setup" if rsi_14 <= 30 else \
                   "deeply overbought, elevated pullback risk" if rsi_14 >= 70 else "in a neutral range"
        signals.append({"label": "RSI (14)", "score": rsi_score, "detail": f"RSI at {rsi_14:.0f} is {rsi_desc}"})
    else:
        notes.append("RSI unavailable (insufficient bars) — excluded from composite")

    macd_line, signal_line, macd_histogram = _compute_macd(close)
    macd_computed = macd_histogram is not None
    macd_score = _macd_to_score(macd_line, signal_line, macd_histogram, close) if macd_computed else 50.0
    if macd_computed:
        notes.append(f"MACD histogram {macd_histogram:.4f} → trend component {macd_score:.0f}/100")
        macd_dir = "accelerating upward momentum" if macd_histogram > 0 else "accelerating downward momentum"
        signals.append({"label": "MACD", "score": macd_score, "detail": f"MACD histogram signals {macd_dir}"})
    else:
        notes.append("MACD unavailable (insufficient bars) — excluded from composite")

    sr_levels = _find_support_resistance(bars)
    sr_computed = len(sr_levels) > 0
    sr_score = _sr_to_score(current_price, sr_levels) if sr_computed else 50.0
    supports    = [l for l in sr_levels if l.level_type == "support"]
    resistances = [l for l in sr_levels if l.level_type == "resistance"]
    if sr_computed:
        ns = max((l.price for l in supports if l.price < current_price), default=None)
        nr = min((l.price for l in resistances if l.price > current_price), default=None)
        notes.append(f"Price ${current_price:.2f} vs support {ns or 'n/a'} / resistance {nr or 'n/a'} → S/R component {sr_score:.0f}/100")
        sr_detail = f"trading near support (${ns:.2f})" if ns and (current_price - ns) / current_price < 0.03 else \
                    f"trading near resistance (${nr:.2f})" if nr and (nr - current_price) / current_price < 0.03 else \
                    "positioned between clear support and resistance levels"
        signals.append({"label": "Support/Resistance", "score": sr_score, "detail": f"Price action is {sr_detail}"})
    else:
        notes.append("No clear support/resistance levels found — excluded from composite")

    volume_computed = len(bars) >= 25
    volume_score = _compute_volume_score(bars) if volume_computed else 50.0
    if volume_computed:
        notes.append(f"Volume trend component {volume_score:.0f}/100")
        if volume_score >= 65 or volume_score <= 35:
            signals.append({"label": "Volume Trend", "score": volume_score, "detail": "Recent price moves are confirmed by above-average volume" if volume_score >= 65 else "Recent price moves lack strong volume confirmation"})

    # ── Moving-average alignment (20/50/200 stack) ────────────────────
    ma_score, ma_levels = _compute_ma_alignment(close)
    ma_computed = ma_score is not None
    if ma_computed:
        stack = " > ".join(
            f"{k.upper()} {v}" for k, v in sorted(ma_levels.items(), key=lambda kv: kv[1], reverse=True)
        )
        notes.append(f"Moving-average alignment → trend-structure component {ma_score:.0f}/100 ({stack})")
        signals.append({
            "label": "MA Alignment (20/50/200)", "score": ma_score,
            "detail": (f"Price ${current_price:.2f} against {stack} — "
                       + ("a bullish stack with every horizon of buyer onside"
                          if ma_score >= 70 else
                          "a bearish stack with shorter averages below longer ones"
                          if ma_score <= 30 else
                          "a mixed stack, with the averages not yet in agreement")),
        })
    else:
        ma_score = 50.0
        notes.append("Moving-average alignment unavailable (insufficient history) — excluded from composite")

    # ── Bollinger %B (position inside the volatility envelope) ────────
    pctb = _compute_bollinger_pctb(close)
    bb_computed = pctb is not None
    bb_score = _pctb_to_score(pctb) if bb_computed else 50.0
    if bb_computed:
        notes.append(f"Bollinger %B {pctb:.2f} → volatility-position component {bb_score:.0f}/100")
        where = ("above the upper band — statistically stretched" if pctb > 1 else
                 "riding the upper band" if pctb > 0.8 else
                 "below the lower band — statistically stretched to the downside" if pctb < 0 else
                 "hugging the lower band" if pctb < 0.2 else "mid-envelope")
        signals.append({"label": "Bollinger %B", "score": bb_score,
                        "detail": f"Price is {where} (%B {pctb:.2f})"})

    # ── Context-only readings: ATR, OBV, VWAP ─────────────────────────
    # These describe the environment rather than express a directional view,
    # so they enrich the narrative and the metrics grid without being scored.
    # Folding a volatility LEVEL into a directional composite would be a
    # category error: high ATR is neither bullish nor bearish on its own.
    atr_pct = _compute_atr_pct(bars)
    obv_slope = _compute_obv_trend(bars)
    vwap_pos = _compute_vwap_position(bars)

    if atr_pct is not None:
        notes.append(f"ATR(14) is {atr_pct * 100:.2f}% of price — typical daily range")
    if obv_slope is not None:
        signals.append({
            "label": "On-Balance Volume", "score": 65.0 if obv_slope > 0 else 35.0,
            "detail": ("OBV is rising — volume is accumulating on up-days"
                       if obv_slope > 0 else
                       "OBV is falling — volume is concentrated in down-days"),
        })
    if vwap_pos is not None:
        signals.append({
            "label": "VWAP Position", "score": 60.0 if vwap_pos > 0 else 40.0,
            "detail": (f"Trading {abs(vwap_pos) * 100:.1f}% "
                       f"{'above' if vwap_pos > 0 else 'below'} its 20-session VWAP"),
        })

    result = reweight([
        WeightedSignal("rsi_score",    rsi_score,    _W_RSI,      rsi_computed),
        WeightedSignal("macd_score",   macd_score,   _W_MACD,     macd_computed),
        WeightedSignal("ma_alignment", ma_score,     _W_MA_ALIGN, ma_computed),
        WeightedSignal("bollinger_pctb", bb_score,   _W_BBANDS,   bb_computed),
        WeightedSignal("sr_score",     sr_score,     _W_SR,       sr_computed),
        WeightedSignal("volume_score", volume_score, _W_VOLUME,   volume_computed),
    ])
    if result.dropped_signals:
        notes.append(f"Excluded from scoring (no real data): {', '.join(result.dropped_signals)}")

    logger.info("Technical analysis complete", extra={
        "ticker": ticker, "score": result.composite_score, "data_completeness": result.data_completeness,
    })

    return TechnicalScore(
        ticker=ticker, score=result.composite_score,
        rsi_score=round(rsi_score, 2), macd_score=round(macd_score, 2),
        sr_score=round(sr_score, 2), volume_score=round(volume_score, 2),
        rsi_14=round(rsi_14, 2) if rsi_14 is not None else None,
        macd_histogram=round(macd_histogram, 6) if macd_histogram is not None else None,
        macd_line=round(macd_line, 6) if macd_line is not None else None,
        signal_line=round(signal_line, 6) if signal_line is not None else None,
        current_price=round(current_price, 2),
        data_completeness=result.data_completeness,
        effective_weights=result.effective_weights,
        signal_breakdown=signals,
        support_levels=supports, resistance_levels=resistances,
        analysis_notes=notes,
    )
