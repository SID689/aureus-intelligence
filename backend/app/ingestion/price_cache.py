"""
app/ingestion/price_cache.py
----------------------------
One last price per ticker, shared by everyone who asks for it.

=====================================================================
WHY
=====================================================================
`MarketDataService.fetch_latest_price` goes to a provider every time it
is called, and nothing above it remembers the answer. Re-pricing a
six-position portfolio is six calls; two users holding AAPL each pay for
their own quote of the same number; a room of thirty people opening the
app at once is a hundred and eighty calls against a free tier that
allows sixty a minute.

The quote is identical for all of them. Caching it by ticker turns that
hundred and eighty into six, which is the difference between serving a
burst of visitors and spending the first minute on rate-limit errors.

=====================================================================
TTL
=====================================================================
Sixty seconds. Long enough to collapse a burst, short enough that a
position's value tracks the market on any timescale a person watching a
portfolio page cares about. Raise price_cache_seconds where provider
quota is the binding constraint and a slightly older quote is not.

Failures are cached too, briefly and separately. A ticker no provider
can price does not become cheaper to ask about by being asked thirty
more times, and the negative entry is what stops one bad symbol in a
portfolio from re-running the whole fallback chain on every refresh.
"""

import logging

from app.core.config import get_settings

logger = logging.getLogger("aureus.ingestion.price_cache")

_MISS_TTL = 30          # how long a "nobody could price this" answer sticks
_KEY = "price:{}"
_MISS_KEY = "price_miss:{}"


def _redis():
    from app.core.redis_client import get_redis_client
    return get_redis_client()


def get_prices(tickers: list[str], service=None) -> dict[str, float]:
    """
    Last price for each ticker, from cache where possible.

    Tickers that cannot be priced are simply absent from the result. The
    caller decides what that means: the portfolio re-pricing path keeps
    the previous value rather than writing a zero, because a holding
    worth an unknown amount is not a holding worth nothing.
    """
    wanted = [t.upper().strip() for t in tickers if t and t.strip()]
    if not wanted:
        return {}

    settings = get_settings()
    out: dict[str, float] = {}
    missing: list[str] = []

    try:
        redis = _redis()
        cached = redis.mget([_KEY.format(t) for t in wanted])
        misses = redis.mget([_MISS_KEY.format(t) for t in wanted])
    except Exception as exc:
        logger.warning("Price cache unavailable, pricing every ticker live",
                       extra={"error": str(exc)})
        cached = [None] * len(wanted)
        misses = [None] * len(wanted)

    for ticker, hit, miss in zip(wanted, cached, misses):
        if hit is not None:
            try:
                out[ticker] = float(hit)
                continue
            except (TypeError, ValueError):
                pass
        if miss is None:
            missing.append(ticker)

    if not missing:
        return out

    if service is None:
        from app.ingestion.market_data import MarketDataService
        service = MarketDataService()

    for ticker in missing:
        try:
            price = float(service.fetch_latest_price(ticker))
        except Exception as exc:                                  # noqa: BLE001
            logger.info("No price available", extra={"ticker": ticker, "error": str(exc)})
            _remember_miss(ticker)
            continue
        out[ticker] = price
        _remember(ticker, price, settings.price_cache_ttl)

    return out


def _remember(ticker: str, price: float, ttl: int) -> None:
    try:
        _redis().setex(_KEY.format(ticker), ttl, repr(price))
    except Exception:
        pass


def _remember_miss(ticker: str) -> None:
    try:
        _redis().setex(_MISS_KEY.format(ticker), _MISS_TTL, "1")
    except Exception:
        pass
