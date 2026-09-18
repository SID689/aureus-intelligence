"""
Capture the demo environment's bundled analysis payloads.

Runs the real ensemble for every showcase ticker and horizon and writes
each result to app/demo/fixtures/. Those files are what makes the first
tap in a presentation instant, and what the endpoint degrades to when a
provider is rate-limited mid-demo.

Run it on a stack with working API keys, then commit the output:

    docker compose exec -T backend python -m scripts.capture_showcase
    docker compose exec -T backend python -m scripts.capture_showcase --tickers AAPL,NVDA
    docker compose exec -T backend python -m scripts.capture_showcase --horizons medium_term

Existing files are overwritten only when the new run succeeds, so a
partial failure leaves the previous good snapshot in place rather than
replacing it with nothing.
"""
import argparse
import sys
import warnings
from dataclasses import asdict
from datetime import datetime, timezone

warnings.filterwarnings("ignore")

from app.analysis.ensemble import run_ensemble_analysis          # noqa: E402
from app.demo.fixtures import save_analysis                       # noqa: E402
from app.demo.showcase import HORIZONS, SHOWCASE_TICKERS          # noqa: E402


def capture(ticker: str, horizon: str) -> tuple[bool, str]:
    try:
        signal = run_ensemble_analysis(ticker=ticker, time_horizon=horizon)
    except Exception as exc:                                       # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"

    payload = asdict(signal)
    payload["generated_at"] = signal.generated_at.isoformat()
    payload["showcase_snapshot"] = True
    payload["snapshot_captured_at"] = datetime.now(tz=timezone.utc).isoformat()
    path = save_analysis(ticker, horizon, payload)
    return True, (f"{signal.signal} {signal.signal_strength} "
                  f"ci={signal.confidence_index:.1f} "
                  f"completeness={signal.overall_data_completeness:.2f} -> {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=",".join(SHOWCASE_TICKERS))
    ap.add_argument("--horizons", default=",".join(HORIZONS))
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    horizons = [h.strip() for h in args.horizons.split(",") if h.strip()]

    failures = 0
    for ticker in tickers:
        for horizon in horizons:
            print(f"{ticker:6s} {horizon:12s} ", end="", flush=True)
            ok, note = capture(ticker, horizon)
            print(note if ok else f"FAILED  {note}")
            failures += 0 if ok else 1

    total = len(tickers) * len(horizons)
    print(f"\n{total - failures}/{total} captured")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
