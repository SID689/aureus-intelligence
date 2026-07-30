"""
app/analysis/reasoning.py  (rewrite — specific strengths/weaknesses, honest DCF diagnosis)
--------------------------------------------------------------------------------------------
Direct fix for: "explanations should extend past the score and talk about
specific things the company is doing well vs poorly, and explain why DCF
was skipped / why FCF is missing."

Strategy: pull every module's signal_breakdown (see fundamental.py,
technical.py, quantitative.py), rank them, and name the top 2-3 highest-
scoring as "what's helping" and the bottom 2-3 lowest-scoring as "what's
hurting" — using the concrete detail string each module already generated,
not a re-summarized paraphrase. The DCF skip reason (if any) is now always
surfaced explicitly and specifically, never just "data unavailable."
"""

import logging

from app.analysis.models import EnsembleSignal, FundamentalScore, QuantitativeScore, TechnicalScore
from app.core.config import get_settings
from app.agents.guardrails import CORE_ORCHESTRATOR_SYSTEM_PROMPT, validate_llm_output

logger = logging.getLogger("aureus.analysis.reasoning")

_STRENGTH_THRESHOLD = 62.0
_WEAKNESS_THRESHOLD = 42.0
_MAX_CALLOUTS = 3


def _completeness_phrase(completeness: float) -> str:
    if completeness >= 0.95: return "based on complete data"
    if completeness >= 0.65: return "based on mostly complete data"
    if completeness >= 0.30: return "based on partial data — treat with extra caution"
    return "based on very limited data — largely a neutral placeholder"


def _collect_all_signals(
    fundamental: FundamentalScore, technical: TechnicalScore, quantitative: QuantitativeScore,
) -> list[dict]:
    all_signals: list[dict] = []
    for module_name, module in [("Fundamental", fundamental), ("Technical", technical), ("Quantitative", quantitative)]:
        for sig in module.signal_breakdown:
            all_signals.append({**sig, "module": module_name})
    return all_signals


def build_deterministic_reasoning(
    ticker: str,
    time_horizon_label: str,
    signal: str,
    strength: str,
    confidence_index: float,
    fundamental: FundamentalScore,
    technical: TechnicalScore,
    quantitative: QuantitativeScore,
    module_weights: dict,
) -> str:
    parts: list[str] = []

    parts.append(
        f"Over a {time_horizon_label} horizon, {ticker} scores {confidence_index:.1f}/100 "
        f"({signal}, {strength.lower()} conviction)."
    )

    fund_w = module_weights.get("fundamental", 0.35)
    tech_w = module_weights.get("technical", 0.35)
    quant_w = module_weights.get("quantitative", 0.30)
    if abs(fund_w - 0.35) > 0.02 or abs(tech_w - 0.35) > 0.02 or abs(quant_w - 0.30) > 0.02:
        parts.append(
            f"Module weighting was adjusted from the standard 35/35/30 split to "
            f"{fund_w*100:.0f}% fundamental / {tech_w*100:.0f}% technical / {quant_w*100:.0f}% quantitative "
            f"because some data sources didn't return usable figures for this ticker."
        )

    # ── What's helping / what's hurting — the direct fix ────────────────
    all_signals = _collect_all_signals(fundamental, technical, quantitative)
    strengths = sorted([s for s in all_signals if s["score"] >= _STRENGTH_THRESHOLD], key=lambda s: -s["score"])[:_MAX_CALLOUTS]
    weaknesses = sorted([s for s in all_signals if s["score"] <= _WEAKNESS_THRESHOLD], key=lambda s: s["score"])[:_MAX_CALLOUTS]

    if strengths:
        bullets = "; ".join(f"{s['label']} ({s['module']}) — {s['detail']}" for s in strengths)
        parts.append(f"What's helping the score: {bullets}.")
    if weaknesses:
        bullets = "; ".join(f"{s['label']} ({s['module']}) — {s['detail']}" for s in weaknesses)
        parts.append(f"What's dragging on the score: {bullets}.")
    if not strengths and not weaknesses:
        parts.append("No individual factor stood out as a strong driver in either direction — this is a genuinely balanced picture across the data available.")

    # ── DCF — always explicit, never just "data unavailable" ────────────
    if fundamental.dcf_detail:
        d = fundamental.dcf_detail
        direction = "above" if d.current_price > d.intrinsic_value_per_share else "below"
        parts.append(
            f"The discounted cash flow model estimates intrinsic value at ${d.intrinsic_value_per_share:.2f} "
            f"per share versus a current price of ${d.current_price:.2f} — trading {direction} the model's "
            f"estimate by {abs(d.margin_of_safety)*100:.1f}%."
        )
    elif fundamental.dcf_skip_reason:
        parts.append(f"DCF valuation was not run: {fundamental.dcf_skip_reason}")

    # ── Module completeness footnotes ────────────────────────────────────
    fc = _completeness_phrase(fundamental.data_completeness)
    tc = _completeness_phrase(technical.data_completeness)
    qc = _completeness_phrase(quantitative.data_completeness)
    parts.append(
        f"Module scores: fundamental {fundamental.score:.0f}/100 ({fc}), "
        f"technical {technical.score:.0f}/100 ({tc}), quantitative {quantitative.score:.0f}/100 ({qc})."
    )

    return " ".join(p for p in parts if p.strip())


# ── Optional LLM polish ─────────────────────────────────────────────────────

_POLISH_USER_TEMPLATE = """Rewrite the following analysis summary into natural, flowing prose (5-7 sentences) suitable for a professional trading dashboard. Preserve every number and every named strength/weakness exactly as given — do not change, round differently, drop, or add any figure or claim not already present. Keep the specific company-strength and company-weakness callouts; do not water them down into vague generalities. Do not use bullet points.

SOURCE SUMMARY (all facts must come from here, verbatim numbers and claims):
{deterministic_text}

Rewrite now:"""


def polish_with_llm(deterministic_text: str, ticker: str) -> tuple[str, str]:
    settings = get_settings()
    if not settings.anthropic_configured:
        return deterministic_text, "deterministic"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        for attempt in range(2):
            user_message = _POLISH_USER_TEMPLATE.format(deterministic_text=deterministic_text)
            if attempt == 1:
                user_message += "\n\nIMPORTANT: your previous attempt used forbidden absolute/guarantee language. Do not predict future price direction. Do not use the words 'will', 'guaranteed', or 'risk-free'."

            response = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=500,
                system=CORE_ORCHESTRATOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            candidate = response.content[0].text.strip()
            validation = validate_llm_output(candidate)
            if validation.is_clean:
                logger.info("Reasoning polished by LLM and passed guardrails", extra={"ticker": ticker, "attempt": attempt})
                return candidate, "llm_polished"
            logger.warning("LLM-polished reasoning failed guardrails", extra={"ticker": ticker, "violations": validation.violations})

        return deterministic_text, "deterministic"
    except Exception as exc:
        logger.warning("LLM polish failed — using deterministic reasoning", extra={"ticker": ticker, "error": str(exc)})
        return deterministic_text, "deterministic"


def generate_reasoning(
    ticker: str, time_horizon_label: str, signal: str, strength: str, confidence_index: float,
    fundamental: FundamentalScore, technical: TechnicalScore, quantitative: QuantitativeScore,
    module_weights: dict, use_llm_polish: bool = True,
) -> tuple[str, str]:
    deterministic = build_deterministic_reasoning(
        ticker, time_horizon_label, signal, strength, confidence_index,
        fundamental, technical, quantitative, module_weights,
    )
    if not use_llm_polish:
        return deterministic, "deterministic"
    return polish_with_llm(deterministic, ticker)
