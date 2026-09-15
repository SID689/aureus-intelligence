"""
app/sentiment/engine.py
-------------------------
Turns raw documents into the three sub-scores the Sentiment pillar
reports: News Sentiment, Social Sentiment Velocity, and SEC Filing Tone.

=====================================================================
NORMALISATION
=====================================================================
Every sub-score is 0-100 with the bands the brief specifies:

      0 - 35   Bearish
     36 - 65   Neutral
     66 - 100  Bullish

Raw polarity is -1..+1 and maps linearly: 50 + polarity*50. A document
set averaging +0.4 lands at 70 (Bullish); -0.4 lands at 30 (Bearish).

=====================================================================
WHY THE AVERAGE IS WEIGHTED THREE WAYS
=====================================================================
A plain mean over articles is the obvious implementation and it is
wrong, in three separate ways this module corrects:

1. RECENCY. A story from six days ago is already in the price. Weight
   decays exponentially with a 48h half-life, so today's news dominates
   without last week's disappearing entirely.

2. AUTHORITY. A Reuters wire and a content-farm rewrite arrive through
   the same API looking identical (see sources.py). Weighting by
   publisher stops volume from substituting for quality — and volume is
   exactly what a low-quality publisher has most of.

3. SATURATION OF COUNT. Twenty articles saying the same thing is not
   twenty independent pieces of evidence; it is one event covered twenty
   times. Confidence therefore grows with sqrt(n), not n.

=====================================================================
SENTIMENT VELOCITY
=====================================================================
The brief asks for a 24h delta against the 7-day rolling average, on the
theory that a sudden shift precedes the price move. Two components:

    polarity velocity   mean(last 24h) - mean(PRIOR period)
    volume velocity     24h rate / prior period's daily rate

Volume matters as much as direction. A ticker whose coverage volume
quadruples overnight is undergoing something, even before the polarity
resolves — and a polarity swing on two documents is noise, which is why
velocity is damped when the recent window is thin.

Both are measured over the combined document set rather than over social
alone, and both report `computed=False` rather than a number when the
sample doesn't span enough time to support the comparison. See
`_velocity` for the measurement that forced that design.

=====================================================================
MANIPULATION RESISTANCE
=====================================================================
Social is the attack surface: it is trivially cheap to post, and coupling
a score to post volume is precisely the mechanism a pump exploits. Three
guards, all deliberate:
  - social is hard-capped at SENTIMENT_MAX_SOCIAL_WEIGHT of the blend;
  - per-poster engagement is log-compressed in sources.py, so one large
    account cannot outvote the crowd;
  - volume velocity is capped, so a 50x spike counts the same as a 4x.
None of this makes the pillar manipulation-proof. It makes manipulation
expensive and bounded, and the UI says so.
"""

import logging
import math
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.sentiment import sources as src
from app.sentiment.edgar_mdna import filing_tone, tone_to_score
from app.sentiment.nlp import available_model, build_aliases, score_document

logger = logging.getLogger("aureus.sentiment.engine")

_RECENCY_HALFLIFE_HOURS = 48.0
_VELOCITY_WINDOW_HOURS = 24.0
# sqrt-saturating confidence: this many effective documents is treated as
# a full-strength sample. Chosen so a typical large-cap (200+ docs/week)
# saturates while a thinly-covered small-cap honestly reports low
# confidence rather than a precise-looking number built on four articles.
_CONFIDENCE_SATURATION = 40.0


@dataclass
class SentimentBreakdown:
    """Everything the pillar and the UI need, with the workings shown."""
    ticker: str
    overall_score: float = 50.0
    overall_label: str = "Neutral"

    news_score: float = 50.0
    news_computed: bool = False
    news_document_count: int = 0
    news_polarity: float = 0.0

    social_score: float = 50.0
    social_computed: bool = False
    social_message_count: int = 0
    social_polarity: float = 0.0
    polarity_velocity: float = 0.0     # 24h mean minus window mean
    volume_velocity: float | None = None  # 24h rate vs prior period; None when unmeasurable
    velocity_label: str = "Steady"

    sec_tone_score: float = 50.0
    sec_tone_computed: bool = False
    sec_tone_label: str = "Unavailable"
    sec_tone_detail: dict = field(default_factory=dict)

    confidence: float = 0.0            # 0-1, how much sample backs this
    model_used: str = "lexicon"
    catalysts: list[dict] = field(default_factory=list)
    source_mix: dict = field(default_factory=dict)
    unavailable_sources: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "overall_score": self.overall_score, "overall_label": self.overall_label,
            "news_score": self.news_score, "news_computed": self.news_computed,
            "news_document_count": self.news_document_count, "news_polarity": self.news_polarity,
            "social_score": self.social_score, "social_computed": self.social_computed,
            "social_message_count": self.social_message_count,
            "social_polarity": self.social_polarity,
            "polarity_velocity": self.polarity_velocity,
            "volume_velocity": self.volume_velocity, "velocity_label": self.velocity_label,
            "sec_tone_score": self.sec_tone_score, "sec_tone_computed": self.sec_tone_computed,
            "sec_tone_label": self.sec_tone_label, "sec_tone_detail": self.sec_tone_detail,
            "confidence": self.confidence, "model_used": self.model_used,
            "catalysts": self.catalysts, "source_mix": self.source_mix,
            "unavailable_sources": self.unavailable_sources, "notes": self.notes,
        }


# ── Normalisation ─────────────────────────────────────────────────────

def polarity_to_score(polarity: float) -> float:
    """-1..+1 -> 0..100."""
    return round(max(0.0, min(100.0, 50.0 + polarity * 50.0)), 2)


def score_label(score: float) -> str:
    """The bands specified in the brief."""
    if score >= 66.0:
        return "Bullish"
    if score <= 35.0:
        return "Bearish"
    return "Neutral"


def _recency_weight(published_at: datetime, now: datetime) -> float:
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / _RECENCY_HALFLIFE_HOURS)


# ── Scoring passes ────────────────────────────────────────────────────

def _score_all(docs: list[src.SentimentDocument], aliases: set[str]) -> None:
    """Score in place. Documents that never name the target are dropped
    by the caller via the `scoped` flag."""
    for d in docs:
        if d.declared_sentiment is not None:
            # A poster who tagged their own message Bullish/Bearish has
            # stated a position. That beats inferring one from slang,
            # emoji and ticker soup, which is what most of these are.
            d.polarity = d.declared_sentiment
            d.model = "declared"
            d.scoped = True
            d.evidence = ["author-declared sentiment"]
            continue
        result = score_document(d.headline, d.body, aliases)
        d.polarity = result["polarity"]
        d.model = result["model"]
        d.scoped = result["scoped"]
        d.evidence = result["evidence"]


def _weighted_polarity(docs: list[src.SentimentDocument], now: datetime) -> tuple[float, float]:
    """Returns (weighted mean polarity, total weight)."""
    num = 0.0
    den = 0.0
    for d in docs:
        w = _recency_weight(d.published_at, now) * d.authority * d.engagement
        num += w * d.polarity
        den += w
    return (num / den if den > 0 else 0.0), den


# A channel must cover at least this many hours before a 24h-vs-window
# comparison means anything. Below it, "the last 24 hours" and "the whole
# window" are the same documents and the delta is structurally zero.
_MIN_SPAN_HOURS_FOR_VELOCITY = 36.0


def _observed_span_hours(docs: list[src.SentimentDocument]) -> float:
    if len(docs) < 2:
        return 0.0
    newest = max(d.published_at for d in docs)
    oldest = min(d.published_at for d in docs)
    return (newest - oldest).total_seconds() / 3600.0


def _velocity(docs: list[src.SentimentDocument], now: datetime,
              window_days: int) -> tuple[float, float | None, str, bool]:
    """
    (polarity velocity, volume velocity or None, label, computed).

    IMPORTANT — why this runs over ALL documents, not just social:

    StockTwits' streams endpoint returns a fixed page of the ~30 most
    recent messages. Measured on this machine, that page spans about
    twelve minutes for a liquid ticker. Every message therefore falls
    inside the 24-hour window, which makes `recent` identical to the full
    set: the polarity delta is exactly 0.0 by construction, and the
    volume ratio pegs at the cap, for every ticker, always. Those were
    not readings — they were artifacts of the endpoint's page size.

    News does span the window (measured: 55-167 hours), so velocity is
    computed over the combined document set where the baseline is real,
    and `computed` is False when even that doesn't span far enough.

    Genuine multi-day SOCIAL velocity needs history the API won't serve
    in one call; `social_history` below accumulates it across runs.
    """
    if len(docs) < 4:
        return 0.0, None, "Insufficient history", False

    span = _observed_span_hours(docs)
    if span < _MIN_SPAN_HOURS_FOR_VELOCITY:
        return 0.0, None, "Baseline establishing", False

    cutoff = now - timedelta(hours=_VELOCITY_WINDOW_HOURS)
    recent = [d for d in docs if d.published_at >= cutoff]
    older = [d for d in docs if d.published_at < cutoff]
    if not recent or not older:
        return 0.0, None, "Baseline establishing", False

    # Compare the last 24h against the PRIOR period, not against a
    # baseline that already contains the last 24h — including recent
    # documents on both sides of the subtraction dilutes exactly the
    # shift the metric exists to detect.
    baseline = statistics.fmean(d.polarity for d in older)
    recent_mean = statistics.fmean(d.polarity for d in recent)
    damping = min(1.0, len(recent) / 8.0)
    pol_velocity = (recent_mean - baseline) * damping

    prior_hours = max(1.0, span - _VELOCITY_WINDOW_HOURS)
    prior_daily_rate = len(older) / (prior_hours / 24.0)
    vol_velocity = min(5.0, len(recent) / prior_daily_rate) if prior_daily_rate > 0 else 1.0

    if vol_velocity >= 2.0 and abs(pol_velocity) >= 0.15:
        label = "Surging bullish" if pol_velocity > 0 else "Surging bearish"
    elif vol_velocity >= 2.0:
        label = "Volume spike, mixed tone"
    elif pol_velocity >= 0.15:
        label = "Improving"
    elif pol_velocity <= -0.15:
        label = "Deteriorating"
    else:
        label = "Steady"
    return round(pol_velocity, 4), round(vol_velocity, 3), label, True


# ── Social history: the only way to get real social velocity ──────────
# One StockTwits call is a snapshot, so multi-day social velocity has to
# be accumulated rather than fetched. Each analysis appends a compact
# (timestamp, count, mean polarity) sample; after a couple of days of
# use, this yields a genuine social trend. Until then the pillar says
# "baseline establishing" instead of inventing one.

_HISTORY_PREFIX = "sentiment_hist:"
_HISTORY_TTL = 60 * 60 * 24 * 14
_HISTORY_MAX_SAMPLES = 96


def record_social_sample(ticker: str, count: int, polarity: float) -> None:
    try:
        import json as _json
        from app.core.redis_client import get_redis_client
        r = get_redis_client()
        key = f"{_HISTORY_PREFIX}{ticker}"
        r.lpush(key, _json.dumps({
            "t": datetime.now(tz=timezone.utc).isoformat(),
            "n": count, "p": round(polarity, 4),
        }))
        r.ltrim(key, 0, _HISTORY_MAX_SAMPLES - 1)
        r.expire(key, _HISTORY_TTL)
    except Exception:
        pass


def social_history(ticker: str) -> list[dict]:
    try:
        import json as _json
        from app.core.redis_client import get_redis_client
        raw = get_redis_client().lrange(f"{_HISTORY_PREFIX}{ticker}", 0, -1)
        return [_json.loads(x) for x in raw]
    except Exception:
        return []


def persist_snapshot(b: "SentimentBreakdown") -> None:
    """
    Write one durable snapshot to Postgres.

    Redis carries the same series for the hot path, but Redis is a cache
    that gets flushed — the durable velocity baseline and the audit trail
    for "why did this read Bearish last Tuesday" have to live in the
    database. See db/migrations/007_sentiment_pillar.sql.

    The unique index on (ticker, hour) means a page refresh loop writes
    one row per hour rather than one per refresh, so ON CONFLICT DO
    NOTHING is the correct resolution: the first reading in an hour is
    kept and the duplicates are discarded rather than biasing the
    baseline toward whatever was true during a refresh burst.

    Never raises — sentiment analysis must not fail because a snapshot
    could not be stored.
    """
    try:
        from sqlalchemy import create_engine, text as sa_text
        from app.core.config import get_settings as _gs
        engine = create_engine(_gs().database_url, pool_pre_ping=True)
        try:
            with engine.begin() as conn:
                conn.execute(sa_text("""
                    INSERT INTO sentiment_snapshots (
                        ticker, overall_score, overall_label,
                        news_score, social_score, sec_tone_score, sec_tone_label,
                        news_polarity, social_polarity,
                        news_document_count, social_message_count,
                        polarity_velocity, volume_velocity, velocity_label,
                        confidence, model_used
                    ) VALUES (
                        :ticker, :overall_score, :overall_label,
                        :news_score, :social_score, :sec_tone_score, :sec_tone_label,
                        :news_polarity, :social_polarity,
                        :news_n, :social_n,
                        :pol_v, :vol_v, :vel_label,
                        :confidence, :model
                    )
                    ON CONFLICT DO NOTHING
                """), {
                    "ticker": b.ticker,
                    "overall_score": b.overall_score,
                    "overall_label": b.overall_label,
                    # NULL, not 50, when a stream produced no reading —
                    # the column comment explains why that distinction is
                    # load-bearing for reweighting.
                    "news_score": b.news_score if b.news_computed else None,
                    "social_score": b.social_score if b.social_computed else None,
                    "sec_tone_score": b.sec_tone_score if b.sec_tone_computed else None,
                    "sec_tone_label": b.sec_tone_label,
                    "news_polarity": b.news_polarity if b.news_computed else None,
                    "social_polarity": b.social_polarity if b.social_computed else None,
                    "news_n": b.news_document_count,
                    "social_n": b.social_message_count,
                    "pol_v": b.polarity_velocity,
                    "vol_v": b.volume_velocity,
                    "vel_label": b.velocity_label,
                    "confidence": b.confidence,
                    "model": b.model_used,
                })
        finally:
            engine.dispose()
    except Exception as exc:
        logger.warning("Sentiment snapshot persist failed",
                       extra={"ticker": b.ticker, "error": str(exc)})


def _social_velocity_from_history(ticker: str, now: datetime,
                                  current_polarity: float) -> tuple[float, bool]:
    """
    Social polarity velocity against this ticker's own accumulated
    history. Returns (velocity, computed).
    """
    samples = social_history(ticker)
    older: list[float] = []
    for s in samples:
        try:
            ts = datetime.fromisoformat(s["t"])
        except (ValueError, KeyError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_h = (now - ts).total_seconds() / 3600.0
        if _VELOCITY_WINDOW_HOURS <= age_h <= 24.0 * 7:
            older.append(float(s.get("p", 0.0)))
    if len(older) < 3:
        return 0.0, False
    return round(current_polarity - statistics.fmean(older), 4), True


def _pick_catalysts(docs: list[src.SentimentDocument], limit: int = 8) -> list[dict]:
    """
    The strongest recent movers, for the UI's catalyst list.

    Ranked by |polarity| * authority * recency so a decisive Reuters
    story today outranks a mildly negative blog post from Tuesday.
    """
    now = datetime.now(tz=timezone.utc)
    news = [d for d in docs if d.channel == "news" and abs(d.polarity) >= 0.25]
    news.sort(
        key=lambda d: abs(d.polarity) * d.authority * _recency_weight(d.published_at, now),
        reverse=True,
    )
    return [{
        "headline": d.headline[:180],
        "source": d.source,
        "url": d.url,
        "published_at": d.published_at.isoformat(),
        "polarity": round(d.polarity, 3),
        "direction": "positive" if d.polarity > 0 else "negative",
        "authority": round(d.authority, 2),
        "evidence": d.evidence[:3],
    } for d in news[:limit]]


# ── SEC tone, off the request path ────────────────────────────────────

_sec_inflight: set[str] = set()
_sec_lock = threading.Lock()


def _spawn_sec_tone(ticker: str) -> None:
    """
    Warm the MD&A cache in the background.

    A cold MD&A read is two ~1MB filing downloads plus parsing. That is
    fine on a worker thread and not fine inside a request, so the first
    analysis of a ticker reports SEC tone as not-computed and every later
    one has it. Identical pattern to the thesis polish and sector medians.
    """
    with _sec_lock:
        if ticker in _sec_inflight:
            return
        _sec_inflight.add(ticker)

    def _work() -> None:
        try:
            filing_tone(ticker)
        except Exception as exc:
            logger.warning("Background MD&A tone failed",
                           extra={"ticker": ticker, "error": str(exc)})
        finally:
            with _sec_lock:
                _sec_inflight.discard(ticker)

    threading.Thread(target=_work, daemon=True, name=f"mdna-{ticker}").start()


# ── Entry point ───────────────────────────────────────────────────────

def analyse_sentiment(ticker: str, company_name: str | None = None) -> SentimentBreakdown:
    """
    Full sentiment read for one ticker.

    Never raises: every source is independently guarded and an empty
    result is reported honestly as low confidence with the sub-scores
    marked not-computed, so the ensemble's reweighting can drop the
    pillar instead of averaging in a fabricated 50.
    """
    ticker = ticker.upper().strip()
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    window_days = settings.sentiment_news_lookback_days

    out = SentimentBreakdown(ticker=ticker, model_used=available_model())
    out.unavailable_sources = list(src.UNAVAILABLE_SOURCES)

    try:
        docs = src.gather_documents(ticker, window_days)
    except Exception as exc:
        logger.error("Sentiment ingestion failed", extra={"ticker": ticker, "error": str(exc)})
        docs = []

    if not docs:
        out.notes.append(
            "No news or social coverage was retrievable for this ticker in the last "
            f"{window_days} days, so the sentiment pillar has no basis and is excluded "
            "from the composite score."
        )
        return out

    aliases = build_aliases(ticker, company_name)
    _score_all(docs, aliases)

    # Documents that never mention the target are about something else.
    # Keeping them would import a competitor's news into this ticker.
    relevant = [d for d in docs if d.scoped]
    dropped = len(docs) - len(relevant)
    if dropped:
        out.notes.append(
            f"{dropped} of {len(docs)} retrieved items never named {ticker} and were "
            "excluded, so competitor and sector-wide news doesn't leak into this score."
        )

    news = [d for d in relevant if d.channel == "news"]
    social = [d for d in relevant if d.channel == "social"]
    out.source_mix = {"news": len(news), "social": len(social)}

    # ── News sub-score ────────────────────────────────────────────────
    if len(news) >= settings.sentiment_min_documents:
        pol, weight = _weighted_polarity(news, now)
        out.news_polarity = round(pol, 4)
        out.news_score = polarity_to_score(pol)
        out.news_computed = True
        out.news_document_count = len(news)
        out.notes.append(
            f"News sub-score from {len(news)} articles over {window_days} days, weighted by "
            "publisher authority and recency (48-hour half-life)."
        )
    else:
        out.news_document_count = len(news)
        out.notes.append(
            f"Only {len(news)} relevant articles found: below the {settings.sentiment_min_documents}"
            "-document minimum, so the news sub-score is excluded rather than resting on a "
            "handful of items."
        )

    # ── Social sub-score and velocity ─────────────────────────────────
    # Velocity is computed over the COMBINED set: news is what actually
    # spans the window (see _velocity's docstring for the measurement).
    pol_v, vol_v, vel_label, vel_computed = _velocity(relevant, now, window_days)
    out.polarity_velocity = pol_v
    out.volume_velocity = vol_v
    out.velocity_label = vel_label
    if vel_computed:
        out.notes.append(
            f"Coverage over the last 24 hours is running at {vol_v:.1f}x the prior period's "
            f"daily rate, with tone {pol_v:+.2f} versus that baseline ({vel_label.lower()})."
        )

    if social:
        pol, _ = _weighted_polarity(social, now)
        out.social_polarity = round(pol, 4)
        out.social_message_count = len(social)

        # Social-specific velocity comes from this ticker's accumulated
        # history, because one StockTwits page cannot supply a baseline.
        soc_v, soc_v_computed = _social_velocity_from_history(ticker, now, pol)
        record_social_sample(ticker, len(social), pol)

        # Level plus velocity: a rising tide of bullishness is different
        # information from a static bullish level, which is the point of
        # tracking velocity at all. Velocity only contributes when it was
        # genuinely measured.
        combined = pol + (soc_v * 0.5 if soc_v_computed else 0.0)
        out.social_score = polarity_to_score(combined)
        out.social_computed = True
        if soc_v_computed:
            out.notes.append(
                f"Social sub-score from {len(social)} StockTwits messages, with tone "
                f"{soc_v:+.2f} against this ticker's own 7-day social history."
            )
        else:
            out.notes.append(
                f"Social sub-score from {len(social)} StockTwits messages. StockTwits serves "
                "only a snapshot of the newest posts, so social velocity is accumulated across "
                "runs and needs a few days of history before it reports."
            )
    else:
        out.notes.append("No retail/social messages were retrievable for this ticker.")

    # ── SEC filing tone ───────────────────────────────────────────────
    try:
        tone = filing_tone(ticker)
    except Exception as exc:
        logger.warning("MD&A tone lookup failed", extra={"ticker": ticker, "error": str(exc)})
        tone = None

    if tone is None:
        _spawn_sec_tone(ticker)
        out.sec_tone_label = "Computing"
        out.notes.append(
            "MD&A filing tone is being read in the background: filings are large, so it is "
            "not fetched on the request path. It will be present on the next analysis."
        )
    else:
        score, computed = tone_to_score(tone)
        out.sec_tone_score = score
        out.sec_tone_computed = computed
        # The label is derived from the SCORE, not taken from the
        # classifier, so the two can never contradict each other. They
        # previously could: NVDA read "Positive" beside a score of 46.9,
        # because the classifier looked only at prose polarity while the
        # score also subtracted for a rise in hedging language. Showing a
        # user a positive word next to a below-neutral number is worse
        # than showing either alone.
        out.sec_tone_label = (
            "Positive" if score >= 58.0 else "Cautious" if score <= 42.0 else "Neutral"
        )
        out.sec_tone_detail = tone.to_dict()
        out.notes.extend(tone.notes)

    # ── Blend ─────────────────────────────────────────────────────────
    # Baselines: news carries the pillar, SEC tone is slow but hard
    # evidence, social is capped as the noisiest and most gameable input.
    parts: list[tuple[str, float, float]] = []   # (name, score, weight)
    if out.news_computed:
        parts.append(("news", out.news_score, 0.55))
    if out.sec_tone_computed:
        parts.append(("sec_tone", out.sec_tone_score, 0.20))
    if out.social_computed:
        parts.append(("social", out.social_score, min(0.25, settings.sentiment_max_social_weight)))

    if parts:
        total_w = sum(w for _, _, w in parts)
        out.overall_score = round(sum(s * w for _, s, w in parts) / total_w, 2)
    else:
        out.overall_score = 50.0
    out.overall_label = score_label(out.overall_score)

    # ── Confidence ────────────────────────────────────────────────────
    # Effective sample size uses authority as the unit, not raw count, so
    # 40 aggregator posts don't read as more confident than 12 wire
    # stories. sqrt-saturating for the reason in the module docstring.
    effective_n = sum(d.authority for d in news) + 0.3 * sum(d.authority for d in social)
    sample_conf = min(1.0, math.sqrt(effective_n / _CONFIDENCE_SATURATION))
    breadth = len(parts) / 3.0        # how many sub-scores actually computed
    out.confidence = round(0.7 * sample_conf + 0.3 * breadth, 3)

    out.catalysts = _pick_catalysts(relevant)
    persist_snapshot(out)
    logger.info("Sentiment analysis complete", extra={
        "ticker": ticker, "score": out.overall_score, "label": out.overall_label,
        "news": len(news), "social": len(social), "confidence": out.confidence,
        "model": out.model_used,
    })
    return out
