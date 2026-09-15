"""
app/core/realtime_auth.py
---------------------------
Signed, short-lived tokens for the premium real-time surfaces.

WHY THIS EXISTS
Every existing REST endpoint identifies its caller by a `user_id` query
parameter, and the original alert WebSocket takes it in the URL path — its
own docstring acknowledges this and defers the fix. For a tier-gated
channel that is not a gate at all. A user's UUID is in their session, their
API calls and their browser's network tab, so a free account that learns a
premium user's id could subscribe to that user's Strong Buy alerts. Gating
a paid feature on an identifier the client simply asserts is decoration.

So the leaderboard, the notification history, push subscription and the
market-alert socket all require a token minted server-side by Next.js from
the NextAuth session (frontend/app/api/realtime/token/route.ts). The
browser cannot forge one because it never holds the signing key.

WHAT THE TOKEN DELIBERATELY DOES NOT CARRY: THE TIER
The token proves identity only. Entitlement is resolved from the database
on every use. A token minted before a downgrade therefore stops unlocking
anything the moment the subscription changes, instead of acting as a bearer
credential for a plan the user no longer pays for.

FORMAT
    v1.<base64url(json payload)>.<base64url(HMAC-SHA256(key, "v1.<payload>"))>

    key = HMAC-SHA256(INTERNAL_API_SECRET, "aureus-realtime-token-v1")

Deriving a purpose-specific key means the raw internal secret — which also
authorises billing mutations — is never used directly to sign something
that travels through a browser. A leaked realtime token cannot be replayed
against the billing endpoints, and vice versa.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time

from fastapi import Header, HTTPException

_VERSION = "v1"
_AUDIENCE = "aureus-realtime"
_KEY_CONTEXT = b"aureus-realtime-token-v1"

# Short on purpose. The socket checks the token once, at connect; REST calls
# fetch a fresh one when this runs out. A stolen token is worth minutes.
MAX_TTL_SECONDS = 900
_CLOCK_SKEW_SECONDS = 30

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class RealtimeAuthError(Exception):
    """Token missing, malformed, forged or expired."""


class RealtimeAuthUnavailable(RealtimeAuthError):
    """
    The signing secret is not configured.

    Raised rather than accepting every token: auth that silently disappears
    when a config value is missing is not auth. billing._verify_internal
    fails closed for the same reason.
    """


def _signing_key() -> bytes:
    secret = os.getenv("INTERNAL_API_SECRET", "")
    if not secret:
        raise RealtimeAuthUnavailable("INTERNAL_API_SECRET is not configured")
    return hmac.new(secret.encode(), _KEY_CONTEXT, hashlib.sha256).digest()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def mint_token(user_id: str, ttl_seconds: int = 300) -> str:
    """
    Mint a token. Production tokens are minted by the Next.js server; this
    mirror exists for tests and internal tooling, and the two must stay
    byte-compatible — see the route handler's comment.
    """
    now = int(time.time())
    payload = {"sub": user_id, "aud": _AUDIENCE, "iat": now,
               "exp": now + max(1, min(ttl_seconds, MAX_TTL_SECONDS))}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{_VERSION}.{body}"
    sig = _b64e(hmac.new(_signing_key(), signing_input.encode(), hashlib.sha256).digest())
    return f"{signing_input}.{sig}"


def verify_token(token: str) -> str:
    """Return the user id a valid token was minted for. Raises on anything else."""
    if not token or token.count(".") != 2:
        raise RealtimeAuthError("malformed token")
    version, body, sig = token.split(".")
    if version != _VERSION:
        raise RealtimeAuthError("unsupported token version")

    # Signature before parsing: never interpret attacker-controlled JSON
    # until it is known to be ours.
    expected = hmac.new(_signing_key(), f"{version}.{body}".encode(), hashlib.sha256).digest()
    try:
        given = _b64d(sig)
    except Exception as exc:  # noqa: BLE001
        raise RealtimeAuthError("malformed signature") from exc
    if not hmac.compare_digest(expected, given):
        raise RealtimeAuthError("bad signature")

    try:
        payload = json.loads(_b64d(body))
    except Exception as exc:  # noqa: BLE001
        raise RealtimeAuthError("malformed payload") from exc

    now = int(time.time())
    if payload.get("aud") != _AUDIENCE:
        raise RealtimeAuthError("wrong audience")
    exp, iat = payload.get("exp"), payload.get("iat")
    if not isinstance(exp, int) or not isinstance(iat, int):
        raise RealtimeAuthError("missing timestamps")
    if exp < now - _CLOCK_SKEW_SECONDS:
        raise RealtimeAuthError("expired")
    if iat > now + _CLOCK_SKEW_SECONDS:
        raise RealtimeAuthError("issued in the future")
    # A correctly signed token with a year-long lifetime would mean the
    # minting side is misconfigured; refuse it rather than honour it.
    if exp - iat > MAX_TTL_SECONDS + _CLOCK_SKEW_SECONDS:
        raise RealtimeAuthError("lifetime exceeds maximum")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not _UUID_RE.match(sub):
        raise RealtimeAuthError("invalid subject")
    return sub


def realtime_user(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: the user id from `Authorization: Bearer <token>`."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="A sign-in token is required",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify_token(token.strip())
    except RealtimeAuthUnavailable:
        raise HTTPException(status_code=503, detail="Real-time authentication is not configured")
    except RealtimeAuthError:
        raise HTTPException(status_code=401, detail="Invalid or expired sign-in token",
                            headers={"WWW-Authenticate": "Bearer"})
