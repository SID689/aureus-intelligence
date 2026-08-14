"""
app/analysis/sentiment.py
---------------------------
The Sentiment pillar adapter — the counterpart to fundamental.py and
technical.py, and the only part of app/sentiment/ the ensemble touches.

Its whole job is to turn the rich SentimentBreakdown produced by
app/sentiment/engine.py into the same shape every other pillar reports:
a 0-100 score, a data_completeness figure, per-signal effective weights,
and a signal_breakdown the reasoning and thesis layers can quote.

The sub-signal weights below are baselines. Every one of them declares
`computed`, so reweighting.py drops whatever didn't compute and
redistributes its weight — meaning a ticker with no retrievable filings
is scored on news and social alone rather than being dragged toward 50
by a fabricated neutral SEC reading. That contract is the reason the
pillar swap is safe to make at all.
"""

import logging

from app.analysis.models import SentimentScore
from app.analysis.reweighting import WeightedSignal, reweight
from app.sentiment.engine import analyse_sentiment

logger = logging.getLogger("aureus.analysis.sentiment")

# News is the backbone: highest volume, best provenance, and the only
# stream with genuine multi-day history. SEC tone is slow-moving but is
# management's own words under legal liability, which is why it outranks
# retail chatter despite updating only quarterly. Social is real signal
# about crowd positioning and the most gameable input in the system, so
# it gets the smallest baseline share.
_W_NEWS, _W_SEC, _W_SOCIAL = 0.55, 0.25, 0.20


def run_sentiment_analysis(ticker: str, company_name: str | None = None) -> SentimentScore:
    """
    Score the Sentiment pillar for one ticker.

    Never raises. A total ingestion failure produces a score of 50 with
    data_completeness 0.0, which the ensemble's own reweighting then
    drops from the composite entirely.
    """
    try:
        b = analyse_sentiment(ticker, company_name)
    except Exception as exc:
        logger.error("Sentiment engine failed", extra={"ticker": ticker, "error": str(exc)})
        return SentimentScore(
            ticker=ticker, score=50.0, news_score=50.0, social_score=50.0,
            sec_tone_score=50.0, data_completeness=0.0,
            analysis_notes=[f"Sentiment analysis could not run: {exc}"],
        )

    notes: list[str] = list(b.notes)
    signals: list[dict] = []

    if b.news_computed:
        signals.append({
            "label": "News Sentiment",
            "score": b.news_score,
            "detail": (
                f"{b.news_document_count} articles over the last week score "
                f"{b.news_polarity:+.2f} on average once weighted for publisher authority and "
                f"recency — {'constructive coverage' if b.news_score >= 60 else 'negative coverage' if b.news_score <= 40 else 'a balanced news picture'}"
            ),
        })
    if b.sec_tone_computed:
        d = b.sec_tone_detail or {}
        signals.append({
            "label": "SEC Filing Tone",
            "score": b.sec_tone_score,
            "detail": (
                f"MD&A of the {d.get('form', 'latest filing')} filed {d.get('filing_date', 'recently')} "
                f"reads {b.sec_tone_label.lower()}"
                + (f" versus the {d.get('prior_filing_date')} filing" if d.get("prior_filing_date") else "")
            ),
        })
    if b.social_computed:
        vel = (f", 24-hour volume {b.volume_velocity:.1f}x the prior rate"
               if b.volume_velocity is not None else "")
        signals.append({
            "label": "Social Sentiment",
            "score": b.social_score,
            "detail": (
                f"{b.social_message_count} retail messages score {b.social_polarity:+.2f}{vel} "
                f"({b.velocity_label.lower()})"
            ),
        })

    result = reweight([
        WeightedSignal("news_score", b.news_score, _W_NEWS, b.news_computed),
        WeightedSignal("sec_tone_score", b.sec_tone_score, _W_SEC, b.sec_tone_computed),
        WeightedSignal("social_score", b.social_score, _W_SOCIAL, b.social_computed),
    ])
    if result.dropped_signals:
        notes.append(f"Excluded from scoring (no real data): {', '.join(result.dropped_signals)}")

    # The engine's own confidence reflects SAMPLE SIZE — how many articles
    # actually backed the reading. reweight()'s data_completeness reflects
    # STRUCTURAL coverage — how many sub-streams reported at all. Both
    # matter and they fail independently: forty articles from one stream
    # is complete-but-narrow, one article from each of three streams is
    # broad-but-thin. Taking the product means either failure honestly
    # reduces the pillar's influence on the composite.
    completeness = round(result.data_completeness * max(0.15, b.confidence), 3)

    logger.info("Sentiment analysis complete", extra={
        "ticker": ticker, "score": result.composite_score,
        "data_completeness": completeness, "model": b.model_used,
    })

    return SentimentScore(
        ticker=ticker,
        score=result.composite_score,
        news_score=round(b.news_score, 2),
        social_score=round(b.social_score, 2),
        sec_tone_score=round(b.sec_tone_score, 2),
        news_computed=b.news_computed,
        social_computed=b.social_computed,
        sec_tone_computed=b.sec_tone_computed,
        overall_label=b.overall_label,
        sec_tone_label=b.sec_tone_label,
        velocity_label=b.velocity_label,
        news_document_count=b.news_document_count,
        social_message_count=b.social_message_count,
        news_polarity=b.news_polarity,
        social_polarity=b.social_polarity,
        polarity_velocity=b.polarity_velocity,
        volume_velocity=b.volume_velocity,
        sentiment_confidence=b.confidence,
        model_used=b.model_used,
        catalysts=b.catalysts,
        source_mix=b.source_mix,
        unavailable_sources=b.unavailable_sources,
        sec_tone_detail=b.sec_tone_detail,
        data_completeness=completeness,
        effective_weights=result.effective_weights,
        signal_breakdown=signals,
        analysis_notes=notes,
    )
