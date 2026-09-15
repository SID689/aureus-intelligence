"""
app/scanner/engine.py
-----------------------
Scores the S&P 500 on all three horizons with the analysis page's own
arithmetic, without exhausting a single API quota.

THE PROBLEM
A full analysis costs roughly six provider calls. Done naively, 503
tickers is ~3,000 calls per sweep, and Finnhub's free plan allows 60 a
minute — shared with every user. A scanner built that way either takes
most of an hour per pass or starves the site.

THE FUNNEL
Each pillar is refreshed on the clock its data actually moves on.

  1. Prices, every run, for every ticker. Batch downloads of 100 tickers
     make this about six requests, and the technical pillar is recomputed
     for the whole index each time.

  2. Fundamentals change when a company reports. The RAW data is cached for
     eight days and refreshed when older than seven (five for names near
     the board). The pillar itself is recomputed every run from that cache
     with the latest price, so the price-sensitive parts stay current at
     zero cost.

  3. Sentiment is fast-moving and the expensive part. It is refreshed in
     priority order: current board members, then names whose ESTIMATED
     composite is within reach of the board, then the stalest of the rest.

  4. Verification. A stock can only enter, or stay on, the board on a
     VERIFIED score: prices from this run, sentiment at most three hours
     old, fundamentals at most seven days. Estimates decide what to spend
     quota on. They never trigger an alert.

SCORING PARITY
Pillars are scored by run_technical_analysis, run_fundamental_analysis and
score_sentiment, and pooled by ensemble.pool_pillars — the same functions
the analysis page runs. The only differences are input freshness, which is
bounded above, and the bar source (see inputs.prime_analysis_cache for how
the page is handed the scanner's bars for the names on the board).

MARKET HOURS
The phase check is weekday 9:30-16:00 New York time. It does not know
exchange holidays; on one, the scanner runs at its open-market cadence
over unchanged prices, which costs quota the budget already caps and
changes no scores.
"""

import logging
import secrets
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.analysis.ensemble import _HORIZON_CONFIG, pool_pillars, sector_metrics
from app.core.redis_client import get_redis_client
from app.scanner import HORIZONS, budget as scan_budget, inputs, leaderboard
from app.scanner.db import engine
from app.scanner.universe import active_universe

logger = logging.getLogger("aureus.scanner.engine")

_ET = ZoneInfo("America/New_York")

CADENCE = {"open": timedelta(minutes=15), "closed": timedelta(minutes=60)}
RUN_DEADLINE_SECONDS = 11 * 60          # well inside the task's 14-minute soft limit
FUNDAMENTAL_MAX_AGE = timedelta(days=7)
FUNDAMENTAL_PRIORITY_AGE = timedelta(days=5)
SENTIMENT_VERIFY_AGE = timedelta(hours=3)
SENTIMENT_ROUTINE_AGE = timedelta(hours=20)
CANDIDATE_FLOOR = 72.0                  # estimated composite that earns priority refreshes
PRIME_CACHE_LIMIT = 40

_LOCK_KEY = "scanner:lock"
_LOCK_TTL = 20 * 60


def market_phase(now: datetime | None = None) -> str:
    et = (now or datetime.now(timezone.utc)).astimezone(_ET)
    if et.weekday() >= 5:
        return "closed"
    minutes = et.hour * 60 + et.minute
    return "open" if 9 * 60 + 30 <= minutes < 16 * 60 else "closed"


@dataclass
class Reading:
    z: float
    score: float
    completeness: float
    at: datetime


def _from_result(r, at: datetime) -> Reading:
    return Reading(float(r.evidence_z), float(r.score), float(r.data_completeness), at)


def _from_row(row: dict | None, pillar: str) -> Reading | None:
    if not row:
        return None
    z, at = row.get(f"{pillar}_z"), row.get(f"{pillar}_at")
    if z is None or at is None:
        return None
    return Reading(z, row.get(f"{pillar}_score") or 50.0, row.get(f"{pillar}_completeness") or 0.0, at)


def _pool(horizon: str, f: Reading | None, t: Reading | None, s: Reading | None):
    res = pool_pillars(
        horizon,
        fundamental=(f.z, f.completeness) if f else (0.0, 0.0),
        technical=(t.z, t.completeness) if t else (0.0, 0.0),
        sentiment=(s.z, s.completeness) if s else (0.0, 0.0),
    )
    # The analysis page's overall_data_completeness: a plain mean, missing pillars counting as zero.
    completeness = round(sum(r.completeness if r else 0.0 for r in (f, t, s)) / 3, 3)
    return res, completeness


def _driver(res, readings: dict[str, Reading | None]) -> str | None:
    """The pillar contributing the most positive weighted evidence."""
    contrib = {p: res.effective_weights.get(p, 0.0) * r.z for p, r in readings.items() if r}
    if not contrib:
        return None
    best = max(contrib, key=contrib.get)
    return best if contrib[best] > 0 else None


@dataclass
class RunStats:
    universe_size: int = 0
    budget_units: int = 0
    units_spent: int = 0
    refreshed_fundamental: int = 0
    refreshed_technical: int = 0
    refreshed_sentiment: int = 0
    estimated: int = 0
    verified: int = 0
    entries: int = 0
    exits: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["note"] = "; ".join(d.pop("notes"))[:1000] or None
        return d


# ── Run bookkeeping ───────────────────────────────────────────────────────

def _due(phase: str, now: datetime) -> bool:
    with engine().connect() as conn:
        last = conn.execute(text(
            "SELECT started_at FROM scanner_runs WHERE status = 'completed' ORDER BY started_at DESC LIMIT 1"
        )).scalar()
    # A minute of slack so a run that took 40 seconds to start is not skipped.
    return last is None or now - last >= CADENCE[phase] - timedelta(minutes=1)


def _start_run(phase: str, stats: RunStats) -> str:
    with engine().begin() as conn:
        return str(conn.execute(text("""
            INSERT INTO scanner_runs (horizon, status, market_phase, universe_size, budget_units)
            VALUES ('all', 'running', :phase, :u, :b) RETURNING id
        """), {"phase": phase, "u": stats.universe_size, "b": stats.budget_units}).scalar_one())


def _finish_run(run_id: str, status: str, stats: RunStats) -> None:
    d = stats.as_dict()
    with engine().begin() as conn:
        conn.execute(text("""
            UPDATE scanner_runs SET status = :status, finished_at = now(),
                   universe_size = :universe_size, budget_units = :budget_units, units_spent = :units_spent,
                   refreshed_fundamental = :refreshed_fundamental, refreshed_technical = :refreshed_technical,
                   refreshed_sentiment = :refreshed_sentiment, estimated = :estimated, verified = :verified,
                   entries = :entries, exits = :exits, errors = :errors, note = :note
             WHERE id = CAST(:id AS uuid)
        """), {**d, "status": status, "id": run_id})


def _release_lock(token: str) -> None:
    try:
        get_redis_client().eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1, _LOCK_KEY, token,
        )
    except Exception:  # noqa: BLE001 — the TTL releases it regardless
        pass


# ── Snapshots ─────────────────────────────────────────────────────────────

def _load_snapshots(tickers: list[str]) -> dict[tuple[str, str], dict]:
    with engine().connect() as conn:
        rows = conn.execute(text("SELECT * FROM scanner_snapshots WHERE ticker = ANY(CAST(:t AS text[]))"),
                            {"t": tickers}).mappings()
        return {(r["ticker"], r["horizon"]): dict(r) for r in rows}


_UPSERT_SNAPSHOT = text("""
    INSERT INTO scanner_snapshots (
        ticker, horizon, price,
        fundamental_z, fundamental_score, fundamental_completeness, fundamental_at,
        technical_z, technical_score, technical_completeness, technical_at,
        sentiment_z, sentiment_score, sentiment_completeness, sentiment_at,
        composite, conviction, agreement, data_completeness,
        estimated_at, verified_at, consecutive_failures, last_error, updated_at)
    VALUES (
        :ticker, :horizon, :price,
        :fundamental_z, :fundamental_score, :fundamental_completeness, :fundamental_at,
        :technical_z, :technical_score, :technical_completeness, :technical_at,
        :sentiment_z, :sentiment_score, :sentiment_completeness, :sentiment_at,
        :composite, :conviction, :agreement, :data_completeness,
        :estimated_at, :verified_at, 0, NULL, now())
    ON CONFLICT (ticker, horizon) DO UPDATE SET
        price = EXCLUDED.price,
        fundamental_z = EXCLUDED.fundamental_z, fundamental_score = EXCLUDED.fundamental_score,
        fundamental_completeness = EXCLUDED.fundamental_completeness, fundamental_at = EXCLUDED.fundamental_at,
        technical_z = EXCLUDED.technical_z, technical_score = EXCLUDED.technical_score,
        technical_completeness = EXCLUDED.technical_completeness, technical_at = EXCLUDED.technical_at,
        sentiment_z = EXCLUDED.sentiment_z, sentiment_score = EXCLUDED.sentiment_score,
        sentiment_completeness = EXCLUDED.sentiment_completeness, sentiment_at = EXCLUDED.sentiment_at,
        composite = EXCLUDED.composite, conviction = EXCLUDED.conviction,
        agreement = EXCLUDED.agreement, data_completeness = EXCLUDED.data_completeness,
        estimated_at = EXCLUDED.estimated_at,
        verified_at = COALESCE(EXCLUDED.verified_at, scanner_snapshots.verified_at),
        consecutive_failures = 0, last_error = NULL, updated_at = now()
""")


def _snapshot_row(ticker: str, horizon: str, price: float | None, f, t, s, res, completeness,
                  now: datetime, verified: bool) -> dict:
    def cols(prefix: str, r: Reading | None) -> dict:
        return {f"{prefix}_z": r.z if r else None, f"{prefix}_score": r.score if r else None,
                f"{prefix}_completeness": r.completeness if r else None, f"{prefix}_at": r.at if r else None}
    return {
        "ticker": ticker, "horizon": horizon, "price": price,
        **cols("fundamental", f), **cols("technical", t), **cols("sentiment", s),
        "composite": res.composite_score, "conviction": res.conviction, "agreement": res.agreement,
        "data_completeness": completeness, "estimated_at": now, "verified_at": now if verified else None,
    }


def _record_failures(tickers: list[str], error: str) -> None:
    if not tickers:
        return
    with engine().begin() as conn:
        conn.execute(text("""
            UPDATE scanner_snapshots SET consecutive_failures = consecutive_failures + 1,
                   last_error = :e, updated_at = now()
             WHERE ticker = ANY(CAST(:t AS text[]))
        """), {"t": tickers, "e": error})


# ── Queues ────────────────────────────────────────────────────────────────

def _best_estimate(t: str, tech: dict, fund: dict, sent: dict) -> float:
    best = 0.0
    for h in HORIZONS:
        tr = tech.get((t, h))
        if tr is None:
            continue
        res, _ = _pool(h, fund.get((t, h)), tr, sent.get((t, h)))
        best = max(best, res.composite_score)
    return best


def _fundamental_queue(tickers, raw, est, board, now) -> list[str]:
    priority, routine = [], []
    for t in tickers:
        data = raw.get(t)
        age = now - inputs.fetched_at_utc(data) if data else None
        near = t in board or est.get(t, 0.0) >= CANDIDATE_FLOOR
        if age is None or age > FUNDAMENTAL_MAX_AGE:
            (priority if near else routine).append(t)
        elif near and age > FUNDAMENTAL_PRIORITY_AGE:
            priority.append(t)
    by_estimate = lambda t: -est.get(t, 0.0)  # noqa: E731
    return sorted(priority, key=lambda t: (t not in board, by_estimate(t))) + sorted(routine, key=by_estimate)


def _sentiment_queue(tickers, sent, est, board, now) -> list[str]:
    priority, routine = [], []
    for t in tickers:
        r = sent.get((t, "medium_term"))       # all horizons are refreshed together
        age = now - r.at if r else None
        near = t in board or est.get(t, 0.0) >= CANDIDATE_FLOOR
        if near and (age is None or age > SENTIMENT_VERIFY_AGE):
            priority.append(t)
        elif age is None or age > SENTIMENT_ROUTINE_AGE:
            routine.append(t)
    return (sorted(priority, key=lambda t: (t not in board, -est.get(t, 0.0)))
            + sorted(routine, key=lambda t: (sent.get((t, "medium_term")) is not None, -est.get(t, 0.0))))


# ── The run ───────────────────────────────────────────────────────────────

def run_scan(*, force: bool = False, tickers: list[str] | None = None,
             limits: dict[str, int] | None = None) -> dict:
    """
    One pass of the funnel. Safe to call as often as the beat likes: it
    takes a lock, skips when not due for the market phase, and never raises.

    `tickers` and `limits` narrow a run for testing and backfills.
    """
    from app.core.config import get_settings

    if not get_settings().scanner_enabled:
        return {"status": "disabled"}

    token = secrets.token_hex(8)
    if not get_redis_client().set(_LOCK_KEY, token, nx=True, ex=_LOCK_TTL):
        return {"status": "locked"}

    started = time.monotonic()
    now = datetime.now(timezone.utc)
    phase = market_phase(now)
    stats = RunStats()
    run_id: str | None = None
    try:
        if not force and not _due(phase, now):
            return {"status": "not_due", "market_phase": phase}

        universe = active_universe()
        if tickers:
            wanted = {t.upper() for t in tickers}
            universe = [u for u in universe if u["ticker"] in wanted]
        meta = {u["ticker"]: u for u in universe}

        budget = scan_budget.RunBudget(phase, deadline=started + RUN_DEADLINE_SECONDS, limits=limits)
        stats.universe_size, stats.budget_units = len(meta), budget.capacity_units
        run_id = _start_run(phase, stats)

        alerts = _scan(run_id, list(meta), meta, now, budget, stats)
        stats.units_spent = budget.units_spent
        stats.notes.extend(budget.stop_reasons)
        _finish_run(run_id, "completed", stats)
        result = {"status": "completed", "run_id": run_id, "market_phase": phase, "alerts": alerts,
                  "elapsed_seconds": round(time.monotonic() - started, 1), **stats.as_dict()}
        logger.info("Market scan complete", extra=result)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Market scan failed", extra={"error": str(exc)}, exc_info=True)
        stats.notes.append(f"failed: {type(exc).__name__}: {exc}")
        if run_id:
            try:
                _finish_run(run_id, "failed", stats)
            except Exception:  # noqa: BLE001
                pass
        return {"status": "failed", "run_id": run_id, "error": str(exc)}
    finally:
        _release_lock(token)


def _scan(run_id: str, symbols: list[str], meta: dict, now: datetime,
          budget: scan_budget.RunBudget, stats: RunStats) -> int:
    from app.analysis.fundamental import run_fundamental_analysis
    from app.analysis.sector_peers import compare_to_sector
    from app.analysis.technical import run_technical_analysis

    today = date.today()                 # the analysis page's own notion of today (see ensemble)
    snaps = _load_snapshots(symbols)
    board = {t for _, t in leaderboard.active_pairs()}

    # 1 — prices and the technical pillar, for everyone ─────────────────
    max_lookback = max(cfg["lookback_days"] for cfg in _HORIZON_CONFIG.values())
    bars, failed = inputs.fetch_universe_bars(symbols, today - timedelta(days=max_lookback), today)
    stats.refreshed_technical = len(bars)
    if failed:
        stats.errors += len(failed)
        _record_failures(failed, "no price bars in the batch download")

    tech: dict[tuple[str, str], Reading] = {}
    prices: dict[str, float] = {}
    for t, df in bars.items():
        prices[t] = float(df["close"].iloc[-1])
        for h, cfg in _HORIZON_CONFIG.items():
            sliced = inputs.slice_lookback(df, cfg["lookback_days"], today)
            if sliced.empty:
                continue
            try:
                tech[(t, h)] = _from_result(run_technical_analysis(t, sliced), now)
            except Exception as exc:  # noqa: BLE001
                stats.errors += 1
                logger.info("Technical pillar failed", extra={"ticker": t, "horizon": h, "error": str(exc)})

    fund_prev = {(t, h): _from_row(snaps.get((t, h)), "fundamental") for t in symbols for h in HORIZONS}
    sent: dict[tuple[str, str], Reading] = {}
    for t in symbols:
        for h in HORIZONS:
            r = _from_row(snaps.get((t, h)), "sentiment")
            if r:
                sent[(t, h)] = r

    # 2 — fundamentals: refresh the stale, recompute everyone ──────────────
    raw = inputs.load_cached_fundamentals(symbols)
    est = {t: _best_estimate(t, tech, {k: v for k, v in fund_prev.items() if v}, sent) for t in symbols}
    for t in _fundamental_queue(symbols, raw, est, board, now):
        if not budget.take("fundamentals"):
            break
        try:
            raw[t] = inputs.refresh_fundamentals(t)
            stats.refreshed_fundamental += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.info("Fundamentals refresh failed", extra={"ticker": t, "error": str(exc)})

    fund: dict[tuple[str, str], Reading] = {}
    for t in symbols:
        data = raw.get(t)
        if data is None:
            # Redis lost the raw data but the stored reading is still in date.
            for h in HORIZONS:
                r = fund_prev.get((t, h))
                if r and now - r.at <= FUNDAMENTAL_MAX_AGE:
                    fund[(t, h)] = r
            continue
        priced = replace(data)
        # Always the latest close. The page gets a live price from its
        # providers; a cached price days old would be further from what the
        # user sees than the close from minutes ago.
        if t in prices:
            priced.current_price = prices[t]
        fetched_at = inputs.fetched_at_utc(data)
        try:
            cmp = compare_to_sector(t, priced.sector, sector_metrics(priced))
            for h in HORIZONS:
                fund[(t, h)] = _from_result(run_fundamental_analysis(t, priced, h, sector_comparison=cmp), fetched_at)
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.info("Fundamental pillar failed", extra={"ticker": t, "error": str(exc)})

    # 3 — sentiment, in priority order ───────────────────────────────────
    est = {t: _best_estimate(t, tech, fund, sent) for t in symbols}
    for t in _sentiment_queue(symbols, sent, est, board, now):
        if not budget.take("sentiment"):
            break
        name = (raw[t].company_name if t in raw and raw[t].company_name else meta[t]["company_name"])
        try:
            scores = inputs.refresh_sentiment(t, name)
            at = datetime.now(timezone.utc)
            for h, s in scores.items():
                sent[(t, h)] = _from_result(s, at)
            stats.refreshed_sentiment += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.info("Sentiment refresh failed", extra={"ticker": t, "error": str(exc)})

    # 4 — pool, verify, persist ──────────────────────────────────────────
    rows: list[dict] = []
    verified: dict[str, list[dict]] = {h: [] for h in HORIZONS}
    for t in symbols:
        for h in HORIZONS:
            tr = tech.get((t, h))
            if tr is None:
                continue                  # no price this run: leave the stored snapshot untouched
            f, s = fund.get((t, h)), sent.get((t, h))
            res, completeness = _pool(h, f, tr, s)
            is_verified = (f is not None and now - f.at <= FUNDAMENTAL_MAX_AGE
                           and s is not None and now - s.at <= SENTIMENT_VERIFY_AGE)
            rows.append(_snapshot_row(t, h, prices.get(t), f, tr, s, res, completeness, now, is_verified))
            stats.estimated += 1
            if is_verified:
                stats.verified += 1
                verified[h].append({
                    "ticker": t, "company_name": meta[t]["company_name"], "sector": meta[t]["gics_sector"],
                    "price": prices.get(t), "composite": res.composite_score, "conviction": res.conviction,
                    "agreement": res.agreement, "data_completeness": completeness,
                    "driver_pillar": _driver(res, {"fundamental": f, "technical": tr, "sentiment": s}),
                })

    with engine().begin() as conn:
        for i in range(0, len(rows), 500):
            conn.execute(_UPSERT_SNAPSHOT, rows[i:i + 500])

    # 5 — board, alerts, caches ──────────────────────────────────────────
    # Verified before THIS run: only these can cross the line and alert.
    previously_verified = {(h, t) for (t, h), row in snaps.items() if row.get("verified_at")}
    outcome = leaderboard.apply_run(run_id, verified, now, previously_verified=previously_verified)
    stats.entries, stats.exits = outcome.entries, outcome.exits

    near_board = sorted({v["ticker"] for vs in verified.values() for v in vs
                         if v["composite"] >= leaderboard.CANDIDATE_DISPLAY_FLOOR})
    hot = list(dict.fromkeys(outcome.board_tickers + near_board))[:PRIME_CACHE_LIMIT]
    inputs.prime_analysis_cache(hot, bars, today)
    leaderboard.refresh_cache()

    if outcome.alert_ids:
        from app.workers.scanner_tasks import deliver_market_alert
        for alert_id in outcome.alert_ids:
            deliver_market_alert.delay(alert_id)
    return len(outcome.alert_ids)
