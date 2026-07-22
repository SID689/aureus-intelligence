"""
app/voice/session_manager.py
-----------------------------
Manages voice session state and conversation memory in Redis.

Each session stores:
  - Full conversation turn history (rolling window of last N turns)
  - Active context: current ticker, strategy, portfolio snapshot
  - Voice minute consumption for tier enforcement
  - Session metadata: user, started_at, session_id

Memory design:
  Context variables survive across turns so the user can say
  "adjust that" or "what about MSFT instead" without restating the full query.
  The last analysis result is kept in context so the voice agent can
  reference it directly without re-running the analysis.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger("aureus.voice.session")

_SESSION_KEY_PREFIX = "voice:session:"


@dataclass
class ConversationTurn:
    role:      str     # "user" | "assistant"
    content:   str
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


@dataclass
class VoiceContext:
    """Persistent context variables that carry across turns."""
    active_ticker:         str | None = None
    active_strategy_id:    str | None = None
    mentioned_tickers:     list[str]  = field(default_factory=list)
    last_analysis_result:  dict | None = None
    last_order_proposal:   dict | None = None
    portfolio_summary:     dict | None = None


@dataclass
class VoiceSession:
    session_id:        str
    user_id:           str
    started_at:        str
    turns:             list[ConversationTurn] = field(default_factory=list)
    context:           VoiceContext           = field(default_factory=VoiceContext)
    voice_minutes_used: float                 = 0.0
    tier_name:         str                   = "sovereign"


def _session_key(session_id: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{session_id}"


def create_session(session_id: str, user_id: str, tier_name: str = "sovereign") -> VoiceSession:
    session = VoiceSession(
        session_id=session_id,
        user_id=user_id,
        started_at=datetime.now(tz=timezone.utc).isoformat(),
        tier_name=tier_name,
    )
    _save(session)
    logger.info("Voice session created", extra={"session_id": session_id, "user_id": user_id})
    return session


def get_session(session_id: str) -> VoiceSession | None:
    raw = get_redis_client().get(_session_key(session_id))
    if not raw:
        return None
    data    = json.loads(raw)
    turns   = [ConversationTurn(**t) for t in data.get("turns", [])]
    context = VoiceContext(**data.get("context", {}))
    return VoiceSession(
        session_id=data["session_id"],
        user_id=data["user_id"],
        started_at=data["started_at"],
        turns=turns,
        context=context,
        voice_minutes_used=data.get("voice_minutes_used", 0.0),
        tier_name=data.get("tier_name", "sovereign"),
    )


def _save(session: VoiceSession) -> None:
    cfg = get_settings()
    data = {
        "session_id":         session.session_id,
        "user_id":            session.user_id,
        "started_at":         session.started_at,
        "turns":              [asdict(t) for t in session.turns],
        "context":            asdict(session.context),
        "voice_minutes_used": session.voice_minutes_used,
        "tier_name":          session.tier_name,
    }
    get_redis_client().setex(
        _session_key(session.session_id),
        cfg.voice_session_ttl_seconds,
        json.dumps(data),
    )


def add_turn(session_id: str, role: str, content: str) -> None:
    """Append a conversation turn and trim to max_context_turns rolling window."""
    session = get_session(session_id)
    if not session:
        return
    cfg = get_settings()
    session.turns.append(ConversationTurn(role=role, content=content))
    # Keep only the last N turns to avoid unbounded context growth
    if len(session.turns) > cfg.voice_max_context_turns * 2:
        session.turns = session.turns[-(cfg.voice_max_context_turns * 2):]
    _save(session)


def update_context(session_id: str, **kwargs: Any) -> None:
    """Update specific context variables without overwriting the whole session."""
    session = get_session(session_id)
    if not session:
        return
    for k, v in kwargs.items():
        if hasattr(session.context, k):
            setattr(session.context, k, v)
        # Add new tickers to mentioned_tickers list
        if k == "active_ticker" and v and v not in session.context.mentioned_tickers:
            session.context.mentioned_tickers.append(v)
    _save(session)


def add_voice_minutes(session_id: str, duration_seconds: float) -> float:
    """Increment voice minutes used and return the new total."""
    session = get_session(session_id)
    if not session:
        return 0.0
    session.voice_minutes_used += duration_seconds / 60.0
    _save(session)
    return session.voice_minutes_used


def get_context_for_llm(session: VoiceSession) -> list[dict]:
    """
    Format the conversation history as the messages array for an LLM API call.
    Includes the rolling window of turns.
    """
    messages = []
    for turn in session.turns:
        messages.append({"role": turn.role, "content": turn.content})
    return messages


def delete_session(session_id: str) -> None:
    get_redis_client().delete(_session_key(session_id))
    logger.info("Voice session deleted", extra={"session_id": session_id})
