"""
Measure the two quantities the aggregator needs: how much each sub-signal
actually MOVES (sigma), and how much the sub-signals REPEAT each other
(rho).

Both are empirical questions, and both were previously assumed rather
than measured — the old aggregator implicitly assumed rho = 1.0 (every
signal perfectly redundant), which is the mathematical reason a
six-signal pillar had the dispersion of a single signal.

Writes JSON to scripts/calibration_data.json for calibration.py to read.

Run:  docker compose exec -T backend python -m scripts.calibrate_signals
"""
import json
import pathlib
import statistics
import sys
import warnings
from datetime import date, timedelta

warnings.filterwarnings("ignore")

from app.analysis.fundamental import run_fundamental_analysis      # noqa: E402
from app.analysis.sector_peers import compare_to_sector            # noqa: E402
from app.analysis.sentiment import run_sentiment_analysis          # noqa: E402
from app.analysis.technical import run_technical_analysis          # noqa: E402
from app.ingestion.fundamentals import FundamentalDataService      # noqa: E402
from app.ingestion.market_data import MarketDataService            # noqa: E402

# Wide enough to span sectors, market caps and momentum regimes. A
# calibration universe drawn only from megacap tech would report that
# every signal is bullish and barely varies.
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "INTC", "MU", "ORCL",
    "JPM", "BAC", "GS", "V", "AXP",
    "JNJ", "PFE", "MRK", "LLY", "UNH",
    "XOM", "CVX", "COP",
    "CAT", "DE", "HON", "GE",
    "WMT", "COST", "TGT", "NKE", "SBUX",
    "T", "VZ", "CMCSA",
    "F", "GM", "DAL",
    "TSLA", "COIN", "PLTR", "SHOP",
]


def main() -> int:
    market_svc, fund_svc = MarketDataService(), FundamentalDataService()
    end = date.today()
    start = end - timedelta(days=365)

    # label -> list of scores across the universe
    tech_sub: dict[str, list[float]] = {}
    fund_sub: dict[str, list[float]] = {}
    sent_sub: dict[str, list[float]] = {}
    pillars: dict[str, list[float]] = {"fundamental": [], "technical": [], "sentiment": []}
    # ticker -> {label: score}, so pairwise correlation can be computed
    rows: list[dict[str, float]] = []

    for t in UNIVERSE:
        row: dict[str, float] = {}
        try:
            bars = market_svc.fetch_bars(t, start, end, frequency="1d").bars
            tech = run_technical_analysis(t, bars)
            for s in tech.signal_breakdown:
                lbl = f"tech::{s['label']}"
                tech_sub.setdefault(lbl, []).append(float(s["score"]))
                row[lbl] = float(s["score"])
            pillars["technical"].append(tech.score)
            row["pillar::technical"] = tech.score
        except Exception as exc:  # noqa: BLE001
            print(f"  {t}: technical failed: {exc}", flush=True)

        try:
            fd = fund_svc.fetch_fundamentals(t)
            sc = compare_to_sector(t, fd.sector, {
                "pe_ratio": fd.pe_ratio, "price_to_sales": fd.price_to_sales,
                "pb_ratio": fd.pb_ratio,
                "gross_margin": (fd.gross_margin * 100) if fd.gross_margin is not None else None,
                "operating_margin": (fd.operating_margin * 100) if fd.operating_margin is not None else None,
                "return_on_equity": (fd.return_on_equity * 100) if fd.return_on_equity is not None else None,
                "roic": (fd.roic * 100) if fd.roic is not None else None,
                "debt_to_equity": fd.debt_to_equity,
            })
            fund = run_fundamental_analysis(t, fd, "medium_term", sector_comparison=sc)
            for s in fund.signal_breakdown:
                lbl = f"fund::{s['label']}"
                fund_sub.setdefault(lbl, []).append(float(s["score"]))
                row[lbl] = float(s["score"])
            pillars["fundamental"].append(fund.score)
            row["pillar::fundamental"] = fund.score
        except Exception as exc:  # noqa: BLE001
            print(f"  {t}: fundamental failed: {exc}", flush=True)

        try:
            sent = run_sentiment_analysis(t)
            for s in sent.signal_breakdown:
                lbl = f"sent::{s['label']}"
                sent_sub.setdefault(lbl, []).append(float(s["score"]))
                row[lbl] = float(s["score"])
            pillars["sentiment"].append(sent.score)
            row["pillar::sentiment"] = sent.score
        except Exception as exc:  # noqa: BLE001
            print(f"  {t}: sentiment failed: {exc}", flush=True)

        rows.append(row)
        print(f"  {t} done ({len(row)} signals)", flush=True)

    def summarise(d: dict[str, list[float]]) -> dict[str, dict]:
        out = {}
        for lbl, xs in sorted(d.items()):
            if len(xs) < 5:
                continue
            out[lbl] = {
                "n": len(xs),
                "mean": round(statistics.fmean(xs), 2),
                "sd": round(statistics.pstdev(xs), 2),
                "min": round(min(xs), 1),
                "max": round(max(xs), 1),
            }
        return out

    def pairwise_rho(labels: list[str]) -> float | None:
        """Mean pairwise Pearson correlation among a group of signals."""
        cors = []
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                a, b = [], []
                for r in rows:
                    if labels[i] in r and labels[j] in r:
                        a.append(r[labels[i]]); b.append(r[labels[j]])
                if len(a) < 8:
                    continue
                sa, sb = statistics.pstdev(a), statistics.pstdev(b)
                if sa == 0 or sb == 0:
                    continue
                ma, mb = statistics.fmean(a), statistics.fmean(b)
                cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / len(a)
                cors.append(cov / (sa * sb))
        return round(statistics.fmean(cors), 3) if cors else None

    result = {
        "universe_size": len(UNIVERSE),
        "as_of": str(date.today()),
        "technical_signals": summarise(tech_sub),
        "fundamental_signals": summarise(fund_sub),
        "sentiment_signals": summarise(sent_sub),
        "pillars": summarise(pillars),
        "rho_within_technical":   pairwise_rho([l for l in tech_sub if len(tech_sub[l]) >= 8]),
        "rho_within_fundamental": pairwise_rho([l for l in fund_sub if len(fund_sub[l]) >= 8]),
        "rho_within_sentiment":   pairwise_rho([l for l in sent_sub if len(sent_sub[l]) >= 8]),
        "rho_across_pillars":     pairwise_rho(["pillar::fundamental", "pillar::technical", "pillar::sentiment"]),
    }

    out = pathlib.Path(__file__).parent / "calibration_data.json"
    out.write_text(json.dumps(result, indent=2))

    print("\n" + "=" * 74)
    for group in ("technical_signals", "fundamental_signals", "sentiment_signals", "pillars"):
        print(f"\n{group}")
        for lbl, st in result[group].items():
            print(f"  {lbl:42s} n={st['n']:3d} mean={st['mean']:6.2f} sd={st['sd']:6.2f} "
                  f"[{st['min']:.0f}–{st['max']:.0f}]")
    print("\nmean pairwise correlation")
    for k in ("rho_within_technical", "rho_within_fundamental", "rho_within_sentiment", "rho_across_pillars"):
        print(f"  {k:26s} {result[k]}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
