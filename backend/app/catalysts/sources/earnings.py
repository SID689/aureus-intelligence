"""
Earnings dates, estimates and surprises — Finnhub's earnings calendar.

WHY THIS SOURCE SCALES
One request covers every company reporting in the date range, so the whole
universe's earnings calendar costs a couple of dozen calls a day rather
than one call per ticker. That single property is why earnings can be
refreshed market-wide on a free key at all.

THE ROW CAP, MEASURED
Finnhub returns at most 1,500 rows per request, silently — a 90-day window
came back with exactly 1,500 on 2026-09-14 while the 30-day window held
401, so the longer query was truncated with no error and no flag. Queries
are therefore split into 7-day chunks, and any chunk that still returns the
cap is bisected until it does not. Trusting a single wide query would drop
companies from the calendar without anyone noticing.
"""

import logging
from datetime import date, timedelta

from app.catalysts.models import Catalyst
from app.catalysts.sources._finnhub import SourceUnavailable, finnhub_get

logger = logging.getLogger("aureus.catalysts.earnings")

PROVIDER_ROW_CAP = 1500
_CHUNK_DAYS = 7

# Finnhub's `hour` codes.
_HOUR = {"bmo": "bmo", "amc": "amc", "dmh": "dmh"}

# A reported quarter is a beat or miss only outside this band. Treating a
# one-cent difference on a $3.00 estimate as a "beat" is how headline
# writers manufacture news; the thesis should not do the same.
_INLINE_BAND_PCT = 2.0


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN guard


def _money(v: float | None) -> str | None:
    if v is None:
        return None
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.0f}"


def _fetch_chunk(start: date, end: date, symbol: str | None, wait: float) -> list[dict]:
    params = {"from": start.isoformat(), "to": end.isoformat()}
    if symbol:
        params["symbol"] = symbol
    data = finnhub_get("/calendar/earnings", params, wait_seconds=wait)
    rows = list((data or {}).get("earningsCalendar") or []) if isinstance(data, dict) else []

    if len(rows) >= PROVIDER_ROW_CAP:
        if start < end:
            mid = start + timedelta(days=(end - start).days // 2)
            return (_fetch_chunk(start, mid, symbol, wait)
                    + _fetch_chunk(mid + timedelta(days=1), end, symbol, wait))
        logger.warning("Single-day earnings query hit the provider row cap; rows may be missing",
                       extra={"date": start.isoformat()})
    return rows


def fetch_calendar(start: date, end: date, *, symbol: str | None = None,
                   wait_seconds: float = 65.0) -> list[dict]:
    """Raw calendar rows. A per-symbol query is small enough to skip chunking."""
    if symbol:
        return _fetch_chunk(start, end, symbol.upper(), wait_seconds)
    rows: list[dict] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=_CHUNK_DAYS - 1))
        rows.extend(_fetch_chunk(cursor, chunk_end, None, wait_seconds))
        cursor = chunk_end + timedelta(days=1)
    return rows


def to_catalysts(rows: list[dict], allowed: set[str] | None = None) -> list[Catalyst]:
    out: list[Catalyst] = []
    seen: set[str] = set()
    for r in rows:
        sym = str(r.get("symbol") or "").upper().strip()
        if not sym or (allowed is not None and sym not in allowed):
            continue
        try:
            d = date.fromisoformat(str(r.get("date")))
        except ValueError:
            continue

        quarter, year = r.get("quarter"), r.get("year")
        est, act = _num(r.get("epsEstimate")), _num(r.get("epsActual"))
        rev_est, rev_act = _num(r.get("revenueEstimate")), _num(r.get("revenueActual"))
        reported = act is not None

        surprise: float | None = None
        direction = "unknown"
        if reported and est not in (None, 0.0):
            surprise = (act - est) / abs(est) * 100.0  # type: ignore[operator]
            direction = ("positive" if surprise > _INLINE_BAND_PCT
                         else "negative" if surprise < -_INLINE_BAND_PCT else "neutral")

        period = f"Q{quarter} {year}" if quarter and year else "Quarterly"
        if reported:
            title = f"{period} earnings reported"
            if surprise is not None:
                desc = f"EPS {act:.2f} vs {est:.2f} consensus ({surprise:+.1f}%)"
            else:
                desc = f"EPS {act:.2f} (no consensus estimate on record)"
            if rev_act is not None:
                desc += f" · revenue {_money(rev_act)}"
        else:
            title = f"{period} earnings"
            desc = f"Consensus EPS {est:.2f}" if est is not None else "No consensus EPS published"
            if rev_est is not None:
                desc += f" · revenue est. {_money(rev_est)}"

        # Keyed by fiscal quarter, not by date, so a rescheduled report
        # updates the existing row instead of leaving a ghost on the old day.
        key = f"earnings:{sym}:{year}Q{quarter}" if quarter and year else f"earnings:{sym}:{d.isoformat()}"
        if key in seen:
            continue
        seen.add(key)

        out.append(Catalyst(
            dedupe_key=key, scope="company", ticker=sym, catalyst_type="earnings",
            title=title, description=desc, event_date=d,
            event_time=_HOUR.get(str(r.get("hour") or "").lower()),
            # A future date from a provider calendar is a schedule, not a
            # confirmation. Only a reported quarter is certain.
            date_confirmed=True if reported else None,
            impact="high", direction=direction,  # type: ignore[arg-type]
            source="finnhub_earnings_calendar",
            details={
                "quarter": quarter, "year": year,
                "eps_estimate": est, "eps_actual": act,
                "revenue_estimate": rev_est, "revenue_actual": rev_act,
                "surprise_pct": round(surprise, 2) if surprise is not None else None,
            },
        ))
    return out


__all__ = ["fetch_calendar", "to_catalysts", "SourceUnavailable", "PROVIDER_ROW_CAP"]
