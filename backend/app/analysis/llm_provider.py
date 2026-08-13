"""
app/analysis/llm_provider.py
------------------------------
Pluggable LLM backend for the synthesis steps, so the app is not tied to a
single paid vendor.

=====================================================================
WHY THIS EXISTS
=====================================================================
The thesis engine was built deterministic-first and works with no LLM at
all. But the brief asks for genuine LLM synthesis, and paying Anthropic for
API credits is a real cost the owner would rather not carry. Anthropic's
consumer Pro subscription does NOT include API access — they are separately
billed products — so "I have Claude Pro" does not make the API free.

The free path is a LOCAL model. Ollama runs quantised open-weight models on
the owner's own machine at zero marginal cost, exposes an OpenAI-ish HTTP
API, and needs no key. This module picks whichever backend is actually
available at call time, in cost order:

    1. Ollama          — free, local, no key, no quota
    2. OpenAI          — only if OPENAI_API_KEY is already set (it is, for
                         voice transcription, so it costs nothing extra to
                         reuse)
    3. Anthropic       — only if a real key is configured
    4. None            — caller keeps its deterministic output

Because every caller already has a complete deterministic result, "no LLM
available" is a normal operating state, not an error. Nothing here raises
on absence.

=====================================================================
SETUP (owner action required for the free path)
=====================================================================
    brew install ollama          # or https://ollama.com/download
    ollama pull llama3.1:8b      # ~4.7GB, runs comfortably on 16GB RAM
    ollama serve                 # usually already running as a service

Then set in backend/.env:
    OLLAMA_BASE_URL=http://host.docker.internal:11434
    OLLAMA_MODEL=llama3.1:8b

`host.docker.internal` is required rather than `localhost` because the
backend runs inside a container and Ollama runs on the host.
"""

import json
import logging
from typing import Literal

import httpx

from app.core.config import get_settings

logger = logging.getLogger("aureus.analysis.llm")

Backend = Literal["ollama", "openai", "anthropic", "none"]

_TIMEOUT = 90.0  # local models on CPU are slow; this is a background-quality step


def available_backend() -> Backend:
    """Cheapest working backend, checked in cost order."""
    s = get_settings()

    if s.ollama_base_url:
        try:
            r = httpx.get(f"{s.ollama_base_url.rstrip('/')}/api/tags", timeout=2.5)
            if r.status_code == 200:
                return "ollama"
        except Exception:
            pass  # not running — fall through, this is not an error

    if s.openai_configured:
        return "openai"
    if s.anthropic_configured:
        return "anthropic"
    return "none"


def complete_json(system: str, user: str, max_tokens: int = 1500) -> dict | None:
    """
    Ask the available backend for a JSON object.

    Returns None on any failure — unavailable backend, timeout, refusal,
    malformed JSON. Callers treat None as "keep the deterministic version",
    so a failure here degrades quality rather than breaking the request.
    """
    backend = available_backend()
    if backend == "none":
        return None
    try:
        if backend == "ollama":
            raw = _ollama(system, user, max_tokens)
        elif backend == "openai":
            raw = _openai(system, user, max_tokens)
        else:
            raw = _anthropic(system, user, max_tokens)
        if not raw:
            return None
        return _parse_json(raw)
    except Exception as exc:
        logger.warning("LLM completion failed — using deterministic output",
                       extra={"backend": backend, "error": str(exc)})
        return None


def _parse_json(raw: str) -> dict | None:
    """Models wrap JSON in prose or fences more often than they should."""
    raw = raw.strip()
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


def _ollama(system: str, user: str, max_tokens: int) -> str:
    s = get_settings()
    resp = httpx.post(
        f"{s.ollama_base_url.rstrip('/')}/api/chat",
        json={
            "model": s.ollama_model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            # Ollama honours a JSON output mode, which removes most of the
            # "here is your JSON:" preamble problem at the source.
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": max_tokens},
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


def _openai(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=get_settings().openai_api_key)
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return r.choices[0].message.content or ""


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text
