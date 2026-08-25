"""
Re-measure signal calibration and write it to the database, on demand.

Thin CLI over app.analysis.calibration_job — the same code the monthly
Celery task runs, so a manual refresh and a scheduled one cannot drift
apart. Use this after editing a scorer (which invalidates that signal's
centre immediately) or to bootstrap a fresh database.

    docker compose exec -T backend python -m scripts.calibrate_signals
    docker compose exec -T backend python -m scripts.calibrate_signals --dry-run
    docker compose exec -T backend python -m scripts.calibrate_signals --tickers AAPL,MSFT,NVDA

--dry-run prints what would be written without touching the table, which
is the right first move after a scorer change: read the numbers, sanity
check them, then commit them.
"""
import argparse
import statistics
import sys
import warnings

warnings.filterwarnings("ignore")

from app.analysis.calibration import calibration_status          # noqa: E402
from app.analysis.calibration_job import UNIVERSE, WINDOW_DAYS, measure, persist  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; do not write")
    ap.add_argument("--tickers", help="comma-separated universe override")
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    args = ap.parse_args()

    universe = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else UNIVERSE

    print(f"before: {calibration_status()}")
    print(f"measuring {len(universe)} tickers over {args.window_days} days…\n", flush=True)

    collected, failures = measure(universe, args.window_days)

    by_group: dict[str, list[tuple[str, list[float]]]] = {}
    for label, (group, scores) in collected.items():
        by_group.setdefault(group, []).append((label, scores))

    for group in sorted(by_group):
        print(f"\n{group}")
        for label, scores in sorted(by_group[group]):
            if len(scores) < 2:
                continue
            print(f"  {label:28s} n={len(scores):3d} "
                  f"mean={statistics.fmean(scores):6.2f} sd={statistics.pstdev(scores):6.2f} "
                  f"[{min(scores):.0f}–{max(scores):.0f}]")

    if failures:
        print(f"\npartial failures: {len(failures)}")
        for f in failures[:8]:
            print(f"  {f}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    result = persist(collected, args.window_days, len(universe), failures)
    print(f"\nwrote {result.rows_written} rows")
    print(f"after:  {calibration_status()}")
    return 0 if result.rows_written else 1


if __name__ == "__main__":
    sys.exit(main())
