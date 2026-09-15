"""
Macro catalysts — FOMC rate decisions, parsed from the Federal Reserve.

WHAT IS HERE, AND WHAT DELIBERATELY IS NOT
FOMC meeting dates come from federalreserve.gov's published calendar,
which is public and fetched politely once a day.

CPI, payrolls and GDP release dates are NOT here, for two separate reasons
worth stating rather than papering over:
  · Finnhub's economic calendar is a paid endpoint on this key (HTTP 403).
  · The BLS release schedule page explicitly prohibits automated retrieval
    ("bot activity that doesn't conform to BLS usage policy is prohibited")
    and returns Access Denied to scripts. Scraping it anyway would mean
    working around a site's stated policy.
Hardcoding a list of dates from memory was the third option and the worst
one: a stale or mistyped CPI date on a trading timeline is worse than an
honest gap. The API reports the gap in `unavailable` instead.
"""

import calendar
import logging
import re
from datetime import date, timedelta

import httpx

from app.catalysts.models import Catalyst
from app.catalysts.sources._finnhub import SourceUnavailable
from app.core.config import get_settings

logger = logging.getLogger("aureus.catalysts.macro")

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

_MONTHS: dict[str, int] = {}
for _i in range(1, 13):
    _MONTHS[calendar.month_name[_i].lower()] = _i
    _MONTHS[calendar.month_abbr[_i].lower()] = _i
_MONTHS["sept"] = 9

_YEAR_RE = re.compile(r"(\d{4}) FOMC Meetings")
_MONTH_RE = re.compile(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>')
_DAY_RE = re.compile(r'fomc-meeting__date[^>]*>([^<]+)<')
_DAY_TEXT_RE = re.compile(r"^\s*(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*(\*)?")


def parse_fomc_calendar(html: str) -> list[tuple[date, bool]]:
    """
    Return (decision_date, has_projections) for every scheduled meeting.

    The decision date is the meeting's FINAL day — the statement is released
    that afternoon, so that is the day a price can move. A trailing asterisk
    on the Fed's calendar marks meetings that also publish the Summary of
    Economic Projections.
    """
    years = list(_YEAR_RE.finditer(html))
    meetings: list[tuple[date, bool]] = []
    for idx, ym in enumerate(years):
        year = int(ym.group(1))
        block = html[ym.end(): years[idx + 1].start() if idx + 1 < len(years) else len(html)]
        months, days = _MONTH_RE.findall(block), _DAY_RE.findall(block)
        if len(months) != len(days):
            # Misaligned columns mean the page layout changed. Refusing the
            # year is safer than pairing a month with the wrong days.
            logger.warning("FOMC calendar layout changed; skipping year",
                           extra={"year": year, "months": len(months), "days": len(days)})
            continue
        for month_text, day_text in zip(months, days):
            m = _DAY_TEXT_RE.match(day_text)
            if not m:
                continue  # notation votes and unscheduled calls carry no day range
            names = [p.strip().lower() for p in month_text.split("/")]
            start_month = _MONTHS.get(names[0])
            end_month = _MONTHS.get(names[-1]) if len(names) > 1 else start_month
            if not start_month or not end_month:
                continue
            start_day = int(m.group(1))
            end_day = int(m.group(2) or m.group(1))
            end_year = year + 1 if end_month < start_month else year
            try:
                meetings.append((date(end_year, end_month, end_day), bool(m.group(3))))
            except ValueError:
                continue
    return meetings


def fetch_fomc_catalysts(*, today: date | None = None) -> list[Catalyst]:
    today = today or date.today()
    try:
        r = httpx.get(FOMC_URL, headers={"User-Agent": get_settings().sec_edgar_user_agent}, timeout=20.0)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"federalreserve.gov unreachable: {type(exc).__name__}") from exc
    if r.status_code >= 400:
        raise SourceUnavailable(f"federalreserve.gov HTTP {r.status_code}")

    lo, hi = today - timedelta(days=60), today + timedelta(days=400)
    out: list[Catalyst] = []
    for decision_day, sep in parse_fomc_calendar(r.text):
        if not lo <= decision_day <= hi:
            continue
        out.append(Catalyst(
            dedupe_key=f"fomc:{decision_day.isoformat()}",
            scope="macro", catalyst_type="fomc",
            title="FOMC rate decision" + (" + economic projections" if sep else ""),
            description=("Policy statement at 2:00 p.m. ET"
                         + (", with the Summary of Economic Projections" if sep else "")),
            event_date=decision_day, event_time="14:00 ET", date_confirmed=True,
            impact="high", direction="unknown", source="federal_reserve", source_url=FOMC_URL,
            details={"summary_of_economic_projections": sep},
        ))
    return out
