"""
app/analysis/aggregation.py
-----------------------------
How independent evidence is combined into one number.

THE PROBLEM THIS REPLACES
reweighting.reweight() takes a weighted ARITHMETIC MEAN of its
sub-signals. That is the correct operation for estimating a quantity
from repeated noisy readings of the same thing. It is the wrong
operation for accumulating separate pieces of evidence about a
hypothesis, and using it here had a precise, measurable cost:

    technical sub-signals   sd 9.9 - 31.1  (mean ~18)
    technical pillar        sd 5.6
    ensemble composite      sd 2.7 at the short horizon

Averaging n near-independent signals divides dispersion by sqrt(n).
Doing it twice - once inside each pillar, once across pillars - divided
it twice. The composite ended up living in a ten-point band around 50
while the BUY threshold sat at 65, roughly 4.7 standard deviations away.
Every stock returned HOLD because no stock could ever return anything
else. That was never a threshold problem; the thresholds were fine and
are unchanged by this module.

WHAT REPLACES IT
Stouffer's weighted Z-method, the standard way to pool independent
evidence, with an explicit correction for how correlated the evidence
actually is:

    Z = SUM(w_i * z_i) / sqrt( SUM(w_i^2) + rho * ((SUM w_i)^2 - SUM(w_i^2)) )

The denominator is the standard deviation of the weighted sum under an
assumed average pairwise correlation rho. The two limits are the whole
argument for this change:

    rho = 1  ->  denominator collapses to SUM(w_i), and Z becomes the
                 weighted MEAN. This is exactly what the old code did.
    rho = 0  ->  denominator becomes sqrt(SUM w_i^2), and n agreeing
                 signals amplify by sqrt(n) instead of attenuating.

So the old behaviour is not merely different from this one, it is this
one evaluated at rho = 1 - an unstated assumption that every signal is
perfectly redundant with every other. Measurement says the true figure
is near zero (see calibration.py). We use a conservative 0.15 - 0.25.

WHY THIS IS NOT JUST "MAKING THE NUMBERS BIGGER"
Amplification is conditional on AGREEMENT. Six signals that all lean
mildly bullish produce a strongly bullish Z, because six independent
confirmations of the same conclusion genuinely are strong evidence.
Three bullish and three bearish cancel in the numerator and produce Z
near zero no matter how emphatic each one was. The old mean did the
first case wrong and the second case right; this does both right. A
stock with genuinely mixed evidence still reads HOLD, and should.
"""

import math
from dataclasses import dataclass, field

from app.analysis.calibration import RHO, centre_and_scale

# A single sub-signal cannot contribute more than this many standard
# deviations. Without a cap, one scorer with a mis-calibrated curve - or
# one genuine outlier like a 900% revenue growth print - can swamp five
# well-behaved signals and produce false conviction from a single input.
#
# 2.0 rather than 2.5: several scorers saturate at 0 or 100, and a
# saturated reading is the LEAST informative kind (it means the scale ran
# out, not that the company is extraordinary). At 2.5 a single pegged
# metric could claim a 99th-percentile lean by itself.
_Z_CLIP = 2.0

# |Z| at which evidence strength is considered maxed out for the
# conviction figure. Z = 2 is a ~98th-percentile lean; treating anything
# beyond as "fully convinced" avoids implying precision we do not have.
_Z_FULL_STRENGTH = 2.0


@dataclass
class EvidenceSignal:
    """One piece of evidence. Mirrors WeightedSignal so call sites port cleanly."""
    name: str
    score: float          # 0-100 as produced by the scorers today
    weight: float         # baseline importance
    computed: bool        # False = no real data behind it; excluded entirely
    detail: str = ""
    # Optional override for the calibration key, when the display label
    # differs from the label the calibration was measured under.
    calibration_label: str | None = None


@dataclass
class EvidenceResult:
    composite_score: float              # 0-100, for display and thresholds
    z: float                            # combined evidence, in sd units
    conviction: float                   # 0-100, how much to trust the direction
    agreement: float                    # 0-1, do the signals concur
    effective_weights: dict[str, float]
    data_completeness: float            # 0-1 of baseline weight genuinely backed
    dropped_signals: list[str]
    contributing: list[EvidenceSignal] = field(default_factory=list)
    # Per-signal z, so the reasoning layer can say WHICH evidence drove it.
    z_by_signal: dict[str, float] = field(default_factory=dict)


def _phi(z: float) -> float:
    """Standard normal CDF. math.erf avoids a scipy dependency."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def combine_evidence(
    signals: list[EvidenceSignal],
    group: str = "ensemble",
    *,
    pre_standardised: bool = False,
) -> EvidenceResult:
    """
    Pool `signals` into one standardised score.

    `group` selects the assumed correlation (see calibration.RHO).

    `pre_standardised` is for the ensemble stage, where the inputs are
    already pillar z-scores rather than 0-100 readings. Passing them
    through centre_and_scale again would standardise a standardised
    quantity and silently shrink everything back toward neutral - which
    is the same class of mistake this module exists to fix. In that mode
    `score` is read as a z directly.
    """
    computed = [s for s in signals if s.computed]
    dropped = [s.name for s in signals if not s.computed]

    if not computed:
        # Say "we do not know" rather than return a falsely precise 50.
        return EvidenceResult(
            composite_score=50.0, z=0.0, conviction=0.0, agreement=0.0,
            effective_weights={s.name: 0.0 for s in signals},
            data_completeness=0.0, dropped_signals=dropped,
        )

    rho = RHO.get(group, 0.2)

    z_by_signal: dict[str, float] = {}
    for s in computed:
        if pre_standardised:
            z = s.score
        else:
            centre, sd = centre_and_scale(s.calibration_label or s.name)
            z = (s.score - centre) / sd
        z_by_signal[s.name] = max(-_Z_CLIP, min(_Z_CLIP, z))

    # Normalise baseline weights across the signals that survived, so a
    # dropped signal redistributes its influence rather than leaving a
    # hole. This preserves reweighting.py's contract exactly.
    total_w = sum(s.weight for s in computed)
    if total_w <= 0:
        total_w = float(len(computed))
        weights = {s.name: 1.0 / total_w for s in computed}
    else:
        weights = {s.name: s.weight / total_w for s in computed}

    sum_w = sum(weights.values())                      # 1.0 by construction
    sum_w_sq = sum(w * w for w in weights.values())

    # Variance of the weighted sum under average pairwise correlation rho.
    var = sum_w_sq + rho * (sum_w * sum_w - sum_w_sq)
    denom = math.sqrt(var) if var > 0 else 1.0

    numerator = sum(weights[s.name] * z_by_signal[s.name] for s in computed)
    z_total = numerator / denom

    # Agreement: 1.0 when every signal points the same way, 0.0 when they
    # cancel exactly. This is the honest counterweight to amplification -
    # it is what distinguishes "six independent confirmations" from "six
    # signals shouting past each other".
    abs_sum = sum(weights[s.name] * abs(z_by_signal[s.name]) for s in computed)
    agreement = abs(numerator) / abs_sum if abs_sum > 1e-9 else 0.0

    baseline_total = sum(s.weight for s in signals)
    completeness = (
        sum(s.weight for s in computed) / baseline_total if baseline_total > 0 else 0.0
    )

    strength = min(1.0, abs(z_total) / _Z_FULL_STRENGTH)

    # Multiplicative, not additive: a direction backed by strong but
    # contradictory evidence, or by one lone surviving signal, should not
    # inherit the conviction of a clean unanimous read. Both factors are
    # floored so conviction degrades rather than collapsing to zero.
    conviction = 100.0 * strength * (0.55 + 0.45 * agreement) * (0.45 + 0.55 * completeness)

    return EvidenceResult(
        composite_score=round(100.0 * _phi(z_total), 2),
        z=round(z_total, 4),
        conviction=round(min(100.0, max(0.0, conviction)), 1),
        agreement=round(agreement, 3),
        effective_weights={
            **{name: round(w, 4) for name, w in weights.items()},
            **{name: 0.0 for name in dropped},
        },
        data_completeness=round(completeness, 3),
        dropped_signals=dropped,
        contributing=computed,
        z_by_signal={k: round(v, 3) for k, v in z_by_signal.items()},
    )
