"""
app/scanner/budget.py
-----------------------
The scanner's spending limits, all in one place.

Every figure is a ceiling the scanner holds itself to. They are sized
against the free plans this platform runs on, and they leave the larger
share of every quota to the people actually using the site.

  Finnhub      60 calls/min on the free plan, SHARED with every analysis a
               user runs. The scanner takes at most 30/min.
  StockTwits   roughly 200 calls/hour per IP, unauthenticated. The scanner
               takes at most 90/hour.
  Yahoo        prices arrive in batch downloads of 100 tickers, so the
               whole index costs about six requests per sweep.
  SEC EDGAR    10 requests/second fair-access limit; fundamentals refreshes
               run at a few per minute at most.

COST PER OPERATION                       Finnhub   StockTwits
  fundamentals refresh                      2          0       (+ SEC company facts)
  sentiment refresh                         1          1       (+ Yahoo news)
  prices for the entire universe            0          0       (~6 Yahoo batch requests)

PER-RUN CEILINGS        market open (every 15 min)   closed (hourly)
  sentiment                        20                      20
  fundamentals                     12                      20

Worst case is about 2,200 Finnhub calls a day: an average under 2/min
against a 60/min limit, with bursts capped at 30/min. StockTwits peaks at
80/hour while the market is open.
"""

import time

from app.ingestion.rate_limiter import RedisTokenBucket

FINNHUB = RedisTokenBucket("scanner_finnhub", max_calls=30, window_seconds=60)
STOCKTWITS = RedisTokenBucket("scanner_stocktwits", max_calls=90, window_seconds=3600)

PER_RUN_LIMITS: dict[str, dict[str, int]] = {
    "open":   {"sentiment": 20, "fundamentals": 12},
    "closed": {"sentiment": 20, "fundamentals": 20},
}
FINNHUB_COST = {"fundamentals": 2, "sentiment": 1}

_POLL_SECONDS = 2.0
# A window is 60s, so waiting longer than one full window means someone
# else is holding the quota and this run should yield, not queue.
_MAX_WAIT_SECONDS = 65.0


def describe() -> dict:
    return {
        "finnhub_per_minute": FINNHUB.max_calls,
        "stocktwits_per_hour": STOCKTWITS.max_calls,
        "per_run": PER_RUN_LIMITS,
        "finnhub_cost": FINNHUB_COST,
    }


class RunBudget:
    def __init__(self, phase: str, deadline: float, limits: dict[str, int] | None = None) -> None:
        self.limits = dict(PER_RUN_LIMITS.get(phase, PER_RUN_LIMITS["closed"]))
        if limits:
            self.limits.update(limits)
        self.deadline = deadline
        self.used = {k: 0 for k in self.limits}
        self.units_spent = 0
        self.stop_reasons: list[str] = []

    @property
    def capacity_units(self) -> int:
        return sum(self.limits[k] * FINNHUB_COST[k] for k in self.limits)

    def time_left(self) -> float:
        return self.deadline - time.monotonic()

    def _stop(self, reason: str) -> bool:
        if reason not in self.stop_reasons:
            self.stop_reasons.append(reason)
        return False

    def _acquire(self, bucket: RedisTokenBucket, n: int) -> bool:
        for _ in range(n):
            give_up_at = time.monotonic() + min(_MAX_WAIT_SECONDS, max(0.0, self.time_left()))
            while not bucket.allow():
                if time.monotonic() >= give_up_at:
                    return False
                time.sleep(_POLL_SECONDS)
        return True

    def take(self, kind: str) -> bool:
        """Reserve quota for one operation, waiting briefly for the rate window if needed."""
        if self.time_left() <= 0:
            return self._stop("run deadline reached")
        if self.used[kind] >= self.limits[kind]:
            return False
        if kind == "sentiment" and not STOCKTWITS.allow():
            return self._stop("StockTwits hourly ceiling reached")
        if not self._acquire(FINNHUB, FINNHUB_COST[kind]):
            return self._stop("Finnhub per-minute ceiling stayed exhausted")
        self.used[kind] += 1
        self.units_spent += FINNHUB_COST[kind]
        return True
