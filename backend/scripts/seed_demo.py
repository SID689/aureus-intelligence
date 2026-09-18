"""
Prepare a deployment for a presentation.

Idempotent, and safe to run on every boot of a demo host:

    docker compose exec -T backend python -m scripts.seed_demo

What it does, in order:

  1. Warms the analysis cache from the bundled snapshots, so the first
     visitor of the day is answered from memory rather than waiting on a
     cold pipeline run.
  2. Optionally refreshes those snapshots from live providers first
     (--refresh), which is worth doing the morning of the event so the
     figures on screen are current.
  3. Reports what the demo has to show: scanner coverage, catalysts,
     leaderboard entries. A board with nothing on it is the one demo
     failure a seeded account cannot paper over, and it is better to
     learn that now than in front of a room.

  --purge clears demo accounts from a previous event.
"""
import argparse
import sys
import warnings

warnings.filterwarnings("ignore")

from sqlalchemy import create_engine, text                         # noqa: E402

from app.analysis import result_cache                              # noqa: E402
from app.core.config import get_settings                           # noqa: E402
from app.demo.fixtures import load_analysis                        # noqa: E402
from app.demo.showcase import HORIZONS, SHOWCASE_TICKERS           # noqa: E402


def warm_cache() -> tuple[int, int]:
    warmed, missing = 0, 0
    for ticker in SHOWCASE_TICKERS:
        for horizon in HORIZONS:
            if load_analysis(ticker, horizon) is None:
                missing += 1
                print(f"  missing snapshot: {ticker} {horizon}")
                continue
            result_cache.prime(ticker, horizon)
            warmed += 1
    return warmed, missing


def readiness() -> list[tuple[str, int, int]]:
    """(label, count, minimum considered presentable)"""
    checks = [
        ("scanner universe", "SELECT count(*) FROM scanner_universe", 100),
        ("scanner snapshots (verified)",
         "SELECT count(*) FROM scanner_snapshots WHERE verified_at IS NOT NULL", 50),
        ("leaderboard entries", "SELECT count(*) FROM leaderboard_entries", 10),
        ("catalysts (upcoming)",
         "SELECT count(*) FROM catalysts WHERE event_date >= current_date", 5),
        ("news articles", "SELECT count(*) FROM news_articles", 20),
    ]
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    out = []
    try:
        for label, sql, floor in checks:
            # A connection per check. Sharing one means the first failed
            # statement aborts the transaction and every later check
            # reports zero for a reason that has nothing to do with the
            # data — which is exactly how a readiness report misleads.
            try:
                with engine.connect() as conn:
                    count = int(conn.execute(text(sql)).scalar() or 0)
            except Exception as exc:                                # noqa: BLE001
                print(f"  {label}: query failed ({type(exc).__name__})")
                count = -1
            out.append((label, count, floor))
    finally:
        engine.dispose()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-capture the snapshots from live providers first")
    ap.add_argument("--purge", action="store_true",
                    help="delete demo accounts from a previous event")
    args = ap.parse_args()

    settings = get_settings()
    print(f"demo_mode={settings.demo_mode}  demo_tier={settings.demo_tier}  "
          f"cache_ttl={settings.analysis_cache_ttl}s")
    if not settings.demo_mode:
        print("\nDEMO_MODE is off. The snapshots will not be served and "
              "/api/v1/demo/session will 404. Set DEMO_MODE=true in backend/.env.")

    if args.purge:
        from app.demo.provision import purge_demo_users
        print(f"\npurged {purge_demo_users(0)} demo account(s)")

    if args.refresh:
        print("\nre-capturing snapshots from live providers")
        from scripts.capture_showcase import capture
        for ticker in SHOWCASE_TICKERS:
            for horizon in HORIZONS:
                ok, note = capture(ticker, horizon)
                print(f"  {ticker:6s} {horizon:12s} {'' if ok else 'FAILED '}{note}")

    print("\nwarming the analysis cache")
    warmed, missing = warm_cache()
    print(f"  {warmed} warmed, {missing} missing")

    print("\nshowcase data")
    thin = 0
    for label, count, floor in readiness():
        ok = count >= floor
        flag = "" if ok else (" QUERY FAILED" if count < 0 else f"  THIN (want >= {floor})")
        thin += 0 if ok else 1
        print(f"  {label:32s} {max(count, 0):6d}{flag}")

    if thin:
        print("\nSome tables are thin. The scanner fills them in the background; "
              "give it a market session, or run:\n"
              "  docker compose exec -T backend python -c "
              "\"from app.workers.scanner_tasks import scan_market; scan_market()\"")
    print("\nready" if not (missing or thin) else "\nready with gaps noted above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
