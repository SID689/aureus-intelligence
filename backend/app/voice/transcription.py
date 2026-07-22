"""
app/voice/transcription.py
---------------------------
Speech-to-text via OpenAI Whisper API.

Two-mode design:
  1. BACKEND STT (this file): client streams audio bytes over WebSocket,
     server buffers and sends to Whisper. More accurate, costs API credits.
  2. BROWSER STT (frontend): Web Speech API runs in Chrome/Safari.
     Zero cost, slightly less accurate, requires no backend transcription.

The WebSocket protocol signals which mode is active:
  {"type": "stt_mode", "mode": "backend"} → use this module
  {"type": "stt_mode", "mode": "browser"} → frontend sends text directly

Audio format accepted: WAV or WebM, 16kHz mono recommended.
Whisper handles format detection automatically.
"""

import io
import logging
import time

from app.core.config import get_settings

logger = logging.getLogger("aureus.voice.transcription")


def transcribe_audio(audio_bytes: bytes, language: str = "en") -> str:
    """
    Send audio bytes to OpenAI Whisper and return the transcript text.
    Raises RuntimeError if OpenAI is not configured.

    Args:
        audio_bytes: Raw audio bytes (WAV, WebM, MP4, MP3 all supported).
        language:    BCP-47 language code hint (improves accuracy).

    Returns:
        Transcribed text string. Empty string if no speech detected.
    """
    settings = get_settings()
    if not settings.openai_configured:
        raise RuntimeError(
            "OPENAI_API_KEY not configured — backend transcription unavailable. "
            "Use browser STT mode instead (set stt_mode=browser in the voice session)."
        )

    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)

    # Whisper requires a file-like object with a name attribute for format detection
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"  # webm is what MediaRecorder produces in browsers

    start_time = time.monotonic()
    try:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="text",
        )
        elapsed = time.monotonic() - start_time
        transcript = response.strip() if isinstance(response, str) else ""
        logger.info(
            "Transcription complete",
            extra={
                "chars": len(transcript),
                "elapsed_seconds": round(elapsed, 2),
            },
        )
        return transcript
    except Exception as exc:
        elapsed = time.monotonic() - start_time
        logger.error(
            "Whisper transcription failed",
            extra={"error": str(exc), "elapsed_seconds": round(elapsed, 2)},
        )
        raise


def text_to_speech(text: str, voice: str = "alloy") -> bytes:
    """
    Convert text to speech via OpenAI TTS API.
    Returns MP3 audio bytes.

    Voice options: alloy, echo, fable, onyx, nova, shimmer
    'alloy' is recommended for financial/professional contexts (clear, neutral tone).

    Note: TTS is a backend fallback. The frontend uses browser-native
    window.speechSynthesis (free, zero latency) by default.
    """
    settings = get_settings()
    if not settings.openai_configured:
        raise RuntimeError("OPENAI_API_KEY not configured — backend TTS unavailable.")

    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)

    # Cap text length — TTS API has a 4096 char limit
    text = text[:4000]

    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        speed=1.1,  # slightly faster — good for financial briefings
    )
    return response.content
