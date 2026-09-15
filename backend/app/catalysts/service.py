"""
app/catalysts/service.py
--------------------------
The catalyst API the rest of the platform uses.

WHY CATALYSTS DO NOT MOVE THE COMPOSITE SCORE
It is tempting to nudge the score when earnings are a week away. It would
be wrong in both directions. An upcoming report is not directional: pulling
pre-earnings names toward neutral punishes a stock the week before a likely
beat, and pushing them toward conviction rewards a coin flip. And catalysts
that already happened — a beat, a restatement — are already in the price and
in the sentiment pillar's coverage, so scoring them again would count the
same news twice.

What a catalyst genuinely changes is the SHAPE OF THE RISK and the argument
around the position. So that is exactly where they are used: dated points in
the bull and bear cases, dated conditions in "what would change this", the
analysis timeline, and the leaderboard's context column.

SOURCE FRESHNESS
Per-ticker sources are refreshed on demand when the analysis page asks, and
remembered in Redis so the next request is free:
    earnings   12h   (reschedules are rare and announced days ahead)
    sec_8k      6h   (a filing can land any business day)
    dividends   5d   (declared weeks before the ex-date)
A failed source is remembered for 15 minutes, so an outage costs one attempt
per quarter hour rather than one per page view.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.catalysts import store
from app.catalysts.models import IMPACT_RANK, TYPE_GROUPS, TYPE_LABELS
from app.catalysts.sources import dividends, earnings, fda, macro, news, sec_8k
from app.catalysts.sources._finnhub import SourceUnavailable

logger = logging.getLogger("aureus.catalysts.service")

_ET = ZoneInfo("America/New_York")

HORIZON_FORWARD_DAYS: dict[str, int] = {"short_term": 30, "medium_term": 180, "long_term": 365}
LOOKBACK_DAYS = 90

_FRESH_TTL: dict[str, int] = {"earnings": 12 * 3600, "sec_8k": 6 * 3600, "dividends": 5 * 86400}
_FAILURE_TTL = 15 * 60

# Stated rather than hidden. Each entry is a catalyst class a user might
# reasonably expect and will not find — with the concrete reason.
UNAVAILABLE_SOURCES: list[dict] = [
    {
        "name": "Economic data releases (CPI, payrolls, GDP)",
        "reason": ("Finnhub's economic calendar is a paid endpoint on this plan, and the Bureau of "
                   "Labor Statistics prohibits automated retrieval of its release schedule."),
        "to_enable": "A paid Finnhub plan or a licensed macro calendar feed.",
    },
    {
        "name": "Dedicated M&A deal database",
        "reason": ("There is no free structured deal feed. Deals appear here from SEC 8-K Items "
                   "1.01, 2.01 and 5.01 and from classified news coverage instead."),
        "to_enable": "A licensed deals dataset.",
    },
    {
        "name": "Company-specific FDA advisory meetings",
        "reason": ("The free FDA calendar names the committee, not the sponsoring company, so a meeting "
                   "cannot be tied to a ticker without guessing. Meetings are shown as sector events on "
                   "Health Care names; company FDA decisions come through news."),
        "to_enable": "A biotech catalyst dataset with sponsor attribution.",
    },
]


def today_et() -> date:
    """US catalysts happen on US dates. UTC would roll 'today' over at 8 p.m. ET."""
    return datetime.now(_ET).date()


# ── Freshness bookkeeping ────────────────────────────────────────────────

def _fresh_key(source: str, ticker: str) -> str:
    return f"catalysts:fresh:{source}:{ticker}"


def _freshness(source: str, ticker: str) -> str | None:
    try:
        from app.core.redis_client import get_redis_client
        raw = get_redis_client().get(_fresh_key(source, ticker))
        return raw.decode() if isinstance(raw, bytes) else raw
    except Exception:  # noqa: BLE001
        return None


def _mark(source: str, ticker: str, ok: bool, detail: str = "") -> None:
    try:
        from app.core.redis_client import get_redis_client
        ttl = _FRESH_TTL[source] if ok else _FAILURE_TTL
        get_redis_client().setex(_fresh_key(source, ticker), ttl, "ok" if ok else f"failed:{detail[:120]}")
    except Exception:  # noqa: BLE001
        pass


def needs_refresh(ticker: str) -> bool:
    t = ticker.upper().strip()
    return any(_freshness(s, t) is None for s in _FRESH_TTL)


# ── Per-ticker refresh ───────────────────────────────────────────────────

def _refresh_earnings(ticker: str, today: date) -> int:
    rows = earnings.fetch_calendar(today - timedelta(days=LOOKBACK_DAYS + 30),
                                   today + timedelta(days=380), symbol=ticker, wait_seconds=0)
    return store.upsert(earnings.to_catalysts(rows, allowed={ticker}))


def _refresh_8k(ticker: str, today: date) -> int:
    return store.upsert(sec_8k.fetch_8k_catalysts(ticker, lookback_days=LOOKBACK_DAYS + 30, today=today))


def _refresh_dividends(ticker: str, today: date) -> int:
    return store.upsert(dividends.fetch_dividend_catalysts(ticker, today=today))


_SOURCES = {"earnings": _refresh_earnings, "sec_8k": _refresh_8k, "dividends": _refresh_dividends}


def _run_source(name: str, ticker: str, today: date) -> str:
    try:
        n = _SOURCES[name](ticker, today)
        _mark(name, ticker, ok=True)
        return f"refreshed ({n})"
    except SourceUnavailable as exc:
        _mark(name, ticker, ok=False, detail=str(exc))
        return f"unavailable: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Catalyst source failed", extra={"source": name, "ticker": ticker, "error": str(exc)})
        _mark(name, ticker, ok=False, detail=type(exc).__name__)
        return "unavailable: unexpected error"


def refresh_ticker(ticker: str, *, today: date | None = None, timeout: float = 8.0) -> dict[str, str]:
    """
    Refresh whichever per-ticker sources are stale, concurrently.

    Bounded by `timeout` so the analysis request never waits on a slow
    upstream. Anything still running at the deadline is reported as
    "pending" and keeps going in the background — its rows appear on the
    next load rather than blocking this one.
    """
    t = ticker.upper().strip()
    today = today or today_et()
    status: dict[str, str] = {}
    todo: list[str] = []
    for name in _SOURCES:
        state = _freshness(name, t)
        if state == "ok":
            status[name] = "cached"
        elif state and state.startswith("failed:"):
            status[name] = f"unavailable: {state[7:]} (retrying shortly)"
        else:
            todo.append(name)
    if not todo:
        return status

    pool = ThreadPoolExecutor(max_workers=len(todo), thread_name_prefix=f"catalysts-{t}")
    futures = {pool.submit(_run_source, name, t, today): name for name in todo}
    done, not_done = wait(futures, timeout=timeout)
    for f in done:
        status[futures[f]] = f.result()
    for f in not_done:
        status[futures[f]] = "pending"
    # Not a `with` block: its __exit__ waits for every future, which is
    # exactly the unbounded wait the timeout above exists to avoid.
    pool.shutdown(wait=False)
    return status


def record_news_catalysts(ticker: str, sentiment_catalysts: list[dict] | None) -> int:
    """Classify headlines the sentiment pillar already fetched. Costs no API calls."""
    if not sentiment_catalysts:
        return 0
    try:
        return store.upsert(news.catalysts_from_sentiment(ticker, sentiment_catalysts, today=today_et()))
    except Exception as exc:  # noqa: BLE001
        logger.warning("News catalyst classification failed", extra={"ticker": ticker, "error": str(exc)})
        return 0



def reclassify_news_catalysts() -> dict:
    """
    Re-derive every stored news catalyst from its headline under the
    CURRENT rules in sources/news.py.

    A rule fix otherwise only reaches headlines fetched after it ships, and
    a misread one already stored keeps arguing in theses for up to a
    quarter. Runs in the daily sweep; run it by hand after changing a rule.
    A headline the rules no longer classify is removed; one whose type
    changed is re-keyed.
    """
    with store._engine().connect() as conn:
        rows = [dict(r) for r in conn.execute(text(
            "SELECT id, dedupe_key, ticker, event_date, source, source_url, details "
            "FROM catalysts WHERE source LIKE 'news:%'")).mappings()]
    stale: list[str] = []
    fresh = []
    for r in rows:
        headline = (r["details"] or {}).get("headline")
        if not headline or not r["ticker"]:
            continue
        item = {"headline": headline, "url": r["source_url"], "source": r["source"][5:],
                "published_at": f"{r['event_date'].isoformat()}T12:00:00+00:00"}
        # today=event_date so the 30-day recency filter cannot mistake an old
        # headline for an unclassifiable one.
        derived = news.catalysts_from_sentiment(r["ticker"], [item], today=r["event_date"])
        if not derived or derived[0].dedupe_key != r["dedupe_key"]:
            stale.append(str(r["id"]))
        fresh.extend(derived)
    if stale:
        with store._engine().begin() as conn:
            conn.execute(text("DELETE FROM catalysts WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": stale})
    store.upsert(fresh)
    return {"checked": len(rows), "removed_or_rekeyed": len(stale), "rewritten": len(fresh)}

# ── Reading ──────────────────────────────────────────────────────────────

def _is_scheduled(row: dict) -> bool:
    """
    Whether an event dated TODAY is still ahead.

    A news report or an 8-K dated today describes something that has
    already happened. An earnings date not yet reported, an FOMC decision
    or an ex-dividend date has not. Splitting on the date alone put this
    morning's lawsuit headline under "upcoming", where the thesis ignores
    it and the timeline presents it as a scheduled event.
    """
    source = (row["source"] or "").lower()
    if source.startswith("news:") or "8k" in source or "8-k" in source or source.startswith("sec"):
        return False
    if row["catalyst_type"] == "earnings" and (row["details"] or {}).get("eps_actual") is not None:
        return False
    return True


def _collapse_news(items: list[dict]) -> list[dict]:
    """
    Five outlets covering one lawsuit are one catalyst, not five.

    News rows are deduplicated per article at write time, which is right
    for storage and wrong for display. Collapsed on (type, date, direction);
    rows arrive ordered by impact within a day, so the survivor is the
    highest-impact report, and the count of the rest is kept.
    """
    out: list[dict] = []
    kept: dict[tuple, dict] = {}
    for i in items:
        if not (i["source"] or "").startswith("news:"):
            out.append(i)
            continue
        key = (i["type"], i["date"], i["direction"])
        if key in kept:
            first = kept[key]
            first["details"] = {**first["details"], "report_count": first["details"].get("report_count", 1) + 1}
            continue
        kept[key] = i
        out.append(i)
    return out


def _decorate(row: dict, today: date) -> dict:
    d: date = row["event_date"]
    days = (d - today).days
    return {
        "id": str(row["id"]),
        "scope": row["scope"],
        "ticker": row["ticker"],
        "sector": row["sector"],
        "type": row["catalyst_type"],
        "type_label": TYPE_LABELS.get(row["catalyst_type"], row["catalyst_type"]),
        "group": TYPE_GROUPS.get(row["catalyst_type"], "corporate"),
        "title": row["title"],
        "description": row["description"],
        "date": d.isoformat(),
        "time": row["event_time"],
        "date_confirmed": row["date_confirmed"],
        "impact": row["impact"],
        "direction": row["direction"],
        "source": row["source"],
        "source_url": row["source_url"],
        "details": row["details"] or {},
        "days_until": days,
        "timing": "upcoming" if days > 0 or (days == 0 and _is_scheduled(row)) else "recent",
    }


def primary_catalyst(items: list[dict]) -> dict | None:
    """
    The single catalyst most worth a glance, for compact surfaces.

    In order: a high-impact event in the next 45 days, one in the last 30,
    one in the next 100; then a medium-impact event in the last 14 days, the
    next 45, the last 30. A scheduled report three months out says more
    about a stock than last week's routine director appointment, and 8-K
    item 5.02 cannot tell that apart from a CEO leaving. Company events only — "FOMC in 3 days" is true of every stock and so says
    nothing about this one.
    """
    company = [i for i in items if i["scope"] == "company"]
    def ahead(i: dict, impact: str, days: int = 45) -> bool:
        return i["timing"] == "upcoming" and i["days_until"] <= days and i["impact"] == impact

    def behind(i: dict, impact: str, days: int = 30) -> bool:
        return i["timing"] == "recent" and i["days_until"] >= -days and i["impact"] == impact

    rules = [
        (lambda i: ahead(i, "high"), lambda i: i["days_until"], "upcoming"),
        (lambda i: behind(i, "high"), lambda i: -i["days_until"], "recent"),
        (lambda i: ahead(i, "high", 100), lambda i: i["days_until"], "upcoming"),
        (lambda i: behind(i, "medium", 14), lambda i: -i["days_until"], "recent"),
        (lambda i: ahead(i, "medium"), lambda i: i["days_until"], "upcoming"),
        (lambda i: behind(i, "medium"), lambda i: -i["days_until"], "recent"),
    ]
    for pred, key, relation in rules:
        hits = sorted((i for i in company if pred(i)), key=key)
        if hits:
            return {**hits[0], "relation": relation}
    return None


def universe_sector(ticker: str) -> str | None:
    try:
        with store._engine().connect() as conn:
            row = conn.execute(text("SELECT gics_sector FROM scanner_universe WHERE ticker = :t"),
                               {"t": ticker}).fetchone()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


def get_timeline(ticker: str, horizon: str = "medium_term", *, sector: str | None = None,
                 refresh: bool = True, today: date | None = None, timeout: float = 8.0) -> dict:
    t = ticker.upper().strip()
    today = today or today_et()
    forward = HORIZON_FORWARD_DAYS.get(horizon, HORIZON_FORWARD_DAYS["medium_term"])
    status = refresh_ticker(t, today=today, timeout=timeout) if refresh else {}
    sector = universe_sector(t) or sector

    rows = store.query_window(t, [fda.HEALTH_CARE] if fda.is_health_care(sector) else [],
                              today - timedelta(days=LOOKBACK_DAYS), today + timedelta(days=forward))
    items = _collapse_news([_decorate(r, today) for r in rows])
    upcoming = [i for i in items if i["timing"] == "upcoming"]
    recent = sorted((i for i in items if i["timing"] == "recent"), key=lambda i: i["days_until"], reverse=True)

    return {
        "ticker": t,
        "horizon": horizon,
        "as_of": today.isoformat(),
        "window": {"lookback_days": LOOKBACK_DAYS, "forward_days": forward},
        "sector": sector,
        "upcoming": upcoming,
        "recent": recent,
        "primary": primary_catalyst(items),
        "counts": {
            "upcoming": len(upcoming),
            "recent": len(recent),
            "high_impact_upcoming": sum(1 for i in upcoming if i["scope"] == "company" and i["impact"] == "high"),
        },
        "sources": status,
        "unavailable": UNAVAILABLE_SOURCES,
    }


def primary_catalysts_for(tickers: list[str], today: date | None = None) -> dict[str, dict | None]:
    """Batch form for the leaderboard: one query, no refresh."""
    today = today or today_et()
    # The window must cover the widest rule in primary_catalyst (100 days
    # ahead), or that rule silently never sees the events it exists for.
    rows = store.company_window([t.upper() for t in tickers], today - timedelta(days=30), today + timedelta(days=100))
    by_ticker: dict[str, list[dict]] = {t.upper(): [] for t in tickers}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(_decorate(r, today))
    return {t: primary_catalyst(_collapse_news(items)) for t, items in by_ticker.items()}


def macro_upcoming(days: int = 90, today: date | None = None) -> list[dict]:
    today = today or today_et()
    return [_decorate(r, today) for r in store.macro_window(today, today + timedelta(days=days))]


# ── Market-wide batch ────────────────────────────────────────────────────

def refresh_market_wide(allowed_tickers: set[str], *, today: date | None = None) -> dict:
    """
    The scheduled sweep. Earnings for the whole universe from a few dozen
    calendar calls, FOMC dates, and the FDA calendar.

    Only tickers in `allowed_tickers` are stored from the earnings calendar.
    It lists every listed company reporting — thousands a quarter — and
    storing all of them would grow the table with names no screen here ever
    shows. Anything outside the set is fetched per symbol when viewed.
    """
    today = today or today_et()
    result: dict[str, dict] = {}

    try:
        rows = earnings.fetch_calendar(today - timedelta(days=35), today + timedelta(days=120), wait_seconds=65)
        cats = earnings.to_catalysts(rows, allowed={t.upper() for t in allowed_tickers})
        result["earnings"] = {"calendar_rows": len(rows), "stored": store.upsert(cats)}
        for t in {c.ticker for c in cats if c.ticker}:
            _mark("earnings", t, ok=True)
    except SourceUnavailable as exc:
        result["earnings"] = {"error": str(exc)}

    for name, fn in (("fomc", lambda: macro.fetch_fomc_catalysts(today=today)),
                     ("fda_advisory", lambda: fda.fetch_fda_adcomm_catalysts(today=today))):
        try:
            result[name] = {"stored": store.upsert(fn())}
        except SourceUnavailable as exc:
            result[name] = {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Market-wide catalyst source failed", extra={"source": name, "error": str(exc)})
            result[name] = {"error": type(exc).__name__}

    return result


def impact_sort_key(item: dict) -> tuple:
    return (IMPACT_RANK.get(item["impact"], 3), abs(item["days_until"]))
