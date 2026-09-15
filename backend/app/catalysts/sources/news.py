"""
Company catalysts classified from headlines the sentiment pillar already fetched.

NO EXTRA API CALLS
The sentiment engine pulls a ticker's recent coverage to score it, and keeps
the high-impact articles as `catalysts`. This module reads those. Deals, FDA
outcomes, guidance changes and legal events therefore reach the timeline
without a single additional provider request — the scanner and the analysis
page both get them for free.

CONSERVATIVE BY DESIGN
Headline classification is the least reliable source here, so it is held to
the narrowest patterns that name a concrete event, and anything phrased as
speculation ("could acquire", "explores a sale", "in talks") is downgraded
rather than presented as a done deal. A timeline that confidently shows an
acquisition which never happened is worse than one that misses a rumour.
"""

import re
from datetime import date, datetime, timedelta, timezone

from app.catalysts.models import Catalyst, stable_hash

_SPECULATIVE = re.compile(
    r"\b(could|may|might|would|considers?|considering|explores?|exploring|weighs?|weighing|"
    r"rumou?rs?|reportedly|talks|in talks|eyes|eyeing|potential|possible|mulls?|said to)\b", re.I)

# (type, pattern, impact, direction). Order matters: first match wins.
_RULES: list[tuple[str, re.Pattern, str, str]] = [
    ("regulatory_fda",
     re.compile(r"\bFDA\b.{0,60}\b(approv\w*|clears?|cleared|clearance|authoriz\w*|grants?|granted)\b|"
                r"\b(approv\w*|clearance)\b.{0,40}\bFDA\b", re.I),
     "high", "positive"),
    ("regulatory_fda",
     re.compile(r"\bFDA\b.{0,60}\b(rejects?|rejected|declines?|refus\w*|complete response letter|CRL)\b|"
                r"\bcomplete response letter\b", re.I),
     "high", "negative"),
    ("merger_acquisition",
     re.compile(r"\b(to acquire|acquires|acquired by|to be acquired|agrees? to (buy|acquire)|"
                r"agreed to (buy|acquire)|merger agreement|definitive agreement to|takeover|tender offer|buyout)\b", re.I),
     "high", "unknown"),
    # Deal talk in hedged language ("could acquire", "explores sale"). Kept
    # as its own rule because the firm-deal pattern above deliberately
    # requires agreement language, and the speculative check below then
    # downgrades impact — a rumour is worth seeing, but it is not a deal.
    ("merger_acquisition",
     re.compile(r"\b(could|may|might|would|considers?|considering|explores?|exploring|weighs?|weighing|"
                r"mulls?|eyes|eyeing|in talks to|nears?)\b.{0,25}\b(acquir\w*|buy(ing)?|merg\w*|sale of|takeover|bid for)\b",
                re.I),
     "high", "unknown"),
    ("guidance",
     re.compile(r"\b(raises|raised|lifts|lifted|boosts|boosted|hikes|hiked|ups)\b.{0,30}"
                r"\b(guidance|outlook|forecast)\b", re.I),
     "medium", "positive"),
    ("guidance",
     re.compile(r"\b(cuts|cut|lowers|lowered|slashes|slashed|reduces|reduced|withdraws|withdrew|pulls|pulled)\b.{0,30}"
                r"\b(guidance|outlook|forecast)\b", re.I),
     "medium", "negative"),
    # Resolution language must be tried BEFORE the generic legal rule, or
    # "X drops antitrust lawsuit against Apple" matches "lawsuit" and is
    # filed as bad news for the company it cleared. Direction is set, but
    # impact is LOW on purpose: a headline cannot reliably say who came out
    # ahead (a plaintiff dropping its own suit, a settlement with a fine),
    # so these appear on the timeline and are never argued from in a thesis.
    # "wins", "ends" and "overturns" are deliberately absent — "DOJ wins
    # case against Google" and "shares end lower as probe widens" would
    # both match and both be wrong.
    ("legal_regulatory",
     re.compile(r"\b(drops?|dropped|dismiss\w*|withdraws?|withdrew|abandons?|abandoned|throws? out|threw out|"
                r"tosses|tossed)\b.{0,40}\b(lawsuit|suit|case|probe|investigation|charges|claims?|complaint)\b|"
                r"\b(lawsuit|suit|case|probe|investigation|charges|claims?|complaint)\b.{0,20}\b(is |was |were |been )?"
                r"(dropped|dismissed|withdrawn|tossed|thrown out)\b", re.I),
     "low", "positive"),
    ("legal_regulatory",
     re.compile(r"\b(settles?|settled|settlement|resolves?|resolved|resolution)\b.{0,40}"
                r"\b(lawsuit|suit|case|probe|investigation|charges|claims?|dispute)\b|"
                r"\b(lawsuit|suit|case|probe|investigation|charges|claims?|dispute)\b.{0,25}\b(settle\w*|resolved)\b", re.I),
     "low", "neutral"),
    ("legal_regulatory",
     re.compile(r"\b(sues|sued|lawsuit|class action|antitrust|subpoena|indict\w*|charged by|"
                r"SEC charges|DOJ|probe|investigation|fined|recall)\b", re.I),
     "medium", "negative"),
]

_MAX_AGE_DAYS = 30


def _published(item: dict) -> date | None:
    raw = item.get("published_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        return None


def classify_headline(headline: str) -> tuple[str, str, str, bool] | None:
    """(type, impact, direction, speculative) for the first rule that matches."""
    for ctype, pattern, impact, direction in _RULES:
        if pattern.search(headline):
            speculative = bool(_SPECULATIVE.search(headline))
            if speculative:
                # A rumoured deal is still worth seeing; it is not a deal.
                impact = "medium" if impact == "high" else "low"
            return ctype, impact, direction, speculative
    return None


_TITLES = {
    ("regulatory_fda", "positive"): "FDA approval or clearance reported",
    ("regulatory_fda", "negative"): "FDA rejection or complete response letter reported",
    ("merger_acquisition", "unknown"): "Acquisition or merger reported",
    ("guidance", "positive"): "Guidance raised",
    ("guidance", "negative"): "Guidance cut",
    ("legal_regulatory", "negative"): "Legal or regulatory action reported",
    ("legal_regulatory", "positive"): "Legal or regulatory action dropped",
    ("legal_regulatory", "neutral"): "Legal or regulatory matter settled",
}


def catalysts_from_sentiment(ticker: str, items: list[dict], *, today: date | None = None) -> list[Catalyst]:
    today = today or date.today()
    out: list[Catalyst] = []
    for item in items or []:
        headline = str(item.get("headline") or "").strip()
        day = _published(item)
        if not headline or day is None or day < today - timedelta(days=_MAX_AGE_DAYS):
            continue
        hit = classify_headline(headline)
        if not hit:
            continue
        ctype, impact, direction, speculative = hit
        title = _TITLES.get((ctype, direction), "Company event reported")
        if speculative:
            title = title.replace(" reported", "") + " (speculative)"
        out.append(Catalyst(
            dedupe_key=f"news:{ticker.upper()}:{ctype}:{stable_hash(item.get('url') or headline)}",
            scope="company", ticker=ticker, catalyst_type=ctype, title=title,
            description=headline, event_date=day, date_confirmed=None,
            impact=impact, direction=direction,  # type: ignore[arg-type]
            source=f"news:{item.get('source') or 'unknown'}", source_url=item.get("url"),
            details={"headline": headline, "speculative": speculative,
                     "article_polarity": item.get("polarity"), "publisher_authority": item.get("authority")},
        ))
    return out
