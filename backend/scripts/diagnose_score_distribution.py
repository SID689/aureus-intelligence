"""
Diagnostic: how are ensemble scores actually distributed?

The complaint is that almost every stock reads HOLD at short and medium
horizons. Before changing any thresholds, measure where the composite
score actually lands and, crucially, WHY — a distribution squashed around
50 has a different fix from thresholds set too wide.

Prints, per horizon: the composite for each ticker, the spread, how many
cross each threshold, and the per-sub-signal spread inside the technical
pillar (the highest-weighted leg at short horizons).

Run:  docker compose exec -T backend python -m scripts.diagnose_score_distribution
"""
import statistics
import sys
import warnings

warnings.filterwarnings("ignore")

from app.analysis.ensemble import run_ensemble_analysis  # noqa: E402

# Deliberately spans regimes so a healthy engine SHOULD disagree across
# them: strong uptrends, broken names, steady megacaps, deep value,
# cyclicals. If these all score the same, the engine is not discriminating.
TICKERS = [
    "NVDA", "AVGO", "PLTR",      # momentum / strong trend
    "AAPL", "MSFT", "JNJ",       # steady megacap
    "INTC", "PFE", "NKE",        # beaten down
    "F", "VZ", "T",              # deep value / high yield
    "TSLA", "COIN",              # high beta
    "XOM", "CAT",                # cyclical
]

HORIZONS = ["short_term", "medium_term", "long_term"]


def main() -> int:
    per_horizon: dict[str, list[tuple[str, float, str, float, float, float]]] = {}

    for horizon in HORIZONS:
        rows = []
        for t in TICKERS:
            try:
                r = run_ensemble_analysis(t, horizon, use_llm_reasoning=False, user_id=None)
                rows.append((t, r.confidence_index, r.signal,
                             r.fundamental_score, r.technical_score, r.sentiment_score))
                print(f"  {horizon:12s} {t:5s} composite={r.confidence_index:6.2f} "
                      f"{r.signal:4s}  F={r.fundamental_score:5.1f} T={r.technical_score:5.1f} "
                      f"S={r.sentiment_score:5.1f}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  {horizon:12s} {t:5s} FAILED: {exc}", flush=True)
        per_horizon[horizon] = rows

    print("\n" + "=" * 78)
    print("DISTRIBUTION SUMMARY")
    print("=" * 78)

    for horizon, rows in per_horizon.items():
        if not rows:
            continue
        comps = [r[1] for r in rows]
        funds = [r[3] for r in rows]
        techs = [r[4] for r in rows]
        sents = [r[5] for r in rows]
        signals = [r[2] for r in rows]

        def spread(xs: list[float]) -> str:
            return (f"min={min(xs):5.1f} max={max(xs):5.1f} "
                    f"range={max(xs) - min(xs):5.1f} sd={statistics.pstdev(xs):5.2f} "
                    f"mean={statistics.fmean(xs):5.1f}")

        print(f"\n{horizon}")
        print(f"  composite   {spread(comps)}")
        print(f"  fundamental {spread(funds)}")
        print(f"  technical   {spread(techs)}")
        print(f"  sentiment   {spread(sents)}")
        print(f"  signals     BUY={signals.count('BUY')} "
              f"HOLD={signals.count('HOLD')} SELL={signals.count('SELL')}  "
              f"({signals.count('HOLD') / len(signals) * 100:.0f}% hold)")

        # How far would the thresholds have to move to split this sample?
        for lo, hi in ((45, 55), (48, 52), (35, 65)):
            n_buy = sum(1 for c in comps if c >= hi)
            n_sell = sum(1 for c in comps if c < lo)
            print(f"    if thresholds were {lo}/{hi}: "
                  f"BUY={n_buy} SELL={n_sell} HOLD={len(comps) - n_buy - n_sell}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
