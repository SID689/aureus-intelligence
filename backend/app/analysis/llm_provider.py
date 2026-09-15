"""
app/analysis/llm_provider.py
------------------------------
Tier-aware LLM synthesis, billed per call against the caller's credits.

=====================================================================
OLLAMA HAS BEEN REMOVED
=====================================================================
Ollama was the right answer while this was a single-user local app: free,
private, no key. It is the wrong answer for a paid product, for reasons
that only appear once there is more than one user:

  - It is not free at scale, it is free at the MARGIN and expensive in
    fixed terms. Every concurrent request needs several GB of resident
    RAM on a machine the owner pays for, so "no API bill" becomes "a
    larger server bill" plus a hard concurrency ceiling.
  - A 3B quantised model cannot produce the output quality a $99/month
    plan implies. It was adequate for restating bullets under a strict
    schema and is not adequate as the product.
  - It made cost invisible. A paid tier has to know what each call cost
    in order to bill it, and a local model reports nothing.

Paid tiers now use Anthropic. The free tier uses no LLM at all: its
output is the deterministic thesis engine, which builds every bullet from
a metric that actually computed. That is an honest free tier, not a
crippled one — what it lacks is prose polish, not substance.

=====================================================================
MODEL SELECTION IS A PLAN PROPERTY
=====================================================================
Each tier declares llm_model_default and llm_model_deep in
subscription_tiers. Routine synthesis runs on the default; work flagged
`deep=True` runs on the stronger model.

    Sovereign      none / none            deterministic only
    Elite          Haiku / Sonnet
    Institutional  Sonnet / Opus

This is the single biggest lever on unit economics. Haiku is roughly a
quarter of Sonnet's price and about a nineteenth of Opus's, so routing
routine work to it is what makes the volume in these plans affordable.

=====================================================================
BILLING
=====================================================================
Every call reserves an estimate, runs, then settles on the token counts
Anthropic reports. A user with no credits is refused BEFORE the vendor is
called, which is where "cannot exceed what they paid for" is actually
enforced — after the call the money is already spent.
"""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import get_settings

logger = logging.getLogger("aureus.analysis.llm")

# Maps the tier's model name to a concrete Anthropic model id and to the
# rate rows seeded in migration 009. Kept here rather than in the
# database because the id is a code-level API contract, while the PRICE
# lives in vendor_cost_rates where it can change without a deploy.
_MODEL_IDS: dict[str, str] = {
    "claude-haiku": "claude-haiku-4-5-20251001",
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-opus": "claude-opus-4-1",
}

# Conservative token estimate used for the pre-call reservation. Measured
# on this codebase's own synthesis prompts; deliberately biased high so
# the reservation rarely under-covers, with the excess refunded at
# settlement.
_ESTIMATE_INPUT_TOKENS = 3000
_ESTIMATE_OUTPUT_TOKENS = 1000


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    credits_charged: float
    billed: bool


class LLMUnavailable(Exception):
    """No model is available for this caller — use deterministic output."""


def model_for_user(user_id: str | None, deep: bool = False) -> str | None:
    """
    The Anthropic model this user's plan entitles them to, or None.

    None is a normal, expected state — it is what the free tier gets, and
    every caller already has a deterministic path for it.
    """
    if not user_id:
        return None
    try:
        from app.core.entitlements import resolve_entitlements
        ent = resolve_entitlements(user_id)
    except Exception as exc:
        logger.warning("Tier lookup failed for LLM routing",
                       extra={"user_id": user_id, "error": str(exc)})
        return None
    raw = ent.llm_model_deep if deep else ent.llm_model_default
    return raw or None


def anthropic_configured() -> bool:
    return get_settings().anthropic_configured


def complete_json(
    system: str,
    user: str,
    user_id: str | None = None,
    deep: bool = False,
    max_tokens: int = 1500,
    operation: str = "synthesis",
) -> dict | None:
    """
    Ask the caller's entitled model for a JSON object, billing the call.

    Returns None whenever synthesis is unavailable or fails — no model on
    this plan, no API key configured, insufficient credits, a timeout, or
    malformed JSON. Every caller treats None as "keep the deterministic
    version", so a failure here degrades quality rather than breaking the
    request. That contract is what makes the free tier and an outage the
    same code path.
    """
    model_key = model_for_user(user_id, deep=deep)
    if model_key is None:
        return None
    if not anthropic_configured():
        logger.info("Anthropic not configured: deterministic output",
                    extra={"user_id": user_id})
        return None

    model_id = _MODEL_IDS.get(model_key)
    if model_id is None:
        logger.warning("Unknown model in tier config", extra={"model": model_key})
        return None

    from app.billing.credits import (
        InsufficientCredits, price_llm_call, reserve, settle,
    )

    estimate = price_llm_call(model_key, _ESTIMATE_INPUT_TOKENS, _ESTIMATE_OUTPUT_TOKENS)
    try:
        reservation = reserve(user_id, estimate, "anthropic", f"{operation}:{model_key}")
    except InsufficientCredits as exc:
        logger.info("LLM call refused: out of credits",
                    extra={"user_id": user_id, "needed": float(exc.required),
                           "available": float(exc.available)})
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
        resp = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.2,
        )
        raw = resp.content[0].text
        in_tok = int(resp.usage.input_tokens)
        out_tok = int(resp.usage.output_tokens)
    except Exception as exc:
        # The call failed, so nothing was consumed upstream — refund the
        # whole reservation rather than charging for a response the user
        # never received.
        settle(user_id, reservation, Decimal(0), "anthropic", f"{operation}:{model_key}")
        logger.warning("LLM call failed: deterministic output kept",
                       extra={"model": model_id, "error": str(exc)})
        return None

    actual = price_llm_call(model_key, in_tok, out_tok)
    settle(user_id, reservation, actual, "anthropic", f"{operation}:{model_key}",
           usd_cost=None, quantity=in_tok + out_tok, unit="token")

    logger.info("LLM synthesis billed", extra={
        "user_id": user_id, "model": model_id,
        "input_tokens": in_tok, "output_tokens": out_tok,
        "credits": float(actual),
    })
    return _parse_json(raw)


def _parse_json(raw: str) -> dict | None:
    """Models wrap JSON in prose or fences more often than they should."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None


def available_backend() -> str:
    """
    Retained for callers that only ask "is synthesis possible at all".

    Returns 'anthropic' or 'none'. The Ollama branch is gone; see the
    module docstring.
    """
    return "anthropic" if anthropic_configured() else "none"
