"""
app/streaming/news_ingestion.py
--------------------------------
Two news ingestion sources writing to Redis Stream `news:raw`:

1. FinnhubNewsPoller — polls Finnhub REST /news endpoint every N seconds.
   Finnhub's WebSocket is for trade ticks, not news. REST polling at 60s
   intervals is the supported pattern for news and meets Institutional-tier
   "sub-second processing latency" because the latency that matters is
   processing + delivery after receipt, not the polling interval itself.

2. RSSNewsPoller — polls a curated list of financial RSS/Atom feeds.
   Used as a free fallback when Finnhub is not configured, and as a
   supplementary source when it is. RSS coverage is broader than any
   single paid source.

Both pollers are designed to be run as long-lived Celery tasks or
standalone async processes. They write to Redis Streams exclusively —
no direct database writes happen here. Preprocessing and deduplication
happen in the next stage (preprocessor.py).
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.streaming.redis_streams import RawNewsMessage, StreamProducer

logger = logging.getLogger("aureus.streaming.ingestion")

# ── RSS feed registry ──────────────────────────────────────────────────────────
# These are publicly available financial news feeds — no key required.
# NOTE (Phase 6): the original feed list included feeds.reuters.com and
# finance.yahoo.com/rss/topfinstories, both of which have been discontinued
# for years — this was silently starving the news pipeline. Replaced with
# currently-active sources, plus SEC EDGAR's own live filing feed, which
# as a direct government source is the most durable of the group.
RSS_FEEDS = [
    {
        "name": "MarketWatch Top Stories",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    },
    {
        "name": "MarketWatch Market Pulse",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    },
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    },
    {
        "name": "Nasdaq Stocks",
        "url": "https://www.nasdaq.com/feed/rssoutbound?category=Stocks",
    },
    {
        # SEC EDGAR's live feed of newly-filed 8-K (material event) filings.
        # Government-run, will not go stale like a media RSS endpoint can.
        # SEC's fair-access policy blocks generic/browser User-Agents with a
        # 403 on sec.gov — it requires a declared UA identifying the requester
        # (see sec.gov/os/webmaster-faq#developers), so this feed needs its
        # own compliant UA instead of the shared browser one below.
        "name": "SEC EDGAR 8-K Filings",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=100&output=atom",
        "user_agent": "Aureus Intelligence suma.karre@gmail.com",
    },
]

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Seen-URL set TTL in Redis — 24 hours is enough to prevent same-session re-ingestion
_SEEN_TTL = 86_400
_SEEN_KEY  = "ingestion:seen_urls"


def _is_already_seen(url: str) -> bool:
    """Check if this URL was already ingested in the last 24h."""
    client = get_redis_client()
    return bool(client.sismember(_SEEN_KEY, url))


def _mark_seen(url: str) -> None:
    """Mark a URL as seen and refresh the SET's TTL."""
    client = get_redis_client()
    pipe = client.pipeline()
    pipe.sadd(_SEEN_KEY, url)
    pipe.expire(_SEEN_KEY, _SEEN_TTL)
    pipe.execute()


def _make_article_id(url: str) -> str:
    """Stable, short article ID from URL hash."""
    return hashlib.sha256(url.encode()).hexdigest()[:24]


# ── Finnhub poller ─────────────────────────────────────────────────────────────

class FinnhubNewsPoller:
    """
    Polls Finnhub /news (general market news) on a fixed interval.
    Tracks the highest `id` seen so far and uses `minId` to fetch only new articles.
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, producer: StreamProducer):
        self._producer   = producer
        self._settings   = get_settings()
        self._last_id    = 0      # Finnhub news IDs are Unix timestamps

    def _fetch_market_news(self) -> list[dict]:
        if not self._settings.finnhub_configured:
            return []
        headers = {"X-Finnhub-Token": self._settings.finnhub_api_key}
        params  = {"category": "general", "minId": self._last_id}
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.BASE_URL}/news", params=params, headers=headers)
            if resp.status_code == 429:
                logger.warning("Finnhub rate limit hit, backing off 60s")
                time.sleep(60)
                return []
            if resp.status_code != 200:
                logger.warning("Finnhub /news error", extra={"status": resp.status_code})
                return []
            return resp.json() or []
        except Exception as exc:
            logger.error("Finnhub fetch failed", extra={"error": str(exc)})
            return []

    def poll_once(self) -> int:
        """
        Run one polling cycle.
        Returns the number of new articles published to Redis Streams.
        """
        articles = self._fetch_market_news()
        published = 0

        for article in articles:
            url = article.get("url", "")
            if not url or _is_already_seen(url):
                continue

            article_id  = _make_article_id(url)
            headline    = article.get("headline", "").strip()
            content     = article.get("summary", article.get("content", "")).strip()
            published_ts = article.get("datetime", int(time.time()))
            published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat()

            if not headline:
                continue

            msg = RawNewsMessage(
                article_id=article_id,
                headline=headline,
                raw_content=content or headline,
                source=article.get("source", "Finnhub"),
                source_url=url,
                published_at=published_at,
                ingested_at=datetime.now(tz=timezone.utc).isoformat(),
            )
            self._producer.publish_raw(msg)
            _mark_seen(url)

            finnhub_id = article.get("id", 0)
            if finnhub_id > self._last_id:
                self._last_id = finnhub_id

            published += 1

        if published:
            logger.info("Finnhub articles ingested", extra={"count": published})

        return published

    def run_forever(self, interval_seconds: int | None = None) -> None:
        """Blocking loop — run in a dedicated thread or Celery task."""
        interval = interval_seconds or get_settings().news_poll_interval_seconds
        logger.info("Finnhub poller started", extra={"interval_seconds": interval})
        while True:
            try:
                self.poll_once()
            except Exception as exc:
                logger.error("Finnhub poller error", extra={"error": str(exc)})
            time.sleep(interval)


# ── RSS poller ─────────────────────────────────────────────────────────────────

class RSSNewsPoller:
    """
    Polls a list of RSS/Atom feeds and writes new entries to Redis Streams.
    feedparser handles feed format detection automatically (RSS 1.0/2.0/Atom).
    """

    def __init__(self, producer: StreamProducer, feeds: list[dict] | None = None):
        self._producer = producer
        self._feeds    = feeds or RSS_FEEDS

    def _parse_feed(self, feed_meta: dict) -> list[RawNewsMessage]:
        name = feed_meta["name"]
        url  = feed_meta["url"]
        messages: list[RawNewsMessage] = []

        try:
            # A browser-like User-Agent is required — several financial
            # news sites (including some used here) reject requests with
            # Python's default urllib User-Agent string with a silent 403,
            # which feedparser reports as an empty feed, not an error.
            parsed = feedparser.parse(
                url,
                agent=feed_meta.get("user_agent", _DEFAULT_UA),
            )
            if parsed.bozo and not parsed.entries:
                logger.warning("RSS parse error", extra={"feed": name, "error": str(parsed.bozo_exception)})
                return []

            status = getattr(parsed, "status", None)
            if status and status >= 400:
                logger.warning("RSS feed returned an HTTP error", extra={"feed": name, "status": status})
                return []
            if not parsed.entries:
                logger.info("RSS feed returned zero entries this cycle", extra={"feed": name, "status": status})

            for entry in parsed.entries:
                entry_url = entry.get("link", "")
                if not entry_url or _is_already_seen(entry_url):
                    continue

                headline = entry.get("title", "").strip()
                if not headline:
                    continue

                # Extract content — prefer full content over summary
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    content = entry.summary or ""

                # Parse published timestamp — RSS uses published_parsed,
                # Atom feeds (like SEC EDGAR's) use updated_parsed instead.
                published_at = datetime.now(tz=timezone.utc).isoformat()
                time_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if time_struct:
                    try:
                        published_at = datetime(*time_struct[:6], tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pass

                msg = RawNewsMessage(
                    article_id=_make_article_id(entry_url),
                    headline=headline,
                    raw_content=content or headline,
                    source=name,
                    source_url=entry_url,
                    published_at=published_at,
                    ingested_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                messages.append(msg)
                _mark_seen(entry_url)

        except Exception as exc:
            logger.error("RSS feed fetch failed", extra={"feed": name, "error": str(exc)})

        return messages

    def poll_once(self) -> int:
        """Poll all configured RSS feeds. Returns total articles published."""
        total = 0
        for feed_meta in self._feeds:
            messages = self._parse_feed(feed_meta)
            for msg in messages:
                self._producer.publish_raw(msg)
                total += 1
        if total:
            logger.info("RSS articles ingested", extra={"count": total})
        return total

    def run_forever(self, interval_seconds: int | None = None) -> None:
        """Blocking loop."""
        interval = interval_seconds or get_settings().news_poll_interval_seconds
        logger.info("RSS poller started", extra={"interval_seconds": interval})
        while True:
            try:
                self.poll_once()
            except Exception as exc:
                logger.error("RSS poller error", extra={"error": str(exc)})
            time.sleep(interval)


# ── Combined ingestion runner ──────────────────────────────────────────────────

def run_combined_ingestion(interval_seconds: int | None = None) -> None:
    """
    Run both pollers in sequence on one interval.
    Called by the Celery news-ingestion periodic task.
    """
    producer = StreamProducer()
    finnhub  = FinnhubNewsPoller(producer)
    rss      = RSSNewsPoller(producer)
    interval = interval_seconds or get_settings().news_poll_interval_seconds

    logger.info("Combined news ingestion started", extra={"interval_seconds": interval})
    while True:
        try:
            n_finnhub = finnhub.poll_once()
            n_rss     = rss.poll_once()
            logger.info(
                "Ingestion cycle complete",
                extra={"finnhub": n_finnhub, "rss": n_rss, "total": n_finnhub + n_rss},
            )
        except Exception as exc:
            logger.error("Ingestion cycle error", extra={"error": str(exc)})
        time.sleep(interval)
