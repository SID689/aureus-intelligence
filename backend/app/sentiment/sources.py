"""
app/sentiment/sources.py
--------------------------
Ingestion for the Sentiment pillar: news wires and retail/social chatter,
normalised into one `SentimentDocument` shape so the engine never has to
care where a document came from.

=====================================================================
WHICH OF THE BRIEF'S SOURCES ARE ACTUALLY FREE
=====================================================================
Probed live on 2026-08-14 from this machine:

    Finnhub /company-news    OK      248 articles for AAPL over 14 days
    Yahoo Finance (yfinance) OK      ~10 curated items per ticker
    StockTwits streams API   OK      30 messages, ~1/3 self-labelled
    SEC EDGAR                OK      see edgar_mdna.py

    Finnhub /news-sentiment  PAID    "You don't have access to this resource"
    StockNewsAPI             PAID    no free tier at all
    Twitter/X API            PAID    $100/mo floor for any read access
    Reddit JSON              BLOCKED 403 on www, old, and /search.json —
                                     Reddit now requires a registered OAuth
                                     app for programmatic reads

So three of the brief's named sources cannot be wired up without either a
paid plan or a registered app. Rather than ship dead code that silently
returns nothing, each is represented by an explicit disabled entry in
UNAVAILABLE_SOURCES, which the API surfaces so the UI can say *why* a
stream is missing instead of just showing a gap. Adding any of them later
means implementing one fetch function and deleting one entry.

=====================================================================
PUBLISHER AUTHORITY
=====================================================================
Not every headline deserves the same vote. A Reuters wire story and an
SEO content farm rehashing it are not equal evidence, but they arrive
through the same API looking identical. _AUTHORITY assigns a multiplier
by publisher so the wires dominate and aggregators contribute without
being able to swing the score on their own.

Unknown publishers get 0.55 — below every named outlet, because the
long tail of financial content is overwhelmingly low-quality, but not
zero, because genuine regional and trade press lands there too.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import get_settings

logger = logging.getLogger("aureus.sentiment.sources")

FINNHUB_BASE = "https://finnhub.io/api/v1"
STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"

_UA = "Aureus Intelligence sentiment/1.0"


@dataclass
class SentimentDocument:
    """One scoreable item, from any source."""
    doc_id: str
    channel: str            # "news" | "social"
    source: str             # publisher / platform name
    headline: str
    body: str
    url: str
    published_at: datetime
    authority: float = 1.0  # publisher-quality multiplier
    engagement: float = 1.0 # social reach multiplier; 1.0 for news
    # StockTwits lets posters self-label Bullish/Bearish. When present
    # that is a stated intent rather than an inference, so the engine
    # trusts it over the text model.
    declared_sentiment: float | None = None
    # Filled in by the engine after scoring.
    polarity: float = 0.0
    model: str = ""
    scoped: bool = True
    evidence: list[str] = field(default_factory=list)


# ── Sources the brief asks for that are not free ──────────────────────
UNAVAILABLE_SOURCES: list[dict[str, str]] = [
    {
        "name": "StockNewsAPI",
        "channel": "news",
        "reason": "No free tier — paid plans start at $19.99/mo.",
        "to_enable": "Subscribe, then set STOCKNEWSAPI_KEY and add a fetch function here.",
    },
    {
        "name": "Twitter / X",
        "channel": "social",
        "reason": "API read access was withdrawn from the free tier; Basic is $100/mo.",
        "to_enable": "Subscribe to an X API tier, then set X_BEARER_TOKEN.",
    },
    {
        "name": "Reddit (r/wallstreetbets, r/stocks)",
        "channel": "social",
        "reason": "Public JSON endpoints now return 403 to unauthenticated clients.",
        "to_enable": (
            "Register a free script app at reddit.com/prefs/apps, then set "
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET. Reddit's free OAuth tier "
            "allows 100 requests/min, which is ample here."
        ),
    },
]


# ── Publisher authority ───────────────────────────────────────────────
_AUTHORITY: dict[str, float] = {
    # Primary wires — first-hand reporting, correction policies, legal exposure
    "reuters": 1.00, "bloomberg": 1.00, "dow jones": 1.00, "associated press": 0.98,
    "financial times": 0.97, "wall street journal": 0.97, "wsj": 0.97,
    # Major financial press
    "cnbc": 0.85, "marketwatch": 0.85, "barron's": 0.90, "barrons": 0.90,
    "the economist": 0.88, "forbes": 0.72, "fortune": 0.75, "business insider": 0.68,
    "yahoo finance": 0.75, "investor's business daily": 0.82, "axios": 0.80,
    "the information": 0.88, "quartz": 0.70, "fortune media": 0.75,
    # Sector / trade press — narrow but often well-sourced
    "techcrunch": 0.70, "the verge": 0.65, "ars technica": 0.72, "stat news": 0.85,
    "endpoints news": 0.82, "fiercebiotech": 0.75, "electrek": 0.60,
    # Aggregators and retail-facing commentary
    "seeking alpha": 0.55, "benzinga": 0.55, "zacks": 0.60, "the motley fool": 0.50,
    "motley fool": 0.50, "investorplace": 0.45, "simply wall st": 0.50,
    "gurufocus": 0.50, "insider monkey": 0.42, "247wallst": 0.42,
    "thestreet": 0.58, "investing.com": 0.55, "tipranks": 0.55,
    # Primary source — a company's own filing is fact, not commentary
    "sec": 1.00, "sec edgar": 1.00,
}
_DEFAULT_AUTHORITY = 0.55


def _squash(s: str) -> str:
    """Lowercase, letters and digits only — 'Seeking Alpha' -> 'seekingalpha'."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


# Precomputed squashed index. Feeds are inconsistent about spacing and
# punctuation for the same outlet — Finnhub returns "SeekingAlpha" while
# the table is keyed "seeking alpha", and a plain substring test misses
# that, silently demoting a known publisher to the unknown default.
_AUTHORITY_SQUASHED: dict[str, float] = {_squash(k): v for k, v in _AUTHORITY.items()}
# Bare aliases that appear as a publisher name on their own.
_AUTHORITY_SQUASHED.setdefault("yahoo", _AUTHORITY["yahoo finance"])
_AUTHORITY_SQUASHED.setdefault("ft", _AUTHORITY["financial times"])
_AUTHORITY_SQUASHED.setdefault("ap", _AUTHORITY["associated press"])


def publisher_authority(source: str) -> float:
    """
    Authority multiplier for a publisher name.

    Matched on a squashed form so spacing and punctuation variants of the
    same outlet resolve to the same weight. Longest known key wins, so
    "Yahoo Finance" is not matched by the shorter "yahoo" entry first.
    """
    if not source:
        return _DEFAULT_AUTHORITY
    sq = _squash(source)
    if not sq:
        return _DEFAULT_AUTHORITY
    if sq in _AUTHORITY_SQUASHED:
        return _AUTHORITY_SQUASHED[sq]
    for known in sorted(_AUTHORITY_SQUASHED, key=len, reverse=True):
        if known in sq:
            return _AUTHORITY_SQUASHED[known]
    return _DEFAULT_AUTHORITY


def _parse_dt(value) -> datetime:
    """Best-effort timestamp parse; unknown times are treated as now."""
    now = datetime.now(tz=timezone.utc)
    if value is None:
        return now
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return now
    if isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return now
    return now


# ── Finnhub company news ──────────────────────────────────────────────

def fetch_finnhub_news(ticker: str, lookback_days: int) -> list[SentimentDocument]:
    """
    Per-ticker news from Finnhub. This is the highest-volume free source
    and the backbone of the news sub-score.

    Note this is /company-news, NOT /news-sentiment. The latter returns
    ready-made sentiment but is gated behind a paid plan on this account,
    which is why the scoring happens locally in nlp.py.
    """
    s = get_settings()
    if not s.finnhub_configured:
        return []
    today = datetime.now(tz=timezone.utc).date()
    params = {
        "symbol": ticker,
        "from": (today - timedelta(days=lookback_days)).isoformat(),
        "to": today.isoformat(),
    }
    try:
        r = httpx.get(f"{FINNHUB_BASE}/company-news", params=params,
                      headers={"X-Finnhub-Token": s.finnhub_api_key, "User-Agent": _UA},
                      timeout=15.0)
        if r.status_code != 200:
            logger.warning("Finnhub company-news non-200",
                           extra={"ticker": ticker, "status": r.status_code})
            return []
        rows = r.json() or []
    except Exception as exc:
        logger.warning("Finnhub company-news failed",
                       extra={"ticker": ticker, "error": str(exc)})
        return []

    docs: list[SentimentDocument] = []
    for a in rows:
        headline = (a.get("headline") or "").strip()
        if not headline:
            continue
        source = (a.get("source") or "Finnhub").strip()
        docs.append(SentimentDocument(
            doc_id=f"fh:{a.get('id') or a.get('url','')}",
            channel="news",
            source=source,
            headline=headline,
            body=(a.get("summary") or "").strip(),
            url=a.get("url", ""),
            published_at=_parse_dt(a.get("datetime")),
            authority=publisher_authority(source),
        ))
    logger.info("Finnhub news fetched", extra={"ticker": ticker, "count": len(docs)})
    return docs


# ── Yahoo Finance via yfinance ────────────────────────────────────────

def fetch_yahoo_news(ticker: str) -> list[SentimentDocument]:
    """
    Yahoo's curated per-ticker feed. Lower volume than Finnhub but
    differently curated, so it surfaces stories Finnhub misses. Free, no
    key — it rides the yfinance dependency the market-data layer uses.
    """
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker).news or []
    except Exception as exc:
        logger.warning("Yahoo news failed", extra={"ticker": ticker, "error": str(exc)})
        return []

    docs: list[SentimentDocument] = []
    for item in raw:
        # yfinance moved the payload under "content" in recent versions;
        # accept both shapes so a dependency bump doesn't silently zero
        # this source out.
        c = item.get("content") or item
        headline = (c.get("title") or "").strip()
        if not headline:
            continue
        provider = ((c.get("provider") or {}).get("displayName")
                    if isinstance(c.get("provider"), dict) else c.get("publisher")) or "Yahoo Finance"
        docs.append(SentimentDocument(
            doc_id=f"yf:{c.get('id') or item.get('id') or headline[:40]}",
            channel="news",
            source=str(provider),
            headline=headline,
            body=(c.get("description") or c.get("summary") or "").strip(),
            url=((c.get("canonicalUrl") or {}).get("url", "")
                 if isinstance(c.get("canonicalUrl"), dict) else c.get("link", "")),
            published_at=_parse_dt(c.get("pubDate") or c.get("providerPublishTime")),
            authority=publisher_authority(str(provider)),
        ))
    logger.info("Yahoo news fetched", extra={"ticker": ticker, "count": len(docs)})
    return docs


# ── StockTwits ────────────────────────────────────────────────────────

_CASHTAG_NOISE = re.compile(r"\$[A-Z.]{1,6}")


def fetch_stocktwits(ticker: str) -> list[SentimentDocument]:
    """
    Retail chatter. Two things make this worth ingesting despite the
    noise: volume responds to events much faster than news does, and
    roughly a third of posters attach an explicit Bullish/Bearish label,
    which is a stated position rather than an inferred one.

    Engagement weighting uses follower count, heavily compressed by a log
    so a 100k-follower account counts for a few ordinary posters rather
    than a few hundred — this is the main defence against a single loud
    account moving a ticker's social score.
    """
    import math
    try:
        r = httpx.get(f"{STOCKTWITS_BASE}/streams/symbol/{ticker}.json",
                      headers={"User-Agent": _UA}, timeout=12.0)
        if r.status_code != 200:
            logger.info("StockTwits unavailable",
                        extra={"ticker": ticker, "status": r.status_code})
            return []
        messages = (r.json() or {}).get("messages", []) or []
    except Exception as exc:
        logger.info("StockTwits fetch failed", extra={"ticker": ticker, "error": str(exc)})
        return []

    docs: list[SentimentDocument] = []
    for m in messages:
        body = (m.get("body") or "").strip()
        if not body:
            continue
        entities = m.get("entities") or {}
        sentiment = entities.get("sentiment") or {}
        declared = None
        if isinstance(sentiment, dict):
            basic = str(sentiment.get("basic", "")).lower()
            if basic == "bullish":
                declared = 1.0
            elif basic == "bearish":
                declared = -1.0

        user = m.get("user") or {}
        followers = float(user.get("followers", 0) or 0)
        engagement = min(3.0, 1.0 + math.log10(1.0 + followers) / 2.0)

        docs.append(SentimentDocument(
            doc_id=f"st:{m.get('id')}",
            channel="social",
            source="StockTwits",
            headline=_CASHTAG_NOISE.sub("", body)[:200].strip(),
            body=body,
            url=f"https://stocktwits.com/message/{m.get('id')}",
            published_at=_parse_dt(m.get("created_at")),
            authority=0.45,   # retail chatter is real signal but weak evidence
            engagement=engagement,
            declared_sentiment=declared,
        ))
    logger.info("StockTwits fetched", extra={"ticker": ticker, "count": len(docs)})
    return docs


# ── Aggregation ───────────────────────────────────────────────────────

def _dedupe(docs: list[SentimentDocument]) -> list[SentimentDocument]:
    """
    Collapse the same story arriving through two feeds.

    Keyed on a normalised headline rather than URL, because syndication
    rewrites URLs but rarely the headline. When a duplicate is found the
    higher-authority copy wins, so a Reuters original beats an aggregator
    reprint of it.
    """
    best: dict[str, SentimentDocument] = {}
    for d in docs:
        key = re.sub(r"[^a-z0-9 ]", "", d.headline.lower())[:80]
        if not key:
            continue
        prev = best.get(key)
        if prev is None or d.authority > prev.authority:
            best[key] = d
    return list(best.values())


def gather_documents(ticker: str, lookback_days: int | None = None) -> list[SentimentDocument]:
    """
    Every free source, deduplicated, newest first.

    Each source is independently guarded — one provider being down
    degrades the pillar's completeness rather than failing the request.
    """
    lookback = lookback_days or get_settings().sentiment_news_lookback_days
    docs: list[SentimentDocument] = []
    for fetch in (
        lambda: fetch_finnhub_news(ticker, lookback),
        lambda: fetch_yahoo_news(ticker),
        lambda: fetch_stocktwits(ticker),
    ):
        try:
            docs.extend(fetch())
        except Exception as exc:
            logger.warning("Sentiment source raised", extra={"ticker": ticker, "error": str(exc)})

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=lookback)
    docs = [d for d in docs if d.published_at >= cutoff]
    docs = _dedupe(docs)
    docs.sort(key=lambda d: d.published_at, reverse=True)
    return docs
