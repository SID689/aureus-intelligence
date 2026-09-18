"""
app/demo/fixtures.py
--------------------
Bundled analysis payloads, read from disk.

These are not hand-written mocks. Each one is the real output of
`run_ensemble_analysis` for that ticker and horizon, captured by
scripts/capture_showcase.py against a configured stack and committed.
That distinction matters for a demo: every number on screen came out of
the engine being demonstrated, so the pillars, the theses and the
composite are all mutually consistent, which invented figures never are.

They serve two purposes:

  1. The first tap on a showcase ticker answers immediately, with no
     provider latency, on a cold deployment.
  2. When a provider is rate-limited, unconfigured or down mid-demo, the
     endpoint degrades to the snapshot instead of returning 503.

Anything served from here carries `showcase_snapshot: true` and the
capture timestamp, and the UI labels it. A stale snapshot presented as
live analysis would be the one genuinely dishonest thing this module
could do.
"""

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger("aureus.demo.fixtures")

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _path(ticker: str, horizon: str) -> str:
    return os.path.join(FIXTURE_DIR, f"analysis_{ticker.upper()}_{horizon}.json")


@lru_cache(maxsize=64)
def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("Showcase fixture unreadable", extra={"path": path, "error": str(exc)})
        return None


def load_analysis(ticker: str, horizon: str) -> dict[str, Any] | None:
    """The captured payload for this ticker and horizon, or None."""
    raw = _read(_path(ticker, horizon))
    if raw is None:
        return None
    # Parsed per call rather than cached as a dict: callers trim the
    # payload for entitlements, and a shared dict would leak one caller's
    # edits into the next response. Only the file text is cached.
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Showcase fixture is not valid JSON",
                     extra={"ticker": ticker, "horizon": horizon, "error": str(exc)})
        return None
    payload["showcase_snapshot"] = True
    return payload


def save_analysis(ticker: str, horizon: str, payload: dict[str, Any]) -> str:
    """Write a captured payload. Used only by the capture script."""
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    path = _path(ticker, horizon)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True, default=str)
        fh.write("\n")
    _read.cache_clear()
    return path


def available() -> list[str]:
    """Fixture filenames present, for the demo status endpoint."""
    try:
        return sorted(f for f in os.listdir(FIXTURE_DIR) if f.endswith(".json"))
    except OSError:
        return []
