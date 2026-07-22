"""
app/api/v1/voice.py
--------------------
Voice interface WebSocket endpoint.

WebSocket protocol (client → server):
  {"type": "start_session", "user_id": "...", "tier": "elite", "stt_mode": "browser|backend"}
  {"type": "text_input", "text": "..."}            ← browser STT mode
  {"type": "audio_start"}                           ← backend STT: begin buffering
  <binary frames>                                   ← raw audio bytes
  {"type": "audio_end"}                             ← backend STT: transcribe buffer
  {"type": "end_session"}

WebSocket protocol (server → client):
  {"type": "session_ready", "session_id": "..."}
  {"type": "transcript", "text": "..."}            ← echo back what we heard
  {"type": "thinking"}                              ← LLM processing indicator
  {"type": "response", "text": "..."}              ← assistant text (browser speaks it)
  {"type": "audio", "data": "<base64 mp3>"}        ← if backend TTS requested
  {"type": "error", "message": "..."}
  {"type": "ping"}

Failure recovery:
  - If Whisper fails → send {"type": "error", "message": "..."}, stay connected
  - If LLM fails → send fallback message, stay connected
  - If session expires → send {"type": "session_expired"}, client reconnects
"""

import asyncio
import base64
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.voice.conversation import process_voice_turn
from app.voice.session_manager import (
    add_voice_minutes,
    create_session,
    delete_session,
    get_session,
)
from app.voice.transcription import text_to_speech, transcribe_audio

logger = logging.getLogger("aureus.api.voice")

router = APIRouter(prefix="/api/v1", tags=["voice"])

# Also expose REST endpoints for session info and pending alerts
REST_PREFIX = "/api/v1/voice"


@router.websocket("/ws/voice/{user_id}")
async def voice_websocket(websocket: WebSocket, user_id: str) -> None:
    """
    Main voice WebSocket endpoint.
    One connection per user. Reconnecting creates a new session.
    """
    await websocket.accept()
    session_id  = str(uuid.uuid4())
    audio_buffer: list[bytes] = []
    stt_mode    = "browser"    # default: client does STT and sends text
    use_tts     = False        # default: browser uses speechSynthesis
    session_start = datetime.now(tz=timezone.utc)

    logger.info("Voice WebSocket connected", extra={"user_id": user_id, "session_id": session_id})

    try:
        # ── Handshake ─────────────────────────────────────────────
        await websocket.send_json({
            "type":       "session_ready",
            "session_id": session_id,
            "message":    "Aureus voice interface ready. How can I help you today?",
        })

        while True:
            # Receive text (JSON control) or binary (audio) frames
            try:
                data = await asyncio.wait_for(websocket.receive(), timeout=120)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            # ── Binary frame = audio chunk ─────────────────────────
            if data.get("bytes"):
                audio_buffer.append(data["bytes"])
                continue

            # ── Text frame = JSON control message ─────────────────
            if not data.get("text"):
                continue

            try:
                msg = json.loads(data["text"])
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")

            # ── start_session ────────────────────────────────────
            if msg_type == "start_session":
                tier     = msg.get("tier", "sovereign")
                stt_mode = msg.get("stt_mode", "browser")
                use_tts  = msg.get("use_backend_tts", False)
                session  = create_session(session_id, user_id, tier_name=tier)
                await websocket.send_json({
                    "type":     "session_configured",
                    "stt_mode": stt_mode,
                    "use_tts":  use_tts,
                })
                logger.info("Voice session configured", extra={
                    "session_id": session_id, "tier": tier, "stt_mode": stt_mode,
                })

            # ── text_input (browser STT mode) ─────────────────────
            elif msg_type == "text_input":
                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue

                session = get_session(session_id)
                if not session:
                    session = create_session(session_id, user_id)

                await websocket.send_json({"type": "thinking"})

                response_text = await asyncio.to_thread(
                    process_voice_turn, session, user_text
                )

                await websocket.send_json({
                    "type": "response",
                    "text": response_text,
                })

                # Optionally stream backend TTS audio
                if use_tts:
                    try:
                        audio_bytes = await asyncio.to_thread(text_to_speech, response_text)
                        audio_b64   = base64.b64encode(audio_bytes).decode()
                        await websocket.send_json({
                            "type":   "audio",
                            "data":   audio_b64,
                            "format": "mp3",
                        })
                    except Exception as exc:
                        logger.warning("Backend TTS failed", extra={"error": str(exc)})

                # Track voice minute usage
                elapsed_seconds = (datetime.now(tz=timezone.utc) - session_start).total_seconds()
                add_voice_minutes(session_id, elapsed_seconds)
                session_start = datetime.now(tz=timezone.utc)

            # ── audio_start (backend STT mode) ────────────────────
            elif msg_type == "audio_start":
                audio_buffer = []

            # ── audio_end (backend STT mode) ──────────────────────
            elif msg_type == "audio_end":
                if not audio_buffer:
                    await websocket.send_json({"type": "error", "message": "No audio received"})
                    continue

                combined = b"".join(audio_buffer)
                audio_buffer = []

                # Transcribe
                try:
                    transcript = await asyncio.to_thread(transcribe_audio, combined)
                except RuntimeError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
                except Exception as exc:
                    await websocket.send_json({
                        "type":    "error",
                        "message": f"Transcription failed: {exc}",
                    })
                    continue

                if not transcript:
                    await websocket.send_json({"type": "error", "message": "No speech detected"})
                    continue

                # Echo transcript back to client
                await websocket.send_json({"type": "transcript", "text": transcript})
                await websocket.send_json({"type": "thinking"})

                session = get_session(session_id)
                if not session:
                    session = create_session(session_id, user_id)

                response_text = await asyncio.to_thread(
                    process_voice_turn, session, transcript
                )
                await websocket.send_json({"type": "response", "text": response_text})

            # ── end_session ───────────────────────────────────────
            elif msg_type == "end_session":
                await websocket.send_json({"type": "session_ended"})
                break

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected", extra={"user_id": user_id})
    except Exception as exc:
        logger.error("Voice WebSocket error", extra={"user_id": user_id, "error": str(exc)}, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "Internal error — session ended."})
        except Exception:
            pass
    finally:
        delete_session(session_id)
        logger.info("Voice session cleaned up", extra={"session_id": session_id})


@router.get("/voice/session/{session_id}")
def get_voice_session_info(session_id: str) -> dict:
    """Return metadata about an active voice session."""
    from fastapi import HTTPException
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {
        "session_id":         session.session_id,
        "user_id":            session.user_id,
        "started_at":         session.started_at,
        "turns_count":        len(session.turns),
        "voice_minutes_used": round(session.voice_minutes_used, 2),
        "active_ticker":      session.context.active_ticker,
        "mentioned_tickers":  session.context.mentioned_tickers,
    }
