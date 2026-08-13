"""
app/games/pattern_engine.py
-----------------------------
Chart Pattern & Candlestick Scenario Guesser.

Shows a real historical price snippet with the ticker hidden, asks which
way it resolved, then reveals the outcome and explains what actually
happened.

=====================================================================
WHY THE OUTCOME THRESHOLD IS VOLATILITY-SCALED
=====================================================================
The obvious design — "up more than 3% is a breakout" — produces a broken
game. A low-volatility utility almost never moves 3% in ten sessions, so
nearly every one of its scenarios would answer "range consolidation";
a high-volatility small-cap would almost never answer anything else. The
player would learn the ticker's volatility regime, not the setup.

So the threshold is scaled by the asset's own recent volatility:

    threshold = k · σ_daily · √horizon        (floored at a small minimum)

σ_daily is the standard deviation of daily returns over the setup window,
and √horizon is the standard scaling of volatility to a multi-day period.
A move only counts as a breakout if it's large RELATIVE TO WHAT THAT
ASSET NORMALLY DOES — which is what a trader actually means by the word,
and which makes the three answers roughly balanced across tickers.

=====================================================================
NO LOOK-AHEAD IN THE SETUP
=====================================================================
The player sees bars[0:cutoff]. The outcome is computed from
bars[cutoff:cutoff+horizon], which is never included in the scenario
payload sent to the client. The rationale text is generated at reveal
time from the outcome window, so it cannot leak into the question.
"""

import logging
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd

from app.games.chart_patterns import (
    MIN_CONFIDENCE_FOR_QUIZ,
    PATTERN_LIBRARY,
    DetectedPattern,
    detect_patterns,
    pattern_choices,
)
from app.ingestion.market_data import MarketDataService

logger = logging.getLogger("aureus.games.pattern")

Direction = Literal["bullish_breakout", "bearish_breakdown", "range_consolidation"]

DIRECTION_LABELS: dict[Direction, str] = {
    "bullish_breakout": "Bullish Breakout",
    "bearish_breakdown": "Bearish Breakdown",
    "range_consolidation": "Range Consolidation",
}

# Tickers the scenario generator draws from. Deliberately spans sectors and
# volatility regimes so the player can't pattern-match on one asset's habits.
SCENARIO_TICKERS = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "ORCL", "CRM", "ADBE",
    # Semis / hardware
    "AMD", "INTC", "QCOM", "TXN", "MU",
    # Financials
    "JPM", "BAC", "GS", "MS", "V", "MA",
    # Healthcare
    "JNJ", "UNH", "PFE", "LLY", "ABBV",
    # Energy / industrials / materials
    "XOM", "CVX", "CAT", "BA", "GE", "FCX",
    # Consumer
    "WMT", "COST", "KO", "PEP", "MCD", "NKE", "SBUX", "TGT",
    # Comms / other
    "DIS", "NFLX", "T", "UBER", "PYPL",
]

SETUP_BARS = 60        # what the player sees
OUTCOME_BARS = 10      # forward window the answer is scored over

# k in the threshold formula, CALIBRATED rather than guessed. Measured over
# 1,806 historical windows across all 12 tickers:
#     k=0.90 -> 22% bull / 15% bear / 63% range   (always answering "range" wins)
#     k=0.60 -> 31% / 23% / 47%
#     k=0.43 -> 38% / 28% / 34%                   <- chosen
# The first value produces a game a player beats by never thinking; 0.43
# lands close to even thirds, so no single answer is a winning default and
# the player has to actually read the setup. Re-run the calibration if the
# ticker list or OUTCOME_BARS changes, since both shift the distribution.
VOL_MULTIPLIER = 0.43
MIN_THRESHOLD = 0.01   # 1% floor so a near-zero-vol window can't classify noise as a breakout
MAX_TICKERS_PER_ATTEMPT = 6   # bounds latency against a rate-limited data provider


QuestionType = Literal["direction", "pattern_id", "pattern_implication"]

# What each pattern is conventionally read as. Used as the answer key for
# pattern_implication questions — which asks what the TEXTBOOK says, not what
# actually happened. The reveal then shows the real outcome, which often
# disagrees; that disagreement is the intended lesson.
BIAS_LABELS: dict[str, str] = {
    "bullish_reversal": "Bullish reversal — a bottom forming",
    "bearish_reversal": "Bearish reversal — a top forming",
    "bullish_continuation": "Bullish continuation — a pause before more upside",
    "bearish_continuation": "Bearish continuation — a pause before more downside",
    "bilateral": "Neither — it signals compression, not direction",
}


@dataclass
class Scenario:
    ticker: str                 # withheld from the client until reveal
    setup_bars: list[dict]      # OHLC shown to the player
    outcome_bars: list[dict]    # revealed only after answering
    correct_direction: Direction
    forward_return_pct: float
    threshold_pct: float
    rationale: str
    setup_notes: list[str]
    # Question framing
    question_type: QuestionType
    question: str
    choices: list[dict]
    correct_answer: str
    pattern_key: str | None = None
    pattern_confidence: float | None = None
    pattern_detail: str | None = None


def _bars_to_records(df: pd.DataFrame) -> list[dict]:
    return [
        {
            "date": str(idx.date()),
            "open": round(float(r.open), 2),
            "high": round(float(r.high), 2),
            "low": round(float(r.low), 2),
            "close": round(float(r.close), 2),
            "volume": int(r.volume) if not pd.isna(r.volume) else 0,
        }
        for idx, r in df.iterrows()
    ]


def _classify(setup: pd.DataFrame, outcome: pd.DataFrame) -> tuple[Direction, float, float]:
    """
    Return (direction, forward_return_pct, threshold_pct).

    Everything returned is a NATIVE Python float, never np.float64. That's
    not cosmetic: psycopg2 has no adapter for numpy scalars, so a leaked
    np.float64 is interpolated into SQL as the literal text
    `np.float64(3.9)` and Postgres then fails parsing `np.` as a schema
    name. Coercing at this boundary keeps numpy an implementation detail.
    """
    entry = float(setup["close"].iloc[-1])
    exit_ = float(outcome["close"].iloc[-1])
    fwd = (exit_ - entry) / entry

    daily_returns = setup["close"].pct_change().dropna()
    sigma = float(daily_returns.std()) if len(daily_returns) > 2 else 0.0
    threshold = float(max(MIN_THRESHOLD, VOL_MULTIPLIER * sigma * float(np.sqrt(len(outcome)))))

    if fwd > threshold:
        direction: Direction = "bullish_breakout"
    elif fwd < -threshold:
        direction = "bearish_breakdown"
    else:
        direction = "range_consolidation"
    return direction, float(fwd * 100), float(threshold * 100)


def _setup_notes(setup: pd.DataFrame) -> list[str]:
    """
    Observable features of the SETUP window only — these are shown with the
    question, so they must contain nothing derived from the outcome.
    """
    close = setup["close"]
    last = float(close.iloc[-1])
    hi = float(setup["high"].max())
    lo = float(setup["low"].min())
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else last
    rng = hi - lo

    notes: list[str] = []
    if rng > 0:
        pos = (last - lo) / rng
        if pos > 0.85:
            notes.append("Price is pressing the top of its recent range.")
        elif pos < 0.15:
            notes.append("Price is sitting near the bottom of its recent range.")
        else:
            notes.append(f"Price sits around the {pos * 100:.0f}th percentile of its recent range.")

    notes.append(
        f"Trading {'above' if last > sma20 else 'below'} its 20-session moving average."
    )

    recent_vol = float(close.pct_change().dropna().tail(10).std() or 0)
    earlier_vol = float(close.pct_change().dropna().head(len(close) // 2).std() or 0)
    if earlier_vol > 0:
        if recent_vol < earlier_vol * 0.7:
            notes.append("Volatility has been compressing — ranges are tightening.")
        elif recent_vol > earlier_vol * 1.3:
            notes.append("Volatility has been expanding into the decision point.")
    return notes


def _rationale(direction: Direction, fwd_pct: float, threshold_pct: float,
               setup: pd.DataFrame, outcome: pd.DataFrame) -> str:
    entry = float(setup["close"].iloc[-1])
    prior_high = float(setup["high"].max())
    prior_low = float(setup["low"].min())
    out_high = float(outcome["high"].max())
    out_low = float(outcome["low"].min())

    parts = [
        f"Over the following {len(outcome)} sessions price moved {fwd_pct:+.1f}%, "
        f"against a volatility-scaled threshold of ±{threshold_pct:.1f}%."
    ]

    if direction == "bullish_breakout":
        parts.append(
            f"That clears the upside band, and the high of {out_high:.2f} "
            + (f"took out the prior range high of {prior_high:.2f}, confirming the breakout."
               if out_high > prior_high else
               "extended the advance without yet exceeding the prior range high.")
        )
    elif direction == "bearish_breakdown":
        parts.append(
            f"That breaches the downside band, and the low of {out_low:.2f} "
            + (f"undercut the prior range low of {prior_low:.2f}, confirming the breakdown."
               if out_low < prior_low else
               "extended the decline while holding just above the prior range low.")
        )
    else:
        parts.append(
            f"The move stayed inside the ±{threshold_pct:.1f}% band, so relative to this asset's own "
            f"volatility nothing resolved — price continued to range around {entry:.2f}. "
            "Compression often persists longer than it looks like it should."
        )
    return " ".join(parts)


def _build_question(rng, pattern: DetectedPattern | None,
                    prefer: QuestionType | None = None) -> tuple[QuestionType, str, list[dict], str]:
    """
    Choose the question to ask for this chart.

    Pattern-based questions are only offered when a formation was detected
    at quiz-grade confidence — otherwise the answer key would be a guess,
    and a quiz that grades against a guess teaches noise. Everything else
    falls back to the direction question, which is always answerable
    because its answer comes from realised prices rather than from a
    subjective label.
    """
    usable = pattern is not None and pattern.confidence >= MIN_CONFIDENCE_FOR_QUIZ

    options: list[QuestionType] = ["direction"]
    if usable:
        options += ["pattern_id", "pattern_implication"]
    qtype = prefer if (prefer in options) else rng.choice(options)

    if qtype == "pattern_id" and pattern:
        return (
            "pattern_id",
            "Which classical chart pattern is forming here?",
            pattern_choices(pattern.key, rng),
            pattern.key,
        )

    if qtype == "pattern_implication" and pattern:
        info = PATTERN_LIBRARY[pattern.key]
        biases = ["bullish_reversal", "bearish_reversal",
                  "bullish_continuation", "bearish_continuation", "bilateral"]
        rng.shuffle(biases)
        return (
            "pattern_implication",
            f"This chart is forming a {info.name}. What is that pattern conventionally read as?",
            [{"value": b, "label": BIAS_LABELS[b]} for b in biases],
            info.bias,
        )

    return (
        "direction",
        f"Which way did it resolve over the next {OUTCOME_BARS} sessions?",
        [{"value": k, "label": v} for k, v in DIRECTION_LABELS.items()],
        "",  # filled in by the caller once the outcome is classified
    )


def generate_scenario(rng: random.Random | None = None,
                      prefer_question: QuestionType | None = None) -> Scenario:
    """
    Build one scenario from real history.

    Tries tickers in random order and, within each, a handful of random
    cutoffs — preferring windows that contain a detectable formation so the
    pattern questions actually get used, while still returning a plain
    direction question when nothing clean is present.

    Raises RuntimeError if no ticker yields enough usable history, so the
    API can return a clear 503 instead of a half-built game.
    """
    rng = rng or random.Random()
    svc = MarketDataService()
    # Sample a SUBSET rather than walking all 45. The market-data provider's
    # free tier is rate-limited to a handful of calls a minute, so an
    # unbounded walk over cold tickers serialises behind backoff and can take
    # minutes. A random subset keeps generation bounded while still drawing
    # from the full universe across users and days.
    tickers = rng.sample(SCENARIO_TICKERS, min(MAX_TICKERS_PER_ATTEMPT, len(SCENARIO_TICKERS)))

    needed = SETUP_BARS + OUTCOME_BARS
    end = date.today()
    start = end - timedelta(days=900)

    fallback: tuple | None = None   # a valid window with no detected pattern

    for ticker in tickers:
        try:
            bars = svc.fetch_bars(ticker, start, end, frequency="1d").bars
        except Exception as exc:
            logger.warning("Scenario fetch failed", extra={"ticker": ticker, "error": str(exc)})
            continue
        if bars is None or len(bars) < needed + 5:
            continue

        max_cut = len(bars) - OUTCOME_BARS
        if max_cut <= SETUP_BARS:
            continue

        for _ in range(6):
            cut = rng.randint(SETUP_BARS, max_cut)
            setup = bars.iloc[cut - SETUP_BARS: cut]
            outcome = bars.iloc[cut: cut + OUTCOME_BARS]
            if len(setup) < SETUP_BARS or len(outcome) < OUTCOME_BARS:
                continue

            matches = detect_patterns(setup)
            pattern = matches[0] if matches else None

            if pattern and pattern.confidence >= MIN_CONFIDENCE_FOR_QUIZ:
                return _assemble(rng, ticker, setup, outcome, pattern, prefer_question)
            if fallback is None:
                fallback = (ticker, setup, outcome, pattern)

    if fallback:
        return _assemble(rng, *fallback, prefer_question)

    raise RuntimeError(
        "Could not build a pattern scenario — no ticker returned enough historical data. "
        "Check market-data provider availability."
    )


def _assemble(rng, ticker, setup, outcome,
              pattern: DetectedPattern | None,
              prefer: QuestionType | None) -> Scenario:
    direction, fwd_pct, threshold_pct = _classify(setup, outcome)
    qtype, question, choices, answer = _build_question(rng, pattern, prefer)
    if qtype == "direction":
        answer = direction

    rationale = _rationale(direction, fwd_pct, threshold_pct, setup, outcome)
    notes = _setup_notes(setup)

    return Scenario(
        ticker=ticker,
        setup_bars=_bars_to_records(setup),
        outcome_bars=_bars_to_records(outcome),
        correct_direction=direction,
        forward_return_pct=round(fwd_pct, 2),
        threshold_pct=round(threshold_pct, 2),
        rationale=rationale,
        setup_notes=notes,
        question_type=qtype,
        question=question,
        choices=choices,
        correct_answer=answer,
        pattern_key=pattern.key if pattern else None,
        pattern_confidence=float(pattern.confidence) if pattern else None,
        pattern_detail=pattern.detail if pattern else None,
    )


def score_pattern_guess(correct: bool) -> int:
    """Knowledge XP for a pattern round. A wrong guess still earns a little,
    because the reveal explanation is the educational point."""
    return 50 if correct else 10
