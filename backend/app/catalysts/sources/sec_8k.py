"""
Material corporate events from SEC Form 8-K filings.

WHY 8-Ks, AND WHY ITEM CODES RATHER THAN READING THE TEXT
Public companies must file an 8-K within four business days of a material
event, and each filing declares which ITEMS it reports under — a numbered
taxonomy defined by the SEC. Item 2.01 is a completed acquisition, 4.02 is
a statement that prior financials can no longer be relied on, 1.03 is
bankruptcy. That makes item codes an authoritative, free, legally-mandated
classification: no keyword guessing and no model reading press releases.

Deliberately skipped:
  2.02  Results of operations — the earnings calendar already covers it,
        and showing each quarter twice would crowd the timeline.
  7.01  Regulation FD disclosure — usually slide decks and conference
        appearances, not events.
  9.01  Financial statements and exhibits — attachments, never an event.

Direction is assigned only where the item itself is unambiguous. A
material agreement (1.01) might be a transformative contract or a new
credit line; leadership changes (5.02) might be a departure or a strong
hire. Those stay "unknown" rather than being guessed at.
"""

import logging
import time
from datetime import date, timedelta

import httpx

from app.catalysts.models import Catalyst
from app.catalysts.sources._finnhub import SourceUnavailable
from app.core.config import get_settings
from app.ingestion.rate_limiter import RedisTokenBucket

logger = logging.getLogger("aureus.catalysts.sec_8k")

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_CIK_CACHE_KEY = "sec:company_tickers:v1"
_CIK_CACHE_TTL = 86400

# SEC's fair-access policy allows 10 requests/second. Stay under it.
_bucket = RedisTokenBucket("sec_edgar", max_calls=8, window_seconds=1)

# item -> (type, title, impact, direction)
ITEM_MAP: dict[str, tuple[str, str, str, str]] = {
    "1.01": ("material_agreement", "Entered a material definitive agreement", "medium", "unknown"),
    "1.02": ("material_agreement", "Terminated a material definitive agreement", "medium", "unknown"),
    "1.03": ("bankruptcy", "Bankruptcy or receivership", "high", "negative"),
    "1.05": ("cybersecurity_incident", "Material cybersecurity incident", "high", "negative"),
    "2.01": ("merger_acquisition", "Completed an acquisition or disposition of assets", "high", "unknown"),
    "2.03": ("financing", "Created a direct financial obligation", "low", "unknown"),
    "2.04": ("financing", "Event accelerating a financial obligation", "high", "negative"),
    "2.05": ("restructuring", "Exit or disposal activities (restructuring)", "medium", "unknown"),
    "2.06": ("impairment", "Material impairment", "high", "negative"),
    "3.01": ("delisting", "Delisting notice or listing-standard failure", "high", "negative"),
    "3.02": ("financing", "Unregistered sale of equity securities", "medium", "unknown"),
    "3.03": ("shareholder_rights", "Material modification to holders' rights", "medium", "unknown"),
    "4.01": ("auditor_change", "Change in certifying accountant", "medium", "unknown"),
    "4.02": ("accounting_restatement", "Prior financial statements can no longer be relied on", "high", "negative"),
    "5.01": ("control_change", "Change in control of the company", "high", "unknown"),
    "5.02": ("leadership_change", "Director or officer departure or appointment", "medium", "unknown"),
    "5.03": ("governance", "Amendment to articles or bylaws", "low", "unknown"),
    "5.07": ("shareholder_vote", "Shareholder vote results", "low", "neutral"),
    "8.01": ("other_material_event", "Other material event", "low", "unknown"),
}


def _headers() -> dict[str, str]:
    return {"User-Agent": get_settings().sec_edgar_user_agent, "Accept-Encoding": "gzip, deflate"}


def _pace(max_wait: float = 5.0) -> None:
    deadline = time.monotonic() + max_wait
    while not _bucket.allow():
        if time.monotonic() >= deadline:
            raise SourceUnavailable("SEC request budget exhausted")
        time.sleep(0.15)


def _get_json(url: str) -> dict:
    _pace()
    try:
        r = httpx.get(url, headers=_headers(), timeout=20.0)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"SEC unreachable: {type(exc).__name__}") from exc
    if r.status_code == 403:
        raise SourceUnavailable("SEC refused the request: check SEC_EDGAR_USER_AGENT")
    if r.status_code == 404:
        return {}
    if r.status_code >= 400:
        raise SourceUnavailable(f"SEC HTTP {r.status_code}")
    return r.json()


def resolve_cik(ticker: str) -> int | None:
    """
    Ticker -> CIK. SEC writes class shares with a hyphen (BRK-B) where
    Wikipedia and Finnhub use a dot (BRK.B), so both spellings are tried.
    """
    import json
    from app.core.redis_client import get_redis_client

    mapping: dict[str, int] | None = None
    try:
        raw = get_redis_client().get(_CIK_CACHE_KEY)
        if raw:
            mapping = json.loads(raw)
    except Exception:  # noqa: BLE001
        mapping = None

    if mapping is None:
        data = _get_json(_TICKER_MAP_URL)
        mapping = {str(v["ticker"]).upper(): int(v["cik_str"]) for v in data.values()}
        try:
            get_redis_client().setex(_CIK_CACHE_KEY, _CIK_CACHE_TTL, json.dumps(mapping))
        except Exception:  # noqa: BLE001
            pass

    t = ticker.upper().strip()
    return mapping.get(t) or mapping.get(t.replace(".", "-")) or mapping.get(t.replace("-", "."))


def fetch_8k_catalysts(ticker: str, *, lookback_days: int = 180, today: date | None = None) -> list[Catalyst]:
    today = today or date.today()
    cik = resolve_cik(ticker)
    if cik is None:
        return []

    data = _get_json(_SUBMISSIONS_URL.format(cik=cik))
    recent = (data.get("filings") or {}).get("recent") or {}
    forms: list[str] = recent.get("form") or []
    cutoff = today - timedelta(days=lookback_days)

    out: list[Catalyst] = []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        try:
            filed = date.fromisoformat(recent["filingDate"][i])
        except (KeyError, IndexError, ValueError):
            continue
        if filed < cutoff:
            break  # the recent arrays are newest-first

        # reportDate is the date of the EVENT; filingDate can be up to four
        # business days later. The event date is the one that belongs on a
        # timeline.
        report_raw = (recent.get("reportDate") or [""] * len(forms))[i] or ""
        try:
            event_day = date.fromisoformat(report_raw) if report_raw else filed
        except ValueError:
            event_day = filed

        accession = recent["accessionNumber"][i]
        doc = (recent.get("primaryDocument") or [""] * len(forms))[i]
        doc_desc = (recent.get("primaryDocDescription") or [""] * len(forms))[i] or None
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{doc}"
               if doc else None)
        items = [x.strip() for x in ((recent.get("items") or [""] * len(forms))[i] or "").split(",") if x.strip()]

        for item in items:
            spec = ITEM_MAP.get(item)
            if not spec:
                continue
            ctype, label, impact, direction = spec
            out.append(Catalyst(
                dedupe_key=f"sec8k:{accession}:{item}",
                scope="company", ticker=ticker, catalyst_type=ctype,
                title=label + (" (amended filing)" if form == "8-K/A" else ""),
                description=doc_desc if doc_desc and doc_desc.upper() not in ("8-K", "FORM 8-K") else f"Form {form}, Item {item}",
                event_date=event_day, date_confirmed=True,
                impact=impact, direction=direction,  # type: ignore[arg-type]
                source="sec_edgar_8k", source_url=url,
                details={"form": form, "item": item, "accession": accession, "filed": filed.isoformat()},
            ))
    return out
