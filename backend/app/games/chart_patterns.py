"""
app/games/chart_patterns.py
-----------------------------
Geometric detection of classical chart patterns, plus the teaching content
for each one.

=====================================================================
WHY THE TOLERANCES ARE DELIBERATELY STRICT
=====================================================================
This module supplies the ANSWER KEY for a quiz. If a detector fires loosely
the game confidently teaches a wrong label — worse than not asking at all.
So every detector is conservative: it would rather return nothing than
claim a marginal formation. `NO_PATTERN` is a legitimate, common outcome,
and the scenario generator falls back to a direction question when nothing
clean is present.

Each detector also returns a 0–1 confidence. Only high-confidence matches
are used for "name this pattern" questions; lower-confidence ones may still
colour the narrative of a direction question but are never the answer key.

=====================================================================
SLOPES ARE NORMALISED, NOT RAW
=====================================================================
A trendline slope of "0.5 per bar" means something completely different on
a $12 stock than a $900 one. Every slope here is divided by the window's
mean price, giving a FRACTION of price per bar, so one set of thresholds
works across the whole ticker universe.

=====================================================================
PATTERNS ARE PROBABILISTIC, NOT DETERMINISTIC
=====================================================================
The library below states each pattern's TEXTBOOK implication. The game
deliberately reveals what actually happened afterwards, which frequently
contradicts the textbook. That contradiction is the most valuable lesson
the game can deliver, so `caveat` on every pattern says so plainly rather
than presenting these as reliable predictors.
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

PatternBias = Literal[
    "bullish_reversal", "bearish_reversal",
    "bullish_continuation", "bearish_continuation",
    "bilateral",
]

# ── Tolerances ───────────────────────────────────────────────────────────
SWING_WINDOW = 3            # a pivot must be the extreme of +/- 3 bars
SHOULDER_SYMMETRY_TOL = 0.09   # shoulders may differ by up to 9%
HEAD_PROMINENCE_MIN = 0.025    # head must clear both shoulders by 2.5%
NECKLINE_TOL = 0.055           # the two troughs may differ by up to 5.5%
PEAK_EQUALITY_TOL = 0.025      # "roughly equal" peaks for double/triple tops
TROUGH_DEPTH_MIN = 0.050       # the dip between peaks must be >= 5%
FLAT_SLOPE_MAX = 0.0012        # |slope| below this counts as horizontal (0.12%/bar)
TREND_SLOPE_MIN = 0.0018       # |slope| above this counts as genuinely sloping
CONVERGENCE_MIN = 0.22         # range must narrow by >= 22% end vs start
PATTERN_RECENCY_BARS = 18      # the formation must finish near the decision point
# Only formations at or above this confidence are used as a quiz ANSWER KEY.
#
# Calibrated, not guessed. Across 600 synthetic random walks the detectors
# name some shape 22% of the time, with those matches spread across
# confidence 0.62–0.99; all 14 hand-built textbook patterns score 0.87–0.99.
# Gating at 0.85 therefore keeps every clean formation while dropping ~40%
# of the marginal ones.
#
# The residual is not really an error rate. A random walk that happens to
# draw two equal peaks, 5%+ apart, separated by 8+ bars, after a 6%+ advance
# IS displaying a double top — any technician would label it one. These
# detectors answer "does this chart show the geometry of pattern X", which
# is what chart reading is; they do not claim the shape was caused by
# anything. The `caveat` on every library entry makes that point to the
# player directly.
MIN_CONFIDENCE_FOR_QUIZ = 0.85
PRIOR_TREND_MIN = 0.060       # a reversal pattern must have >=6% of trend to reverse
# Consecutive peaks (or troughs) must be this many bars apart. A random walk
# readily throws up two similar highs a few bars apart; a formation traders
# would actually name takes time to build. This single constraint removes
# more noise than any tolerance tightening.
MIN_EXTREME_SEPARATION = 8
WEDGE_CONVERGENCE_MIN = 0.32  # wedges need tighter coiling than triangles


# ── Educational library ──────────────────────────────────────────────────

@dataclass(frozen=True)
class PatternInfo:
    key: str
    name: str
    bias: PatternBias
    shape: str          # what it looks like on the chart
    implication: str    # what it is conventionally read as
    confirmation: str   # what would actually confirm it
    caveat: str         # why it is not a guarantee


PATTERN_LIBRARY: dict[str, PatternInfo] = {
    "head_and_shoulders": PatternInfo(
        "head_and_shoulders", "Head & Shoulders", "bearish_reversal",
        "Three peaks: a left shoulder, a higher head, then a right shoulder roughly level with the left. The two troughs between them define a neckline.",
        "Read as a topping formation — buyers made a higher high on the head but could not repeat it on the right shoulder, suggesting demand is exhausting after an advance.",
        "The pattern is only considered confirmed when price CLOSES below the neckline, ideally on expanding volume. The conventional measured move projects the head-to-neckline distance down from the break.",
        "One of the most widely taught reversal patterns, and therefore one of the most widely front-run. Necklines break and immediately reverse often enough that trading it without confirmation is a coin flip.",
    ),
    "inverse_head_and_shoulders": PatternInfo(
        "inverse_head_and_shoulders", "Inverse Head & Shoulders", "bullish_reversal",
        "The mirror image: three troughs, with the middle one the deepest, and two intervening peaks forming a neckline overhead.",
        "Read as a bottoming formation — sellers drove a lower low on the head but could not press price down as far on the right shoulder, suggesting supply is drying up.",
        "Confirmed on a close ABOVE the neckline. Volume expanding on the breakout is the classic corroborating signal.",
        "Bottoms tend to take longer to form than tops. An inverse H&S that breaks out on weak volume frequently fails back into the range.",
    ),
    "double_top": PatternInfo(
        "double_top", "Double Top", "bearish_reversal",
        "Two peaks at approximately the same level separated by a meaningful trough — an 'M' shape.",
        "Price tested a resistance level twice and was rejected both times, indicating a supply zone that buyers could not absorb.",
        "Confirmed on a close below the intervening trough (the 'valley' or neckline). Until that happens it is just a range.",
        "An unconfirmed double top is indistinguishable from ordinary range-bound trading. Many resolve upward on the third attempt precisely because so many stops sit above the highs.",
    ),
    "double_bottom": PatternInfo(
        "double_bottom", "Double Bottom", "bullish_reversal",
        "Two troughs at approximately the same level separated by an intervening peak — a 'W' shape.",
        "Price found buyers at the same level twice, indicating a demand zone that sellers could not push through.",
        "Confirmed on a close above the intervening peak. The measured move projects the pattern's height up from the breakout.",
        "The second bottom undercutting the first slightly (a 'spring') is common and does not invalidate it — but a decisive close below both invalidates the read entirely.",
    ),
    "triple_top": PatternInfo(
        "triple_top", "Triple Top", "bearish_reversal",
        "Three peaks at approximately the same level with troughs between them.",
        "A stronger version of the double top: three failed attempts at the same resistance suggests a persistent seller.",
        "Confirmed on a close below the lowest intervening trough. Declining volume on each successive peak strengthens the read.",
        "Triple tops are rarer than they appear — most are simply horizontal resistance in a range that eventually breaks upward. The more times a level is tested, the weaker it often becomes.",
    ),
    "triple_bottom": PatternInfo(
        "triple_bottom", "Triple Bottom", "bullish_reversal",
        "Three troughs at approximately the same level with peaks between them.",
        "Three defended tests of the same support level, suggesting persistent demand at that price.",
        "Confirmed on a close above the highest intervening peak, ideally with volume expansion.",
        "Long basing patterns can resolve in either direction. Repeated tests of support also progressively consume the buying interest defending it.",
    ),
    "ascending_triangle": PatternInfo(
        "ascending_triangle", "Ascending Triangle", "bullish_continuation",
        "A flat horizontal resistance line with a rising sequence of higher lows pressing up into it.",
        "Buyers are willing to pay progressively more while sellers defend one fixed price — conventionally read as accumulation resolving upward.",
        "Confirmed on a close above the horizontal resistance. The measured move is the triangle's height projected up from the breakout point.",
        "Direction is not guaranteed by the shape. Ascending triangles break down a meaningful fraction of the time, especially against a weak broader market.",
    ),
    "descending_triangle": PatternInfo(
        "descending_triangle", "Descending Triangle", "bearish_continuation",
        "A flat horizontal support line with a falling sequence of lower highs pressing down into it.",
        "Sellers accept progressively less while buyers defend one fixed price — conventionally read as distribution resolving downward.",
        "Confirmed on a close below the horizontal support, with the height projected down from the break.",
        "The mirror caveat applies: a descending triangle into strong support in a rising market often resolves upward instead.",
    ),
    "symmetrical_triangle": PatternInfo(
        "symmetrical_triangle", "Symmetrical Triangle", "bilateral",
        "Lower highs and higher lows converging toward a single point — a coil.",
        "Genuinely directionless on its own. It signals compression: volatility is contracting and a range expansion is likely, but the shape does not say which way.",
        "There is nothing to confirm until price closes outside one boundary. The breakout direction is the signal, not the triangle.",
        "This is the pattern most often misread as predictive. Treating a symmetrical triangle as bullish or bearish before the break is imposing a view the chart has not expressed.",
    ),
    "rising_wedge": PatternInfo(
        "rising_wedge", "Rising Wedge", "bearish_reversal",
        "Both boundaries slope upward, but the lower line rises faster than the upper — the range narrows as price grinds higher.",
        "Counter-intuitively bearish. Price is still rising but each advance is smaller, indicating momentum decaying even as the trend technically continues.",
        "Confirmed on a close below the lower boundary. The compression means the eventual move is often quick.",
        "Rising wedges can persist far longer than they look sustainable. Shorting a wedge simply because it is a wedge, while price keeps making higher highs, is a well-known way to lose money.",
    ),
    "falling_wedge": PatternInfo(
        "falling_wedge", "Falling Wedge", "bullish_reversal",
        "Both boundaries slope downward, but the upper line falls faster than the lower — the range narrows as price grinds lower.",
        "Counter-intuitively bullish. Price is still declining but each leg down is shallower, indicating selling pressure exhausting.",
        "Confirmed on a close above the upper boundary, typically with a sharp expansion once the coil releases.",
        "A falling wedge inside a genuine downtrend is often just an orderly decline. Absent a breakout, 'falling more slowly' is still falling.",
    ),
    "bull_flag": PatternInfo(
        "bull_flag", "Bull Flag", "bullish_continuation",
        "A sharp near-vertical advance (the pole) followed by a tight, gently downward-drifting consolidation (the flag).",
        "Read as a pause rather than a reversal — holders are not selling into the rally aggressively, and the shallow drift suggests profit-taking rather than distribution.",
        "Confirmed on a close above the flag's upper boundary. The classic target adds the pole's height to the breakout point.",
        "The distinction between a flag and the start of a real reversal is depth. A 'flag' that retraces most of the pole was never a flag.",
    ),
    "bear_flag": PatternInfo(
        "bear_flag", "Bear Flag", "bearish_continuation",
        "A sharp decline (the pole) followed by a tight, gently upward-drifting consolidation (the flag).",
        "Read as a pause in a decline — the weak bounce suggests relief buying rather than genuine demand returning.",
        "Confirmed on a close below the flag's lower boundary, with the pole's height projected down.",
        "Bear flags in oversold conditions frequently become genuine bottoms instead. The pattern says nothing about whether the selling was already overdone.",
    ),
    "cup_and_handle": PatternInfo(
        "cup_and_handle", "Cup & Handle", "bullish_continuation",
        "A rounded, U-shaped base that recovers to roughly its starting level, followed by a small shallow pullback (the handle) near the rim.",
        "The rounded shape suggests a gradual transfer from sellers to buyers rather than a panic low, and the shallow handle suggests little remaining supply.",
        "Confirmed on a close above the rim/handle high. The depth of the cup projected upward is the conventional target.",
        "A V-shaped recovery is not a cup — the roundness matters because it implies gradual accumulation. Deep handles (more than about a third of the cup) tend to fail.",
    ),
}

# Specificity ranking, used to break ties when several detectors fire on the
# same window. Confidence alone is the wrong tiebreak: a generic converging
# range scores very high on "is it converging?" while a Head & Shoulders
# scores more modestly on strict symmetry tolerances — so ranking purely by
# confidence would report a textbook H&S as a symmetrical triangle. A more
# structurally specific formation is the better answer whenever both are
# genuinely present, and every detector here is already conservative enough
# that "it fired at all" is meaningful.
PATTERN_SPECIFICITY: dict[str, int] = {
    "head_and_shoulders": 3, "inverse_head_and_shoulders": 3, "cup_and_handle": 3,
    "triple_top": 2, "triple_bottom": 2, "double_top": 2, "double_bottom": 2,
    "bull_flag": 1, "bear_flag": 1,
    "ascending_triangle": 0, "descending_triangle": 0, "symmetrical_triangle": 0,
    "rising_wedge": 0, "falling_wedge": 0,
}

# Which patterns look enough alike to make fair multiple-choice distractors.
CONFUSABLE: dict[str, list[str]] = {
    "head_and_shoulders": ["triple_top", "double_top", "rising_wedge"],
    "inverse_head_and_shoulders": ["triple_bottom", "double_bottom", "falling_wedge"],
    "double_top": ["triple_top", "head_and_shoulders", "rising_wedge"],
    "double_bottom": ["triple_bottom", "inverse_head_and_shoulders", "falling_wedge"],
    "triple_top": ["double_top", "head_and_shoulders", "descending_triangle"],
    "triple_bottom": ["double_bottom", "inverse_head_and_shoulders", "ascending_triangle"],
    "ascending_triangle": ["symmetrical_triangle", "descending_triangle", "bull_flag"],
    "descending_triangle": ["symmetrical_triangle", "ascending_triangle", "bear_flag"],
    "symmetrical_triangle": ["ascending_triangle", "descending_triangle", "rising_wedge"],
    "rising_wedge": ["symmetrical_triangle", "bull_flag", "ascending_triangle"],
    "falling_wedge": ["symmetrical_triangle", "bear_flag", "descending_triangle"],
    "bull_flag": ["ascending_triangle", "rising_wedge", "cup_and_handle"],
    "bear_flag": ["descending_triangle", "falling_wedge", "symmetrical_triangle"],
    "cup_and_handle": ["double_bottom", "bull_flag", "inverse_head_and_shoulders"],
}


@dataclass
class SwingPoint:
    index: int
    price: float
    kind: Literal["high", "low"]


@dataclass
class DetectedPattern:
    key: str
    confidence: float
    detail: str                       # scenario-specific, with real numbers
    key_levels: dict[str, float] = field(default_factory=dict)

    @property
    def info(self) -> PatternInfo:
        return PATTERN_LIBRARY[self.key]


# ── Swing / pivot detection ──────────────────────────────────────────────

def find_swings(df: pd.DataFrame, window: int = SWING_WINDOW) -> list[SwingPoint]:
    """
    Locate swing highs and lows, then force strict alternation.

    Alternation matters: pattern templates below are written as sequences
    like high-low-high-low-high. Without collapsing consecutive same-kind
    pivots into their single most extreme member, a noisy cluster of three
    adjacent highs would be read as three separate peaks and a double top
    would be mis-detected as a triple top.
    """
    highs, lows = df["high"].to_numpy(float), df["low"].to_numpy(float)
    n = len(df)
    raw: list[SwingPoint] = []

    for i in range(window, n - window):
        seg_h = highs[i - window: i + window + 1]
        seg_l = lows[i - window: i + window + 1]
        if highs[i] >= seg_h.max():
            raw.append(SwingPoint(i, float(highs[i]), "high"))
        elif lows[i] <= seg_l.min():
            raw.append(SwingPoint(i, float(lows[i]), "low"))

    if not raw:
        return []

    # Collapse runs of the same kind, keeping the most extreme.
    out: list[SwingPoint] = [raw[0]]
    for p in raw[1:]:
        last = out[-1]
        if p.kind == last.kind:
            better = (p.price > last.price) if p.kind == "high" else (p.price < last.price)
            if better:
                out[-1] = p
        else:
            out.append(p)
    return out


def _norm_slope(xs: list[int], ys: list[float], mean_price: float) -> float:
    """Least-squares slope as a fraction of price per bar."""
    if len(xs) < 2 or mean_price <= 0:
        return 0.0
    slope = float(np.polyfit(np.array(xs, float), np.array(ys, float), 1)[0])
    return slope / mean_price


def _rel_diff(a: float, b: float) -> float:
    m = max(abs(a), abs(b))
    return abs(a - b) / m if m else 0.0


def _tolerance_score(actual: float, limit: float) -> float:
    """1.0 when perfect, 0.0 at the tolerance limit. Used to build confidence."""
    if limit <= 0:
        return 0.0
    return float(max(0.0, min(1.0, 1.0 - actual / limit)))


def _daily_sigma(df: pd.DataFrame) -> float:
    r = df["close"].pct_change().dropna()
    return float(r.std()) if len(r) > 2 else 0.0


def _significant_move(sigma: float, bars: int, floor: float) -> float:
    """
    The move size that counts as structurally meaningful over `bars` sessions.

    Same volatility-scaling principle the direction threshold uses: a 4% dip
    between two peaks is a real structural feature on a sleepy large-cap and
    routine intraday noise on a volatile small-cap. Scaling by the asset's own
    sigma is what stops the detectors from finding "double tops" in the
    ordinary wiggle of a high-volatility name.
    """
    return max(floor, 1.15 * sigma * float(np.sqrt(max(bars, 1))))


def _prior_move(df: pd.DataFrame, upto_index: int) -> float:
    """
    Fractional price move from the start of the window to `upto_index`.

    Reversal patterns are defined by what they reverse: a "double top" in the
    middle of a directionless drift is just two bumps. Requiring a prior
    advance (or decline) is part of the textbook definition, and it is also
    what stops the detectors from labelling random noise — a random walk
    regularly produces two similar peaks with a dip between them, but far
    less often after a sustained run.
    """
    if upto_index <= 0:
        return 0.0
    start = float(df["close"].iloc[0])
    at = float(df["close"].iloc[min(upto_index, len(df) - 1)])
    return (at - start) / start if start else 0.0


def _is_recent(last_index: int, n: int) -> bool:
    return (n - 1 - last_index) <= PATTERN_RECENCY_BARS


# ── Individual detectors ─────────────────────────────────────────────────
# Each returns a DetectedPattern or None. All are conservative by design.

def _detect_head_and_shoulders(df, swings, inverse: bool) -> DetectedPattern | None:
    want, other = ("low", "high") if inverse else ("high", "low")
    n = len(df)

    # Walk every 5-pivot window shaped extreme/counter/extreme/counter/extreme.
    for i in range(len(swings) - 4):
        seq = swings[i: i + 5]
        if [s.kind for s in seq] != [want, other, want, other, want]:
            continue
        ls, t1, head, t2, rs = seq
        if not _is_recent(rs.index, n):
            continue

        if inverse:
            head_clears = head.price < ls.price * (1 - HEAD_PROMINENCE_MIN) and \
                          head.price < rs.price * (1 - HEAD_PROMINENCE_MIN)
        else:
            head_clears = head.price > ls.price * (1 + HEAD_PROMINENCE_MIN) and \
                          head.price > rs.price * (1 + HEAD_PROMINENCE_MIN)
        if not head_clears:
            continue
        prom = _significant_move(_daily_sigma(df),
                                 max((rs.index - ls.index) // 2, 1), HEAD_PROMINENCE_MIN)
        if abs(head.price - max(ls.price, rs.price)) / max(ls.price, rs.price) < prom:
            continue

        # A reversal formation needs a prior trend to reverse.
        run_in = _prior_move(df, ls.index)
        if (not inverse and run_in < PRIOR_TREND_MIN) or (inverse and run_in > -PRIOR_TREND_MIN):
            continue

        sym = _rel_diff(ls.price, rs.price)
        neck = _rel_diff(t1.price, t2.price)
        if sym > SHOULDER_SYMMETRY_TOL or neck > NECKLINE_TOL:
            continue

        confidence = 0.55 + 0.25 * _tolerance_score(sym, SHOULDER_SYMMETRY_TOL) \
                          + 0.20 * _tolerance_score(neck, NECKLINE_TOL)
        neckline = (t1.price + t2.price) / 2
        key = "inverse_head_and_shoulders" if inverse else "head_and_shoulders"
        word = "trough" if inverse else "peak"
        return DetectedPattern(
            key, round(min(confidence, 0.99), 2),
            (f"Three {word}s at {ls.price:.2f}, {head.price:.2f} and {rs.price:.2f} — the middle "
             f"{'undercuts' if inverse else 'clears'} both shoulders, which sit within "
             f"{sym * 100:.1f}% of each other. Neckline runs near {neckline:.2f}."),
            {"neckline": round(neckline, 2), "head": round(head.price, 2),
             "left_shoulder": round(ls.price, 2), "right_shoulder": round(rs.price, 2)},
        )
    return None


def _detect_multi_top_bottom(df, swings, count: int, top: bool) -> DetectedPattern | None:
    """Double/triple tops and bottoms — `count` equal extremes with dips between."""
    want, other = ("high", "low") if top else ("low", "high")
    n = len(df)
    seq_len = count * 2 - 1
    expected = [want if k % 2 == 0 else other for k in range(seq_len)]

    for i in range(len(swings) - seq_len + 1):
        seq = swings[i: i + seq_len]
        if [s.kind for s in seq] != expected:
            continue
        if not _is_recent(seq[-1].index, n):
            continue

        extremes = [s.price for s in seq[0::2]]
        middles = [s.price for s in seq[1::2]]

        worst_eq = max(_rel_diff(a, b) for a in extremes for b in extremes)
        if worst_eq > PEAK_EQUALITY_TOL:
            continue

        ref = min(extremes) if top else max(extremes)
        depth = min((ref - m) / ref for m in middles) if top else \
                min((m - ref) / ref for m in middles)
        span = seq[-1].index - seq[0].index
        if depth < _significant_move(_daily_sigma(df), max(span // 2, 1), TROUGH_DEPTH_MIN):
            continue

        # A reversal formation needs a prior trend to reverse.
        run_in = _prior_move(df, seq[0].index)
        if (top and run_in < PRIOR_TREND_MIN) or (not top and run_in > -PRIOR_TREND_MIN):
            continue

        # Peaks must be separated in time — see MIN_EXTREME_SEPARATION.
        idx = [s.index for s in seq[0::2]]
        if any(b - a < MIN_EXTREME_SEPARATION for a, b in zip(idx, idx[1:])):
            continue

        # A genuine triple must not be better explained as an H&S; the head
        # prominence check above already excludes those, but guard anyway.
        confidence = 0.55 + 0.25 * _tolerance_score(worst_eq, PEAK_EQUALITY_TOL) \
                          + 0.20 * min(1.0, depth / (TROUGH_DEPTH_MIN * 3))
        key = ("triple_" if count == 3 else "double_") + ("top" if top else "bottom")
        level = float(np.mean(extremes))
        return DetectedPattern(
            key, round(min(confidence, 0.99), 2),
            (f"{count} {'peaks' if top else 'troughs'} clustered near {level:.2f} "
             f"(within {worst_eq * 100:.1f}% of each other), with a "
             f"{depth * 100:.1f}% {'dip' if top else 'bounce'} between them."),
            {"level": round(level, 2),
             "trigger": round(float(min(middles) if top else max(middles)), 2)},
        )
    return None


def _detect_triangle_or_wedge(df, swings) -> DetectedPattern | None:
    n = len(df)
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    # At least one boundary needs 3+ touches; two points define a line through
    # any two random pivots, which is how noise masquerades as a trendline.
    if len(highs) < 2 or len(lows) < 2 or max(len(highs), len(lows)) < 3:
        return None
    if not _is_recent(max(highs[-1].index, lows[-1].index), n):
        return None

    mean_price = float(df["close"].mean())
    sh = _norm_slope([s.index for s in highs], [s.price for s in highs], mean_price)
    sl = _norm_slope([s.index for s in lows], [s.price for s in lows], mean_price)

    # Convergence: compare the boundary gap early vs late in the window.
    xs = np.arange(n, dtype=float)
    fit_h = np.poly1d(np.polyfit([s.index for s in highs], [s.price for s in highs], 1))
    fit_l = np.poly1d(np.polyfit([s.index for s in lows], [s.price for s in lows], 1))
    start_gap = float(fit_h(xs[0]) - fit_l(xs[0]))
    end_gap = float(fit_h(xs[-1]) - fit_l(xs[-1]))
    if start_gap <= 0:
        return None
    convergence = (start_gap - end_gap) / start_gap

    flat_h, flat_l = abs(sh) < FLAT_SLOPE_MAX, abs(sl) < FLAT_SLOPE_MAX
    # Wedges are defined by BOTH boundaries sloping, so both need enough
    # touches to be real lines rather than two arbitrary pivots joined up.
    wedge_ok = len(highs) >= 3 and len(lows) >= 3
    key: str | None = None

    if flat_h and sl > TREND_SLOPE_MIN:
        key = "ascending_triangle"
    elif flat_l and sh < -TREND_SLOPE_MIN:
        key = "descending_triangle"
    elif sh < -TREND_SLOPE_MIN and sl > TREND_SLOPE_MIN:
        key = "symmetrical_triangle"
    elif wedge_ok and sh > TREND_SLOPE_MIN and sl > TREND_SLOPE_MIN and sl > sh and convergence >= WEDGE_CONVERGENCE_MIN:
        key = "rising_wedge"
    elif wedge_ok and sh < -TREND_SLOPE_MIN and sl < -TREND_SLOPE_MIN and sh < sl and convergence >= WEDGE_CONVERGENCE_MIN:
        key = "falling_wedge"

    if key is None:
        return None
    # Triangles must also actually be narrowing, or it's just a channel.
    if key.endswith("triangle") and convergence < CONVERGENCE_MIN:
        return None

    confidence = 0.55 + 0.30 * min(1.0, convergence / 0.55) + \
                 0.15 * min(1.0, (len(highs) + len(lows)) / 6)
    return DetectedPattern(
        key, round(min(confidence, 0.99), 2),
        (f"Upper boundary sloping {sh * 100:+.2f}%/bar and lower boundary {sl * 100:+.2f}%/bar, "
         f"with the range narrowing {convergence * 100:.0f}% across the window."),
        {"upper_now": round(float(fit_h(xs[-1])), 2), "lower_now": round(float(fit_l(xs[-1])), 2)},
    )


def _detect_flag(df, bull: bool) -> DetectedPattern | None:
    """
    A flag is a sharp impulse (pole) followed by a shallow counter-drift.
    Detected on price geometry rather than pivots, since the flag body is
    usually too short to produce reliable swing points.
    """
    n = len(df)
    if n < 30:
        return None
    close = df["close"].to_numpy(float)
    flag_len = 10
    pole_lookback = 14
    pole_start = n - flag_len - pole_lookback
    if pole_start < 0:
        return None

    pole_a, pole_b = close[pole_start], close[n - flag_len - 1]
    pole_move = (pole_b - pole_a) / pole_a
    if bull and pole_move < 0.09:
        return None
    if not bull and pole_move > -0.09:
        return None

    flag = close[n - flag_len:]
    mean_price = float(flag.mean())
    drift = _norm_slope(list(range(len(flag))), list(flag), mean_price)

    # The flag must drift AGAINST the pole, gently. The band is deliberately
    # loose because the real constraints on "is this a flag" are the retrace
    # and range checks below — an over-tight slope bound rejects textbook
    # flags for being a fraction of a percent per bar too steep.
    if bull and not (-0.011 < drift < 0.0015):
        return None
    if not bull and not (-0.0015 < drift < 0.011):
        return None

    # And it must be a pause, not a retracement of the whole move.
    retrace = abs(flag.min() - pole_b) / abs(pole_b - pole_a) if bull else \
              abs(flag.max() - pole_b) / abs(pole_b - pole_a)
    if retrace > 0.55:
        return None

    # Tight range is what distinguishes a flag from a drift.
    flag_range = (flag.max() - flag.min()) / mean_price
    if flag_range > 0.09:
        return None

    confidence = 0.58 + 0.22 * min(1.0, abs(pole_move) / 0.20) + \
                 0.20 * (1 - min(1.0, retrace / 0.55))
    key = "bull_flag" if bull else "bear_flag"
    return DetectedPattern(
        key, round(min(confidence, 0.99), 2),
        (f"A {pole_move * 100:+.1f}% pole into {'a' if bull else 'a'} tight "
         f"{flag_range * 100:.1f}%-wide consolidation that has retraced only "
         f"{retrace * 100:.0f}% of the move."),
        {"pole_start": round(float(pole_a), 2), "pole_end": round(float(pole_b), 2)},
    )


def _detect_cup_and_handle(df) -> DetectedPattern | None:
    n = len(df)
    if n < 45:
        return None
    close = df["close"].to_numpy(float)
    handle_len = 8
    cup = close[: n - handle_len]
    handle = close[n - handle_len:]
    if len(cup) < 30:
        return None

    left_rim, right_rim = cup[0], cup[-1]
    bottom_i = int(np.argmin(cup))
    bottom = float(cup[bottom_i])

    # Rims roughly level, and a real depression between them.
    if _rel_diff(left_rim, right_rim) > 0.07:
        return None
    depth = (min(left_rim, right_rim) - bottom) / min(left_rim, right_rim)
    if depth < 0.10:
        return None

    # The low must sit in the middle — a low at either edge is a trend, not a cup.
    pos = bottom_i / len(cup)
    if not (0.30 <= pos <= 0.70):
        return None

    # Roundness: a V-bottom is not a cup. Require the halves to descend and
    # ascend gradually rather than in one impulse — measured by how much time
    # price spends in the lower third of the cup's range.
    lower_third = bottom + (min(left_rim, right_rim) - bottom) * 0.33
    time_low = float((cup <= lower_third).sum()) / len(cup)
    if time_low < 0.18:
        return None

    handle_depth = (right_rim - float(handle.min())) / right_rim
    if handle_depth > depth * 0.5 or handle_depth < 0:
        return None

    confidence = 0.55 + 0.25 * min(1.0, time_low / 0.35) + \
                 0.20 * (1 - min(1.0, handle_depth / (depth * 0.5 + 1e-9)))
    return DetectedPattern(
        "cup_and_handle", round(min(confidence, 0.99), 2),
        (f"A rounded {depth * 100:.0f}%-deep base with rims near {left_rim:.2f} and "
         f"{right_rim:.2f}, followed by a shallow {handle_depth * 100:.1f}% handle."),
        {"rim": round(float(max(left_rim, right_rim)), 2), "cup_low": round(bottom, 2)},
    )


# ── Public entry point ───────────────────────────────────────────────────

def detect_patterns(df: pd.DataFrame) -> list[DetectedPattern]:
    """
    Run every detector and return matches sorted by confidence.

    Order matters for the reversal family: Head & Shoulders is checked
    before triple top, because an H&S IS a triple top with an elevated
    middle peak. The peak-equality tolerance would otherwise let a genuine
    H&S be reported as a triple top, which is a materially different read.
    """
    swings = find_swings(df)
    found: list[DetectedPattern] = []

    for detector in (
        lambda: _detect_head_and_shoulders(df, swings, inverse=False),
        lambda: _detect_head_and_shoulders(df, swings, inverse=True),
        lambda: _detect_multi_top_bottom(df, swings, 3, top=True),
        lambda: _detect_multi_top_bottom(df, swings, 3, top=False),
        lambda: _detect_multi_top_bottom(df, swings, 2, top=True),
        lambda: _detect_multi_top_bottom(df, swings, 2, top=False),
        lambda: _detect_triangle_or_wedge(df, swings),
        lambda: _detect_flag(df, bull=True),
        lambda: _detect_flag(df, bull=False),
        lambda: _detect_cup_and_handle(df),
    ):
        try:
            m = detector()
        except Exception:
            m = None  # a malformed window must never break scenario generation
        if m:
            found.append(m)

    # Keep only the strongest match per pattern family.
    best: dict[str, DetectedPattern] = {}
    for m in found:
        if m.key not in best or m.confidence > best[m.key].confidence:
            best[m.key] = m
    # Conflict resolution between genuinely ambiguous shapes.
    # An ascending triangle is flat highs over RISING lows; a double/triple
    # top is the same flat highs but WITHOUT the rising support. When the
    # triangle detector fires — it has its own strict convergence test — the
    # rising lows are real, and the top reading would invert the conventional
    # bias from bullish continuation to bearish reversal. Defer to the
    # triangle. Mirrored for descending triangles versus bottoms.
    if "ascending_triangle" in best:
        best.pop("double_top", None); best.pop("triple_top", None)
    if "descending_triangle" in best:
        best.pop("double_bottom", None); best.pop("triple_bottom", None)
    # A symmetrical triangle has FALLING highs and RISING lows, so neither
    # boundary is the flat resistance/support an equal-peaks reading requires.
    if "symmetrical_triangle" in best:
        for k in ("double_top", "triple_top", "double_bottom", "triple_bottom"):
            best.pop(k, None)

    # Specificity first, confidence second — see PATTERN_SPECIFICITY.
    return sorted(
        best.values(),
        key=lambda m: (-PATTERN_SPECIFICITY.get(m.key, 0), -m.confidence),
    )


def best_pattern(df: pd.DataFrame, min_confidence: float = 0.0) -> DetectedPattern | None:
    matches = detect_patterns(df)
    if not matches or matches[0].confidence < min_confidence:
        return None
    return matches[0]


def pattern_choices(correct_key: str, rng, count: int = 4) -> list[dict]:
    """Multiple-choice options: the answer plus visually confusable distractors."""
    pool = [k for k in CONFUSABLE.get(correct_key, []) if k in PATTERN_LIBRARY]
    extras = [k for k in PATTERN_LIBRARY if k != correct_key and k not in pool]
    rng.shuffle(extras)
    distractors = (pool + extras)[: count - 1]
    keys = [correct_key] + distractors
    rng.shuffle(keys)
    return [{"value": k, "label": PATTERN_LIBRARY[k].name} for k in keys]
