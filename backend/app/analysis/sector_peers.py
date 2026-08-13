"""
app/analysis/sector_peers.py
------------------------------
Sector-relative valuation: how a ticker's multiples compare to the median of
its peer group.

=====================================================================
WHY RELATIVE, NOT ABSOLUTE
=====================================================================
An absolute multiple is close to meaningless on its own. A 35x P/E is
expensive for a utility and unremarkable for enterprise software; a 1.2x
price-to-book is cheap for a bank and a red flag for a business whose value
is supposed to be intangible. Scoring valuation against a fixed threshold
therefore systematically rewards low-multiple SECTORS rather than
attractively-priced COMPANIES — it turns the fundamental pillar into a
sector-rotation bet nobody asked for.

Comparing each multiple to its own sector's median removes that bias and
makes the question the one an analyst actually asks: is this cheap
*relative to the things it competes with for capital*?

=====================================================================
WHY MEDIAN, NOT MEAN
=====================================================================
Valuation multiples are severely right-skewed and produce outright garbage
values — a company with near-zero trailing earnings shows a P/E in the
hundreds, and one loss-making peer can drag a sector mean far from anything
representative. The median ignores those tails. Negative and absurd values
are dropped before the median is taken as well, since a negative P/E is not
"cheap", it means there were no earnings.

=====================================================================
COST AND CACHING
=====================================================================
Every metric needed for a peer comes from ONE Finnhub /stock/metric call, so
a ten-peer group costs ten calls — comfortably inside the free tier's 60/min.
Even so, medians are cached in Redis for a week (sector multiples move
slowly) and computed on a BACKGROUND thread, exactly like the thesis polish:
the first request for an uncovered sector returns without relative context
rather than waiting on ten HTTP round-trips, and every later request has it.
"""

import json
import logging
import statistics
import threading
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

logger = logging.getLogger("aureus.analysis.sector_peers")

FINNHUB_BASE = "https://finnhub.io/api/v1"
_CACHE_TTL = 60 * 60 * 24 * 7      # a week; sector multiples drift slowly
_CACHE_PREFIX = "sector_median:"

# Representative, liquid constituents per Finnhub industry label. Deliberately
# large-cap and long-listed: the point is a stable reference for the sector's
# typical multiple, not a complete census. A ticker is excluded from its own
# peer median at query time so a company is never compared against itself.
SECTOR_PEERS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "TXN", "QCOM"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "T", "VZ", "CMCSA", "TMUS", "EA", "OMC"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "GM"],
    "Consumer Defensive": ["WMT", "COST", "PG", "KO", "PEP", "PM", "MDLZ", "CL", "GIS", "KMB"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "AXP", "V", "MA"],
    "Healthcare": ["JNJ", "UNH", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "AMGN", "GILD"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "VLO", "OXY", "HAL"],
    "Industrials": ["CAT", "BA", "GE", "HON", "UNP", "UPS", "RTX", "LMT", "DE", "MMM"],
    "Basic Materials": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "DOW", "DD", "PPG", "NUE"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "WEC"],
    "Real Estate": ["PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL", "DLR", "AVB"],
}

# Finnhub metric key -> the name used throughout the app.
_PEER_METRICS: dict[str, str] = {
    "peTTM": "pe_ratio",
    "psTTM": "price_to_sales",
    "pbAnnual": "pb_ratio",
    "currentEv/freeCashFlowTTM": "ev_to_fcf",
    "grossMarginTTM": "gross_margin",
    "operatingMarginTTM": "operating_margin",
    "roeTTM": "return_on_equity",
    "roiTTM": "roic",
    "totalDebt/totalEquityAnnual": "debt_to_equity",
}

# Values outside these ranges are data errors or not-meaningful, not signal.
# A negative P/E means there were no earnings, which is not "cheap".
_SANE_RANGE: dict[str, tuple[float, float]] = {
    "pe_ratio": (0.5, 300.0),
    "price_to_sales": (0.05, 100.0),
    "pb_ratio": (0.1, 200.0),
    "ev_to_fcf": (1.0, 400.0),
    "gross_margin": (0.0, 100.0),
    "operating_margin": (-50.0, 100.0),
    "return_on_equity": (-200.0, 400.0),
    "roic": (-100.0, 300.0),
    "debt_to_equity": (0.0, 20.0),
}

# Metrics where a HIGHER value is better for the company.
_HIGHER_IS_BETTER = {"gross_margin", "operating_margin", "return_on_equity", "roic"}

# What actually feeds the relative VALUATION score. Listed explicitly rather
# than inferred as "everything not higher-is-better", because debt-to-equity
# would otherwise be swept in — it is a balance-sheet risk measure, not a
# price multiple, and a company being less levered than its sector says
# nothing about whether its shares are cheap. It still appears in the
# per-metric comparison table, just not in this blend.
_VALUATION_METRICS = {"pe_ratio", "price_to_sales", "pb_ratio", "ev_to_fcf"}


@dataclass
class SectorComparison:
    sector: str
    peer_count: int
    medians: dict[str, float] = field(default_factory=dict)
    # metric -> {"value", "median", "premium_pct", "cheaper_than_peers"}
    comparisons: dict[str, dict] = field(default_factory=dict)
    relative_score: float | None = None   # 0-100, valuation vs sector
    stale: bool = False                    # True when medians are still computing

    def to_dict(self) -> dict:
        return {
            "sector": self.sector,
            "peer_count": self.peer_count,
            "medians": self.medians,
            "comparisons": self.comparisons,
            "relative_score": self.relative_score,
            "stale": self.stale,
        }


def _fetch_peer_metrics(ticker: str) -> dict[str, float] | None:
    """One Finnhub call; returns only values inside their sane range."""
    s = get_settings()
    if not s.finnhub_configured:
        return None
    try:
        r = httpx.get(
            f"{FINNHUB_BASE}/stock/metric",
            params={"symbol": ticker, "metric": "all"},
            headers={"X-Finnhub-Token": s.finnhub_api_key},
            timeout=12.0,
        )
        if r.status_code != 200:
            return None
        m = r.json().get("metric") or {}
    except Exception:
        return None

    out: dict[str, float] = {}
    for fh_key, name in _PEER_METRICS.items():
        v = m.get(fh_key)
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v != v:  # NaN
            continue
        lo, hi = _SANE_RANGE.get(name, (float("-inf"), float("inf")))
        if lo <= v <= hi:
            out[name] = v
    return out or None


def _compute_medians(sector: str) -> dict[str, float]:
    peers = SECTOR_PEERS.get(sector, [])
    collected: dict[str, list[float]] = {}
    for p in peers:
        vals = _fetch_peer_metrics(p)
        if not vals:
            continue
        for k, v in vals.items():
            collected.setdefault(k, []).append(v)

    # Require at least three peers before publishing a median — two values
    # produce a "median" that is really just an average of whatever answered.
    return {
        k: round(float(statistics.median(v)), 4)
        for k, v in collected.items()
        if len(v) >= 3
    }


def _cache_get(sector: str) -> dict[str, float] | None:
    try:
        from app.core.redis_client import get_redis_client
        raw = get_redis_client().get(f"{_CACHE_PREFIX}{sector}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_put(sector: str, medians: dict[str, float]) -> None:
    try:
        from app.core.redis_client import get_redis_client
        get_redis_client().setex(f"{_CACHE_PREFIX}{sector}", _CACHE_TTL, json.dumps(medians))
    except Exception:
        pass


_INFLIGHT: set[str] = set()
_INFLIGHT_LOCK = threading.Lock()


def _spawn_median_computation(sector: str) -> None:
    """Compute in the background, once per sector at a time."""
    with _INFLIGHT_LOCK:
        if sector in _INFLIGHT:
            return
        _INFLIGHT.add(sector)

    def _work() -> None:
        try:
            medians = _compute_medians(sector)
            if medians:
                _cache_put(sector, medians)
                logger.info("Sector medians cached",
                            extra={"sector": sector, "metrics": len(medians)})
        except Exception as exc:
            logger.warning("Sector median computation failed",
                           extra={"sector": sector, "error": str(exc)})
        finally:
            with _INFLIGHT_LOCK:
                _INFLIGHT.discard(sector)

    threading.Thread(target=_work, daemon=True, name=f"sector-{sector}").start()


def _relative_score(comparisons: dict[str, dict]) -> float | None:
    """
    Blend the per-metric comparisons into one 0-100 valuation reading.

    A metric trading at its sector median scores 50. Cheaper scores higher,
    richer scores lower, and the response is capped so a single extreme
    multiple (a 300x P/E on depressed earnings) cannot dominate the blend.
    """
    valuation = [c for name, c in comparisons.items() if name in _VALUATION_METRICS]
    if not valuation:
        return None
    scores = []
    for c in valuation:
        prem = c["premium_pct"] / 100.0            # +0.30 = 30% above median
        scores.append(max(0.0, min(100.0, 50.0 - max(-1.0, min(1.0, prem)) * 50.0)))
    return round(sum(scores) / len(scores), 2)


def compare_to_sector(ticker: str, sector: str | None, metrics: dict[str, float | None]) -> SectorComparison | None:
    """
    Compare a ticker's metrics to its sector medians.

    Returns None when the sector is unknown or uncovered. When the medians
    aren't cached yet it kicks off a background computation and returns a
    `stale` result immediately rather than blocking the request.
    """
    if not sector or sector not in SECTOR_PEERS:
        return None

    medians = _cache_get(sector)
    if medians is None:
        _spawn_median_computation(sector)
        return SectorComparison(sector=sector, peer_count=len(SECTOR_PEERS[sector]), stale=True)

    comparisons: dict[str, dict] = {}
    for name, median in medians.items():
        value = metrics.get(name)
        if value is None or median in (0, None):
            continue
        lo, hi = _SANE_RANGE.get(name, (float("-inf"), float("inf")))
        if not (lo <= value <= hi):
            continue
        premium = (value - median) / abs(median) * 100.0
        higher_better = name in _HIGHER_IS_BETTER
        comparisons[name] = {
            "value": round(value, 4),
            "median": median,
            "premium_pct": round(premium, 2),
            # For a valuation multiple "better" means below the median; for a
            # quality metric it means above it.
            "favourable": (premium > 0) if higher_better else (premium < 0),
        }

    if not comparisons:
        return SectorComparison(sector=sector, peer_count=len(SECTOR_PEERS[sector]),
                                medians=medians, stale=False)

    return SectorComparison(
        sector=sector,
        peer_count=len(SECTOR_PEERS[sector]),
        medians=medians,
        comparisons=comparisons,
        relative_score=_relative_score(comparisons),
    )
