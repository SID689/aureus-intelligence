"""
app/api/v1/demo.py
------------------
The presentation environment's two endpoints.

POST /api/v1/demo/session
    Provisions (or returns) the demo account for a device and hands back
    the fields NextAuth needs to mint a session. Internal-only: it is
    called from the Next.js server during sign-in, never from a browser,
    and it is the one endpoint in the app that can create a top-tier
    account without payment. It refuses every call unless demo mode is
    explicitly on AND the internal secret matches, so a production
    deployment that never sets `DEMO_MODE` cannot be talked into issuing
    free Institutional accounts even if this route is reachable.

GET /api/v1/demo/status
    Public and cheap. Says whether the demo is available and what is
    seeded, so the landing page can show the entry point only when it
    will actually work.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.billing import _verify_internal
from app.core.config import get_settings
from app.demo.fixtures import available as available_fixtures
from app.demo.provision import ensure_demo_session
from app.demo.showcase import SHOWCASE_TICKERS

logger = logging.getLogger("aureus.api.demo")
router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoSessionRequest(BaseModel):
    # Opaque, browser-generated, and treated as untrusted: it is slugged
    # down to [a-z0-9] before it reaches a query. See provision.normalise_device.
    device: str = Field(default="", max_length=128)


@router.get("/status")
def demo_status() -> dict:
    """Whether this deployment is a demo, and what it has been seeded with."""
    settings = get_settings()
    return {
        "enabled": settings.demo_mode,
        "tier": settings.demo_tier if settings.demo_mode else None,
        "showcase_tickers": list(SHOWCASE_TICKERS) if settings.demo_mode else [],
        "snapshots": len(available_fixtures()) if settings.demo_mode else 0,
    }


@router.post("/session", dependencies=[Depends(_verify_internal)])
def create_demo_session(req: DemoSessionRequest) -> dict:
    settings = get_settings()
    if not settings.demo_mode:
        # 404 rather than 403: in a non-demo deployment this route does
        # not meaningfully exist, and saying "forbidden" would confirm
        # that a free-account endpoint is present and merely switched off.
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return ensure_demo_session(req.device)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception as exc:
        logger.error("Demo session provisioning failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=503, detail="Demo session could not be created")
