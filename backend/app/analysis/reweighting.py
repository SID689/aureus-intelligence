"""
app/analysis/reweighting.py
-----------------------------
THE CORE FIX for the "everything returns HOLD with similar scores" bug.

ROOT CAUSE: the original Phase 2 implementation used fixed weights
(e.g., 35% DCF / 25% safety / 25% growth / 15% moat) even when a
sub-signal had no real data and silently defaulted to a neutral 50.
A defaulted-to-50 signal at 35% weight drags every stock's fundamental
score toward 50 regardless of that stock's actual fundamentals — and
since 50 always classifies as HOLD, most tickers converged on HOLD
with near-identical composite scores whenever upstream data providers
(Finnhub/EDGAR, or SPY for beta) didn't return usable data.

THE FIX: every sub-signal now reports whether it was genuinely computed
from real data (`computed=True`) or fell back to a neutral default
(`computed=False`). `reweight()` drops non-computed signals entirely and
redistributes their weight proportionally across the signals that DID
compute, so a stock's score is driven only by the data that's actually
known about it. If literally nothing computed, we return 50 with an
explicit "insufficient data" flag rather than pretending precision.
"""

from dataclasses import dataclass


@dataclass
class WeightedSignal:
    name:      str      # e.g. "dcf_signal", "rsi_score"
    score:     float    # 0-100
    weight:    float    # baseline weight, e.g. 0.35
    computed:  bool      # True if genuinely computed from real data
    detail:    str = ""  # short human-readable note for the reasoning text


@dataclass
class ReweightResult:
    composite_score:    float
    effective_weights:  dict[str, float]   # name -> weight actually used
    data_completeness:  float              # 0-1, fraction of baseline weight backed by real data
    dropped_signals:    list[str]          # names that were excluded (no data)
    contributing:       list[WeightedSignal]


def reweight(signals: list[WeightedSignal]) -> ReweightResult:
    """
    Compute a weighted-average score, dropping any signal that wasn't
    genuinely computed and redistributing its weight proportionally
    across the remaining computed signals.
    """
    computed_signals = [s for s in signals if s.computed]
    dropped = [s.name for s in signals if not s.computed]

    if not computed_signals:
        # Nothing computed at all — be honest about it rather than
        # returning a falsely-precise number.
        return ReweightResult(
            composite_score=50.0,
            effective_weights={s.name: 0.0 for s in signals},
            data_completeness=0.0,
            dropped_signals=dropped,
            contributing=[],
        )

    total_computed_weight = sum(s.weight for s in computed_signals)
    baseline_total = sum(s.weight for s in signals)

    # Redistribute proportionally: each computed signal's effective weight
    # scales up so the computed signals' weights sum to 1.0
    effective_weights: dict[str, float] = {}
    composite = 0.0
    for s in computed_signals:
        eff_w = s.weight / total_computed_weight if total_computed_weight > 0 else 1.0 / len(computed_signals)
        effective_weights[s.name] = round(eff_w, 4)
        composite += eff_w * s.score

    for name in dropped:
        effective_weights[name] = 0.0

    data_completeness = total_computed_weight / baseline_total if baseline_total > 0 else 0.0

    return ReweightResult(
        composite_score=round(max(0.0, min(100.0, composite)), 2),
        effective_weights=effective_weights,
        data_completeness=round(data_completeness, 3),
        dropped_signals=dropped,
        contributing=computed_signals,
    )
