"""
app/scanner/leaderboard.py
----------------------------
The Strong Buy board: who is on it, who comes off, and when anyone is told.

ENTRY (all on a verified score)
    composite >= 80        the analysis engine's own STRONG BUY line
    agreement >= 0.60      the pillars actually concur; 80 reached by one
                           pillar shouting over two that disagree is not a
                           setup anyone should be alerted to
    completeness >= 0.60   enough data behind the number to mean something

EXIT
    composite < 72, agreement < 0.45 or completeness < 0.50 on a verified
    score, or no successful verification for 48 hours.

The gap between the entry and exit lines is hysteresis, and it is the
single most important rule here. With one line at 80, a stock oscillating
between 79.6 and 80.3 enters and leaves the board every fifteen minutes,
and every entry is a push notification. Paying customers would mute the
feature inside a day.

ALERTS
An alert means a stock CROSSED the line, so it requires an earlier verified
score for that horizon that did not qualify. A stock verified for the first
time joins the board silently. Without this, the first day of any
deployment alerts every subscriber about every name the scanner happens to
verify, and each of those alerts reports warm-up, not news.

One per stock per 72 hours, across all horizons. A name that exits and
re-enters within the cooldown returns to the board silently, and a name
that enters two horizons in one run produces one alert.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.analysis.ensemble import _STRONG_BUY_THRESH
from app.core.redis_client import get_redis_client
from app.scanner import HORIZON_LABELS, HORIZONS
from app.scanner.db import engine

logger = logging.getLogger("aureus.scanner.leaderboard")

ENTRY_COMPOSITE = _STRONG_BUY_THRESH
ENTRY_MIN_AGREEMENT = 0.60
ENTRY_MIN_COMPLETENESS = 0.60
EXIT_COMPOSITE = 72.0
EXIT_MIN_AGREEMENT = 0.45
EXIT_MIN_COMPLETENESS = 0.50
STALE_EXIT = timedelta(hours=48)
ALERT_COOLDOWN = timedelta(hours=72)
CANDIDATE_DISPLAY_FLOOR = 72.0
MAX_ENTRANT_CATALYST_REFRESHES = 10

# Which horizon names the alert when a stock enters several at once.
_ALERT_HORIZON_ORDER = ("medium_term", "short_term", "long_term")

_CACHE_KEY = "leaderboard:v1:{}"
_CACHE_TTL = 20 * 60


def rules() -> dict:
    return {
        "entry": {"composite": ENTRY_COMPOSITE, "agreement": ENTRY_MIN_AGREEMENT,
                  "data_completeness": ENTRY_MIN_COMPLETENESS},
        "exit": {"composite": EXIT_COMPOSITE, "agreement": EXIT_MIN_AGREEMENT,
                 "data_completeness": EXIT_MIN_COMPLETENESS, "stale_hours": STALE_EXIT.total_seconds() / 3600},
        "alert_cooldown_hours": ALERT_COOLDOWN.total_seconds() / 3600,
        "candidate_floor": CANDIDATE_DISPLAY_FLOOR,
        "alert_requires_prior_verification": True,
    }


def qualifies_for_entry(v: dict) -> bool:
    return (v["composite"] >= ENTRY_COMPOSITE and v["agreement"] >= ENTRY_MIN_AGREEMENT
            and v["data_completeness"] >= ENTRY_MIN_COMPLETENESS)


def exit_reason(v: dict) -> str | None:
    if v["composite"] < EXIT_COMPOSITE:
        return f"Composite fell to {v['composite']:.1f}, below the {EXIT_COMPOSITE:.0f} exit line"
    if v["agreement"] < EXIT_MIN_AGREEMENT:
        return f"Pillar agreement fell to {v['agreement'] * 100:.0f}%"
    if v["data_completeness"] < EXIT_MIN_COMPLETENESS:
        return f"Data completeness fell to {v['data_completeness'] * 100:.0f}%"
    return None


def compact_catalyst(c: dict | None) -> dict | None:
    if not c:
        return None
    keys = ("title", "type", "type_label", "group", "date", "time", "impact", "direction", "relation", "source_url")
    return {k: c.get(k) for k in keys}


def _with_days(c: dict | None) -> dict | None:
    """days_until is relative to TODAY, so it is derived on read, never stored."""
    if not c or not c.get("date"):
        return c
    from app.catalysts.service import today_et
    days = (date.fromisoformat(c["date"]) - today_et()).days
    # On the day itself the stored relation decides: a filing dated today
    # has happened, an earnings date today has not (catalysts.service._is_scheduled).
    relation = "upcoming" if days > 0 else "recent" if days < 0 else c.get("relation") or "upcoming"
    return {**c, "days_until": days, "relation": relation}


def active_pairs() -> set[tuple[str, str]]:
    with engine().connect() as conn:
        return {(r[0], r[1]) for r in conn.execute(
            text("SELECT horizon, ticker FROM leaderboard_entries WHERE status = 'active'"))}


@dataclass
class Outcome:
    entries: int = 0
    exits: int = 0
    alert_ids: list[str] = field(default_factory=list)
    board_tickers: list[str] = field(default_factory=list)


def _exit(conn, horizon: str, ticker: str, v: dict | None, reason: str, run_id: str, now: datetime) -> None:
    conn.execute(text("""
        UPDATE leaderboard_entries SET status = 'exited', exited_at = :now, exit_reason = :reason
         WHERE horizon = :h AND ticker = :t
    """), {"now": now, "reason": reason, "h": horizon, "t": ticker})
    conn.execute(text("""
        INSERT INTO leaderboard_events (horizon, ticker, event, composite, conviction, reason, run_id)
        VALUES (:h, :t, 'exited', :c, :cv, :reason, CAST(:run AS uuid))
    """), {"h": horizon, "t": ticker, "c": v["composite"] if v else None,
           "cv": v["conviction"] if v else None, "reason": reason, "run": run_id})


def apply_run(run_id: str, verified: dict[str, list[dict]], now: datetime,
              previously_verified: set[tuple[str, str]] | None = None) -> Outcome:
    """
    `previously_verified` holds (horizon, ticker) pairs verified before this
    run. None disables the crossing requirement (used by tests).
    """
    from app.catalysts import service as catalyst_service
    from app.notifications import market_alerts

    out = Outcome()
    with engine().connect() as conn:
        entries = {(r["horizon"], r["ticker"]): dict(r)
                   for r in conn.execute(text("SELECT * FROM leaderboard_entries")).mappings()}
        recently_alerted = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT ticker FROM market_alerts WHERE created_at >= :since"), {"since": now - ALERT_COOLDOWN})}

    active = {k for k, e in entries.items() if e["status"] == "active"}
    entrants = [(h, v) for h in HORIZONS for v in verified.get(h, [])
                if (h, v["ticker"]) not in active and qualifies_for_entry(v)]

    # Catalysts for a new entrant are fetched fresh — the alert is about to
    # name one — and bounded, so a market-wide rally cannot turn one run
    # into hundreds of catalyst calls.
    for t in list(dict.fromkeys(v["ticker"] for _, v in entrants))[:MAX_ENTRANT_CATALYST_REFRESHES]:
        try:
            catalyst_service.refresh_ticker(t, timeout=15)
        except Exception as exc:  # noqa: BLE001
            logger.info("Entrant catalyst refresh failed", extra={"ticker": t, "error": str(exc)})
    tickers = sorted({t for _, t in active} | {v["ticker"] for _, v in entrants})
    primaries = catalyst_service.primary_catalysts_for(tickers) if tickers else {}

    with engine().begin() as conn:
        # Existing members: re-verify, or exit.
        for h in HORIZONS:
            vmap = {v["ticker"]: v for v in verified.get(h, [])}
            for (eh, t) in sorted(active):
                if eh != h:
                    continue
                primary = json.dumps(compact_catalyst(primaries.get(t)))
                v = vmap.get(t)
                if v is None:
                    if now - entries[(h, t)]["last_verified_at"] > STALE_EXIT:
                        _exit(conn, h, t, None, "Not re-verified for 48 hours; its inputs could not be refreshed",
                              run_id, now)
                        out.exits += 1
                    else:
                        conn.execute(text("UPDATE leaderboard_entries SET primary_catalyst = CAST(:p AS jsonb) "
                                          "WHERE horizon = :h AND ticker = :t"), {"p": primary, "h": h, "t": t})
                    continue
                reason = exit_reason(v)
                if reason:
                    _exit(conn, h, t, v, reason, run_id, now)
                    out.exits += 1
                    continue
                conn.execute(text("""
                    UPDATE leaderboard_entries SET composite = :c, conviction = :cv, agreement = :a,
                           data_completeness = :dc, price = :p, driver_pillar = :d,
                           primary_catalyst = CAST(:pc AS jsonb), last_verified_at = :now,
                           peak_composite = GREATEST(COALESCE(peak_composite, :c), :c)
                     WHERE horizon = :h AND ticker = :t
                """), {"c": v["composite"], "cv": v["conviction"], "a": v["agreement"],
                       "dc": v["data_completeness"], "p": v["price"], "d": v["driver_pillar"],
                       "pc": primary, "now": now, "h": h, "t": t})

        # New members, walked in alert-priority order.
        ordered = sorted(entrants, key=lambda hv: _ALERT_HORIZON_ORDER.index(hv[0]))
        alerted_this_run: set[str] = set()
        for h, v in ordered:
            t = v["ticker"]
            primary = compact_catalyst(primaries.get(t))
            crossed = previously_verified is None or (h, t) in previously_verified
            alert_due = crossed and t not in recently_alerted and t not in alerted_this_run
            conn.execute(text("""
                INSERT INTO leaderboard_entries (horizon, ticker, status, composite, conviction, agreement,
                        data_completeness, price, driver_pillar, primary_catalyst, entered_at,
                        last_verified_at, peak_composite, last_alerted_at)
                VALUES (:h, :t, 'active', :c, :cv, :a, :dc, :p, :d, CAST(:pc AS jsonb), :now, :now, :c,
                        CASE WHEN :alert THEN CAST(:now AS timestamptz) END)
                ON CONFLICT (horizon, ticker) DO UPDATE SET
                    status = 'active', composite = EXCLUDED.composite, conviction = EXCLUDED.conviction,
                    agreement = EXCLUDED.agreement, data_completeness = EXCLUDED.data_completeness,
                    price = EXCLUDED.price, driver_pillar = EXCLUDED.driver_pillar,
                    primary_catalyst = EXCLUDED.primary_catalyst, entered_at = EXCLUDED.entered_at,
                    last_verified_at = EXCLUDED.last_verified_at, peak_composite = EXCLUDED.peak_composite,
                    exited_at = NULL, exit_reason = NULL,
                    last_alerted_at = COALESCE(EXCLUDED.last_alerted_at, leaderboard_entries.last_alerted_at)
            """), {"h": h, "t": t, "c": v["composite"], "cv": v["conviction"], "a": v["agreement"],
                   "dc": v["data_completeness"], "p": v["price"], "d": v["driver_pillar"],
                   "pc": json.dumps(primary), "now": now, "alert": alert_due})
            conn.execute(text("""
                INSERT INTO leaderboard_events (horizon, ticker, event, composite, conviction, reason, run_id)
                VALUES (:h, :t, 'entered', :c, :cv, :reason, CAST(:run AS uuid))
            """), {"h": h, "t": t, "c": v["composite"], "cv": v["conviction"], "run": run_id,
                   "reason": (f"Composite {v['composite']:.1f} with {v['agreement'] * 100:.0f}% pillar agreement "
                              f"and {v['data_completeness'] * 100:.0f}% data completeness"
                              + ("" if crossed else "; first verification, so no alert"))})
            out.entries += 1
            if alert_due:
                out.alert_ids.append(market_alerts.create_alert(conn, horizon=h, entry=v, primary=primary))
                alerted_this_run.add(t)

    out.board_tickers = sorted({t for _, t in active_pairs()})
    return out


# ── Reading ───────────────────────────────────────────────────────────────

def _iso(v):
    return v.isoformat() if isinstance(v, (datetime, date)) else v


def build_board(horizon: str) -> dict:
    from app.catalysts.service import primary_catalysts_for

    with engine().connect() as conn:
        members = conn.execute(text("""
            SELECT le.*, su.company_name, su.gics_sector,
                   ss.fundamental_score, ss.technical_score, ss.sentiment_score
              FROM leaderboard_entries le
              LEFT JOIN scanner_universe su ON su.ticker = le.ticker
              LEFT JOIN scanner_snapshots ss ON ss.ticker = le.ticker AND ss.horizon = le.horizon
             WHERE le.horizon = :h AND le.status = 'active'
             ORDER BY le.composite DESC
        """), {"h": horizon}).mappings().all()
        # Candidates must have been verified on the LATEST pass, so the
        # number shown is a verified one rather than an estimate.
        candidates = conn.execute(text("""
            SELECT ss.*, su.company_name, su.gics_sector
              FROM scanner_snapshots ss JOIN scanner_universe su ON su.ticker = ss.ticker
             WHERE ss.horizon = :h AND ss.composite >= :floor
               AND ss.verified_at IS NOT NULL AND ss.verified_at = ss.estimated_at
               AND ss.verified_at >= now() - interval '6 hours'
               AND NOT EXISTS (SELECT 1 FROM leaderboard_entries le
                                WHERE le.horizon = ss.horizon AND le.ticker = ss.ticker AND le.status = 'active')
             ORDER BY ss.composite DESC LIMIT 15
        """), {"h": horizon, "floor": CANDIDATE_DISPLAY_FLOOR}).mappings().all()
        last_run = conn.execute(text("""
            SELECT id, status, market_phase, started_at, finished_at, verified, entries, exits
              FROM scanner_runs WHERE status IN ('completed', 'failed') ORDER BY started_at DESC LIMIT 1
        """)).mappings().first()
        coverage = conn.execute(text("""
            SELECT count(*) AS scored,
                   count(*) FILTER (WHERE verified_at >= now() - interval '24 hours') AS verified_24h,
                   count(*) FILTER (WHERE fundamental_at >= now() - interval '7 days') AS fundamentals_fresh,
                   count(*) FILTER (WHERE sentiment_at >= now() - interval '24 hours') AS sentiment_fresh
              FROM scanner_snapshots WHERE horizon = :h
        """), {"h": horizon}).mappings().first()
        universe_size = conn.execute(text("SELECT count(*) FROM scanner_universe WHERE active")).scalar_one()

    cand_primary = primary_catalysts_for([c["ticker"] for c in candidates]) if candidates else {}

    def pillars(r) -> dict:
        return {"fundamental": r["fundamental_score"], "technical": r["technical_score"],
                "sentiment": r["sentiment_score"]}

    return {
        "horizon": horizon,
        "horizon_label": HORIZON_LABELS[horizon],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_scan": {k: _iso(v) for k, v in last_run.items()} if last_run else None,
        "members": [{
            "ticker": m["ticker"], "company_name": m["company_name"], "sector": m["gics_sector"],
            "price": m["price"], "composite": m["composite"], "conviction": m["conviction"],
            "agreement": m["agreement"], "data_completeness": m["data_completeness"],
            "driver_pillar": m["driver_pillar"], "pillars": pillars(m),
            "primary_catalyst": _with_days(m["primary_catalyst"]),
            "entered_at": _iso(m["entered_at"]), "last_verified_at": _iso(m["last_verified_at"]),
            "peak_composite": m["peak_composite"],
        } for m in members],
        "candidates": [{
            "ticker": c["ticker"], "company_name": c["company_name"], "sector": c["gics_sector"],
            "price": c["price"], "composite": c["composite"], "conviction": c["conviction"],
            "agreement": c["agreement"], "data_completeness": c["data_completeness"],
            "pillars": pillars(c), "verified_at": _iso(c["verified_at"]),
            "primary_catalyst": _with_days(compact_catalyst(cand_primary.get(c["ticker"]))),
            "blocked_by": _blocked_by(c),
        } for c in candidates],
        "coverage": {**dict(coverage), "universe": universe_size},
        "rules": rules(),
    }


def _blocked_by(c) -> str:
    """Why a near-miss is not on the board, in the reader's terms."""
    if c["composite"] < ENTRY_COMPOSITE:
        return f"{ENTRY_COMPOSITE - c['composite']:.1f} points below the entry line"
    if c["agreement"] < ENTRY_MIN_AGREEMENT:
        return f"pillar agreement {c['agreement'] * 100:.0f}% (needs {ENTRY_MIN_AGREEMENT * 100:.0f}%)"
    if c["data_completeness"] < ENTRY_MIN_COMPLETENESS:
        return f"data completeness {c['data_completeness'] * 100:.0f}% (needs {ENTRY_MIN_COMPLETENESS * 100:.0f}%)"
    return "qualifies; enters on the next pass"


def refresh_cache() -> None:
    redis = get_redis_client()
    for h in HORIZONS:
        try:
            redis.setex(_CACHE_KEY.format(h), _CACHE_TTL, json.dumps(build_board(h), default=str))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Leaderboard cache write failed", extra={"horizon": h, "error": str(exc)})


def cached_board(horizon: str) -> dict:
    try:
        raw = get_redis_client().get(_CACHE_KEY.format(horizon))
        if raw:
            board = json.loads(raw)
            # Re-derive relative dates: the cache can outlive midnight.
            for row in board["members"] + board["candidates"]:
                row["primary_catalyst"] = _with_days(row.get("primary_catalyst"))
            return board
    except Exception:  # noqa: BLE001
        pass
    board = build_board(horizon)
    try:
        get_redis_client().setex(_CACHE_KEY.format(horizon), _CACHE_TTL, json.dumps(board, default=str))
    except Exception:  # noqa: BLE001
        pass
    return board


def recent_events(horizon: str | None, limit: int = 50) -> list[dict]:
    with engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT e.id, e.horizon, e.ticker, e.event, e.composite, e.conviction, e.reason, e.created_at,
                   su.company_name
              FROM leaderboard_events e LEFT JOIN scanner_universe su ON su.ticker = e.ticker
             WHERE (CAST(:h AS text) IS NULL OR e.horizon = :h)
             ORDER BY e.created_at DESC LIMIT :limit
        """), {"h": horizon, "limit": limit}).mappings().all()
    return [{k: (str(v) if k == "id" else _iso(v)) for k, v in r.items()} for r in rows]


def scanner_status() -> dict:
    from app.scanner import budget
    from app.scanner.engine import CADENCE, market_phase

    with engine().connect() as conn:
        runs = conn.execute(text("""
            SELECT id, status, market_phase, started_at, finished_at, universe_size, budget_units, units_spent,
                   refreshed_fundamental, refreshed_technical, refreshed_sentiment, estimated, verified,
                   entries, exits, errors, note
              FROM scanner_runs ORDER BY started_at DESC LIMIT 8
        """)).mappings().all()
        universe = conn.execute(text("""
            SELECT count(*) FILTER (WHERE active) AS active, max(updated_at) AS updated_at,
                   (array_agg(source ORDER BY updated_at DESC))[1] AS source
              FROM scanner_universe
        """)).mappings().first()
    phase = market_phase()
    return {
        "market_phase": phase,
        "cadence_minutes": CADENCE[phase].total_seconds() / 60,
        "runs": [{k: (str(v) if k == "id" else _iso(v)) for k, v in r.items()} for r in runs],
        "universe": {k: _iso(v) for k, v in universe.items()},
        "budget": budget.describe(),
        "rules": rules(),
    }
