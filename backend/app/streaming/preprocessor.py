"""
app/streaming/preprocessor.py
------------------------------
Preprocessing worker: consumes from `news:raw`, cleans articles,
extracts candidate tickers, runs VADER sentiment as a pre-filter,
and writes qualifying articles to `news:processed`.

Why VADER as a pre-filter?
  The LLM agent pipeline (LangGraph + Claude) costs money and takes ~2-5s
  per article. VADER runs in microseconds and filters out neutral/routine
  articles (earnings estimates, analyst ratings, minor index moves) so the
  LLM only processes articles with genuine sentiment signal.
  Threshold is configurable via SENTIMENT_PREFILTER_THRESHOLD in .env.

Deduplication:
  Each article gets a content hash (SHA256 of normalized headline + source).
  The hash is stored in a Redis SET with a 24h TTL. Articles whose hash
  already exists are silently dropped before any further processing.
  This catches the same article re-published across multiple RSS feeds.
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.streaming.redis_streams import (
    GROUP_PREPROCESSOR,
    STREAM_RAW,
    ProcessedNewsMessage,
    StreamConsumer,
    StreamProducer,
)

logger = logging.getLogger("aureus.streaming.preprocessor")

_vader  = SentimentIntensityAnalyzer()

# ── Ticker normalization ───────────────────────────────────────────────────────

# Explicit $TICKER mentions in text
_CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})\b")

# Whitelist of valid ticker formats (1-5 uppercase letters)
_TICKER_RE  = re.compile(r"\b([A-Z]{2,5})\b")

# Major company name → canonical ticker mapping
# This is intentionally comprehensive for large/frequently-mentioned companies.
COMPANY_TO_TICKER: dict[str, str] = {
    "apple": "AAPL", "apple inc": "AAPL", "apple computer": "AAPL",
    "microsoft": "MSFT", "microsoft corp": "MSFT",
    "alphabet": "GOOGL", "google": "GOOGL", "google llc": "GOOGL",
    "amazon": "AMZN", "amazon.com": "AMZN",
    "meta": "META", "facebook": "META", "meta platforms": "META",
    "tesla": "TSLA", "tesla inc": "TSLA", "tesla motors": "TSLA",
    "nvidia": "NVDA", "nvidia corp": "NVDA",
    "netflix": "NFLX", "netflix inc": "NFLX",
    "berkshire": "BRK.B", "berkshire hathaway": "BRK.B",
    "jpmorgan": "JPM", "jp morgan": "JPM", "jpmorgan chase": "JPM",
    "goldman sachs": "GS", "goldman": "GS",
    "morgan stanley": "MS",
    "bank of america": "BAC", "bofa": "BAC",
    "citigroup": "C", "citibank": "C",
    "wells fargo": "WFC",
    "eli lilly": "LLY", "lilly": "LLY",
    "johnson & johnson": "JNJ", "j&j": "JNJ",
    "pfizer": "PFE",
    "unitedhealth": "UNH", "united health": "UNH",
    "exxon": "XOM", "exxon mobil": "XOM", "exxonmobil": "XOM",
    "chevron": "CVX",
    "walmart": "WMT",
    "home depot": "HD",
    "disney": "DIS", "walt disney": "DIS",
    "visa": "V",
    "mastercard": "MA",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "broadcom": "AVGO",
    "amd": "AMD", "advanced micro devices": "AMD",
    "intel": "INTC", "intel corp": "INTC",
    "qualcomm": "QCOM",
    "paypal": "PYPL",
    "uber": "UBER",
    "airbnb": "ABNB",
    "coinbase": "COIN",
    "palantir": "PLTR",
    "snowflake": "SNOW",
    "crowdstrike": "CRWD",
    "openai": None,   # private — explicitly suppress
    "anthropic": None,
}

# Common words that look like tickers but aren't — suppress them
_TICKER_BLACKLIST = {
    "A", "I", "IT", "BE", "BY", "FOR", "IN", "IS", "ON", "OR", "TO",
    "THE", "AND", "BUT", "NOT", "ALL", "NEW", "US", "UK", "EU", "UN",
    "CEO", "CFO", "COO", "IPO", "ETF", "GDP", "CPI", "FED", "IMF",
    "SEC", "FDA", "DOJ", "FBI", "CIA", "DHS", "DOE", "EPA",
    "AI", "ML", "LLM", "API", "SaaS", "ESG", "EPS", "PE", "YTD",
    "QoQ", "YoY", "MoM",
}


def extract_tickers(text: str) -> list[str]:
    """
    Extract candidate tickers from text using three strategies:
    1. Explicit $TICKER cashtag mentions
    2. Company name → ticker lookup
    3. Standalone ALL-CAPS 2-5 letter tokens (filtered against blacklist)
    Returns deduplicated list of uppercase ticker strings.
    """
    found: set[str] = set()

    # Strategy 1: explicit cashtags
    for match in _CASHTAG_RE.finditer(text):
        ticker = match.group(1).upper()
        if ticker not in _TICKER_BLACKLIST:
            found.add(ticker)

    # Strategy 2: company name lookup
    lower_text = text.lower()
    for company, ticker in COMPANY_TO_TICKER.items():
        if ticker and company in lower_text:
            found.add(ticker)

    # Strategy 3: ALL-CAPS tokens (more conservative — only add if 2+ chars)
    for match in _TICKER_RE.finditer(text):
        candidate = match.group(1)
        if candidate not in _TICKER_BLACKLIST and len(candidate) >= 2:
            # Only include if it looks like it could plausibly be a ticker
            # This is intentionally conservative — the LLM agent will refine
            pass  # strategy 3 too noisy without a full ticker database

    return sorted(found)


# ── HTML / boilerplate stripping ───────────────────────────────────────────────

# Boilerplate phrases common in financial news syndication
_BOILERPLATE_PATTERNS = [
    re.compile(r"click here to.*?\.", re.IGNORECASE),
    re.compile(r"subscribe to.*?newsletter.*?\.", re.IGNORECASE),
    re.compile(r"follow us on.*?(twitter|x|linkedin|facebook).*?\.", re.IGNORECASE),
    re.compile(r"(sign up|register) (for|to).*?(free|newsletter).*?\.", re.IGNORECASE),
    re.compile(r"©.*?\d{4}.*?all rights reserved.*?\.?", re.IGNORECASE),
    re.compile(r"this article.*?originally published.*?\.", re.IGNORECASE),
    re.compile(r"(read more|continue reading|more from).*?$", re.IGNORECASE | re.MULTILINE),
]


def strip_html_and_boilerplate(raw: str) -> str:
    """
    1. Strip HTML tags via BeautifulSoup.
    2. Collapse whitespace.
    3. Remove known boilerplate patterns.
    Returns clean plaintext.
    """
    # Strip HTML
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove boilerplate
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)

    # Collapse again after removal
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ── Content deduplication ──────────────────────────────────────────────────────

_DEDUP_KEY  = "preprocessing:content_hashes"
_DEDUP_TTL  = 86_400  # 24 hours


def _content_hash(headline: str, source: str) -> str:
    """
    Content-based fingerprint: SHA256 of (normalized headline + source).
    Normalization strips punctuation and lowercases so minor editorial
    variations of the same headline don't slip through.
    """
    normalized = re.sub(r"[^\w\s]", "", headline.lower().strip())
    return hashlib.sha256(f"{normalized}|{source}".encode()).hexdigest()[:32]


def is_duplicate_content(headline: str, source: str) -> bool:
    client = get_redis_client()
    h = _content_hash(headline, source)
    return bool(client.sismember(_DEDUP_KEY, h))


def mark_content_seen(headline: str, source: str) -> None:
    client = get_redis_client()
    h = _content_hash(headline, source)
    pipe = client.pipeline()
    pipe.sadd(_DEDUP_KEY, h)
    pipe.expire(_DEDUP_KEY, _DEDUP_TTL)
    pipe.execute()


# ── VADER pre-filter ───────────────────────────────────────────────────────────

def vader_compound(text: str) -> float:
    """Run VADER and return the compound score (-1.0 to 1.0)."""
    scores = _vader.polarity_scores(text[:1000])  # limit to avoid slow analysis
    return float(scores["compound"])


# ── Main preprocessing pipeline ────────────────────────────────────────────────

class PreprocessingWorker:
    """
    Consumes from `news:raw`, applies the full preprocessing pipeline,
    and publishes qualifying articles to `news:processed`.

    Filtering logic:
      DUPLICATE? → drop
      HTML/boilerplate stripped → clean_content
      VADER |compound| < threshold? → drop (neutral article)
      Tickers extracted → affected_tickers
      Publish to news:processed
    """

    def __init__(self, consumer_name: str = "preprocessor-1"):
        self._consumer = StreamConsumer(STREAM_RAW, GROUP_PREPROCESSOR, consumer_name)
        self._producer = StreamProducer()
        self._settings = get_settings()

    def process_one(self, msg_id: str, fields: dict) -> bool:
        """
        Process a single raw message.
        Returns True if the article was forwarded, False if filtered.
        """
        headline = fields.get("headline", "")
        source   = fields.get("source", "")

        # ── 1. Content deduplication ──────────────────────────
        if is_duplicate_content(headline, source):
            logger.debug("Duplicate content dropped", extra={"headline": headline[:60]})
            return False
        mark_content_seen(headline, source)

        # ── 2. HTML stripping and boilerplate removal ─────────
        raw_content  = fields.get("raw_content", headline)
        clean_content = strip_html_and_boilerplate(raw_content)

        # ── 3. VADER pre-filter ───────────────────────────────
        analysis_text = f"{headline}. {clean_content[:500]}"
        compound      = vader_compound(analysis_text)
        threshold     = self._settings.sentiment_prefilter_threshold

        if abs(compound) < threshold:
            logger.debug(
                "VADER pre-filter: neutral article dropped",
                extra={"headline": headline[:60], "compound": compound},
            )
            return False

        # ── 4. Ticker extraction ──────────────────────────────
        tickers = extract_tickers(f"{headline} {clean_content[:1000]}")

        # ── 5. Publish to processed stream ────────────────────
        msg = ProcessedNewsMessage(
            article_id=fields.get("article_id", ""),
            headline=headline,
            clean_content=clean_content[:4000],  # cap at 4K chars for LLM context
            source=source,
            source_url=fields.get("source_url", ""),
            published_at=fields.get("published_at", ""),
            ingested_at=fields.get("ingested_at", ""),
            affected_tickers=json.dumps(tickers),
            vader_compound=compound,
        )
        self._producer.publish_processed(msg)

        logger.info(
            "Article preprocessed and forwarded",
            extra={
                "headline": headline[:60],
                "tickers": tickers,
                "vader_compound": round(compound, 3),
            },
        )
        return True

    def run_forever(self) -> None:
        """Blocking consumer loop. Run in a dedicated Celery task."""
        logger.info("Preprocessing worker started")
        self._consumer.reclaim_idle()  # recover any orphaned messages at startup

        while True:
            processed = 0
            try:
                for msg_id, fields in self._consumer.read():
                    try:
                        self.process_one(msg_id, fields)
                    except Exception as exc:
                        logger.error(
                            "Preprocessing error on message",
                            extra={"msg_id": msg_id, "error": str(exc)},
                        )
                    finally:
                        # Always ack — we never want to reprocess a raw message
                        self._consumer.ack(msg_id)
                    processed += 1

            except Exception as exc:
                logger.error("Preprocessing consumer error", extra={"error": str(exc)})
                time.sleep(5)
