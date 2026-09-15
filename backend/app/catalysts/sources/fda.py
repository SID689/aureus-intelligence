"""
FDA advisory committee meetings — Finnhub's FDA calendar.

ATTACHED TO THE SECTOR, NEVER TO A TICKER
The free calendar describes each meeting by committee — "Pediatric Advisory
Committee", "Molecular and Clinical Genetics Panel" — and does not name the
sponsoring company (checked 2026-09-14 across all 591 rows). Assigning a
meeting to a ticker would therefore require guessing from drug or device
names, and a wrong guess puts a fabricated regulatory event on someone's
investment timeline. So these are stored as sector events and shown only on
Health Care names, labelled for exactly what they are.

Company-specific FDA outcomes — approvals, complete response letters — do
reach the timeline, through classified news in news.py, where the company
IS named.
"""

import re
from datetime import date, timedelta

from app.catalysts.models import Catalyst, stable_hash
from app.catalysts.sources._finnhub import finnhub_get

HEALTH_CARE = "Health Care"

_LEADING_DATE = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}:\s*")
_TRAILING_DATE = re.compile(r"\s*-\s*\d{2}/\d{2}/\d{4}\s*$")
_NOISE = re.compile(r"\s*Meeting Announcement\s*$", re.I)


def fetch_fda_adcomm_catalysts(*, today: date | None = None, wait_seconds: float = 65.0) -> list[Catalyst]:
    today = today or date.today()
    rows = finnhub_get("/fda-advisory-committee-calendar", wait_seconds=wait_seconds)
    if not isinstance(rows, list):
        return []

    lo, hi = today - timedelta(days=30), today + timedelta(days=180)
    out: list[Catalyst] = []
    for row in rows:
        try:
            day = date.fromisoformat(str(row.get("fromDate", ""))[:10])
        except ValueError:
            continue
        if not lo <= day <= hi:
            continue
        desc = _NOISE.sub("", _TRAILING_DATE.sub("", _LEADING_DATE.sub("", str(row.get("eventDescription") or "")))).strip()
        if not desc:
            continue
        out.append(Catalyst(
            dedupe_key=f"fda_adcomm:{day.isoformat()}:{stable_hash(desc)}",
            scope="sector", sector=HEALTH_CARE, catalyst_type="fda_advisory_committee",
            title="FDA advisory committee meeting", description=desc,
            event_date=day, date_confirmed=True, impact="low", direction="unknown",
            source="finnhub_fda_calendar", source_url=row.get("url"),
            details={"committee": desc},
        ))
    return out


def is_health_care(sector: str | None) -> bool:
    """
    GICS says "Health Care"; Finnhub's company profile says things like
    "Pharmaceuticals" or "Biotechnology". Either should see these events.
    """
    if not sector:
        return False
    s = sector.lower()
    return any(k in s for k in ("health", "pharma", "biotech", "life science", "medical"))
