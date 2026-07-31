"""
app/voice/conversation.py
--------------------------
Claude-backed conversational AI for the voice interface.

The voice assistant behaves like a knowledgeable financial analyst
available on-call. It:
  - Knows the user's portfolio (injected from DB into system prompt)
  - Remembers conversation context across turns (rolling window)
  - Can trigger analysis, summarise news alerts, and explain positions
  - Never recommends specific trades or predicts prices
  - Speaks in short, natural sentences (not bullet points or markdown)
  - Invokes the mandatory disclaimer on first financial topic per session
"""

import json
import logging
import re
import time
from datetime import datetime, timezone

import anthropic

from app.agents.guardrails import validate_llm_output
from app.core.config import get_settings
from app.voice.session_manager import (
    VoiceSession,
    add_turn,
    get_context_for_llm,
    update_context,
)

logger = logging.getLogger("aureus.voice.conversation")

# ── Ticker extraction from spoken text ───────────────────────────────────────

_TICKER_SPOKEN_MAP = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
    "alphabet": "GOOGL", "amazon": "AMZN", "tesla": "TSLA",
    "nvidia": "NVDA", "meta": "META", "netflix": "NFLX",
    "salesforce": "CRM", "amd": "AMD", "intel": "INTC",
}

def _extract_ticker_from_text(text: str) -> str | None:
    lower = text.lower()
    for name, ticker in _TICKER_SPOKEN_MAP.items():
        if name in lower:
            return ticker
    # Explicit ticker mention (spoken as individual letters, e.g. "A A P L")
    match = re.search(r'\b([A-Z]{2,5})\b', text)
    if match:
        return match.group(1)
    return None


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(session: VoiceSession, portfolio_text: str) -> str:
    ctx = session.context
    return f"""You are Aureus, an AI financial analyst assistant for the Aureus Intelligence platform. You are speaking with a user via voice interface.

## PERSONA AND TONE
- Speak in natural, conversational sentences. Never use bullet points, headers, or markdown.
- Keep responses concise — 2 to 4 sentences maximum unless the user explicitly asks for detail.
- Sound like a knowledgeable colleague, not a formal report.
- Use "I" and "we" naturally. Be direct but measured.

## CAPABILITIES
You can:
- Discuss market analysis, company fundamentals, and technical patterns
- Summarise recent news and its portfolio implications
- Explain risk metrics (beta, volatility, drawdown) in plain language
- Help the user think through strategy adjustments
- Reference the user's portfolio positions and recent alerts

## STRICT RULES — NEVER VIOLATE THESE
1. NEVER predict specific price targets or percentage movements
2. NEVER explicitly recommend buying or selling a specific security
3. NEVER invent data — if you don't know, say so
4. On the FIRST financial discussion topic of each session, say: "Just to note, nothing I say is financial advice — I'm here to inform, not advise."
5. Keep responses spoken-word friendly — no symbols like $ or % unless reading a number

## MEMORY AND CONTEXT
Current active ticker: {ctx.active_ticker or 'none'}
Tickers mentioned this session: {', '.join(ctx.mentioned_tickers) or 'none'}
Active strategy: {ctx.active_strategy_id or 'none'}
Session started: {session.started_at}

## USER PORTFOLIO SNAPSHOT
{portfolio_text}

## LAST ANALYSIS RESULT
{json.dumps(ctx.last_analysis_result, indent=2) if ctx.last_analysis_result else 'No analysis run yet this session.'}

When the user says things like "adjust that" or "what about instead" — use the memory above to understand what they're referring to."""


def _get_portfolio_text(user_id: str) -> str:
    """Fetch a brief portfolio summary for the system prompt."""
    try:
        from sqlalchemy import create_engine, text as sql_text
        engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                sql_text("""
                    SELECT ph.ticker, ph.current_weight, ph.current_price, ph.beta
                    FROM portfolio_holdings ph
                    JOIN portfolios p ON ph.portfolio_id = p.id
                    WHERE p.user_id = :uid
                    ORDER BY ph.current_weight DESC NULLS LAST
                    LIMIT 10
                """),
                {"uid": user_id},
            ).fetchall()
        engine.dispose()
        if not rows:
            return "No portfolio holdings on record."
        lines = [f"{r.ticker}: {r.current_weight:.1f}% weight, price ${r.current_price:.2f}, beta {r.beta:.2f}"
                 for r in rows if r.current_weight]
        return "\n".join(lines) or "Portfolio data loading."
    except Exception:
        return "Portfolio data temporarily unavailable."


# ── Main conversation function ────────────────────────────────────────────────

def process_voice_turn(
    session: VoiceSession,
    user_text: str,
) -> str:
    """
    Process one conversational turn.

    Args:
        session:   Current VoiceSession (loaded from Redis by the WebSocket handler).
        user_text: Transcribed user speech.

    Returns:
        Assistant response text (to be spoken via TTS or browser speechSynthesis).
    """
    settings = get_settings()
    if not settings.anthropic_configured:
        return (
            "I'm not fully configured yet. "
            "The Anthropic API key is missing — please contact your administrator."
        )

    # Update context if a ticker is mentioned
    detected_ticker = _extract_ticker_from_text(user_text)
    if detected_ticker:
        update_context(session.session_id, active_ticker=detected_ticker)
        # Reload session to get updated context
        from app.voice.session_manager import get_session
        session = get_session(session.session_id) or session

    # Add user turn to history
    add_turn(session.session_id, "user", user_text)

    # Build messages for Claude
    portfolio_text = _get_portfolio_text(session.user_id)
    system_prompt  = _build_system_prompt(session, portfolio_text)
    messages       = get_context_for_llm(session)

    # Call Claude
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    start  = time.monotonic()

    try:
        for attempt in range(2):
            turn_messages = messages
            if attempt == 1:
                # Same guardrail-violation-retry shape as analysis/reasoning.py's
                # polish_with_llm: one corrective retry before giving up.
                turn_messages = messages + [{
                    "role": "user",
                    "content": (
                        "Your previous reply used forbidden absolute/guarantee "
                        "language. Do not predict future price direction and do "
                        "not use words like 'will', 'guaranteed', or 'risk-free'. "
                        "Rephrase your answer to the same question without them."
                    ),
                }]

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,      # short — voice responses should be brief
                system=system_prompt,
                messages=turn_messages,
            )
            assistant_text = response.content[0].text.strip()

            validation = validate_llm_output(assistant_text)
            if validation.is_clean:
                elapsed = time.monotonic() - start
                logger.info(
                    "Voice turn processed",
                    extra={
                        "session_id":     session.session_id,
                        "user_chars":     len(user_text),
                        "response_chars": len(assistant_text),
                        "elapsed_seconds": round(elapsed, 2),
                        "attempt":        attempt,
                    },
                )
                add_turn(session.session_id, "assistant", assistant_text)
                return assistant_text

            logger.warning(
                "Voice turn failed guardrail validation",
                extra={"session_id": session.session_id, "violations": validation.violations, "attempt": attempt},
            )

        # Both attempts violated guardrails — never speak the unsafe text.
        fallback = "I can't phrase that safely as investment guidance — could you rephrase your question?"
        add_turn(session.session_id, "assistant", fallback)
        return fallback

    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit in voice turn")
        return "I'm receiving too many requests right now — please try again in a moment."
    except Exception as exc:
        logger.error("Voice turn failed", extra={"error": str(exc)})
        return "I ran into a technical issue. Please try speaking again."
