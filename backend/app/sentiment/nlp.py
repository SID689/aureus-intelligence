"""
app/sentiment/nlp.py
----------------------
The model layer: turns a piece of text about a company into a polarity on
-1.0 .. +1.0, using the best model actually available on this machine.

=====================================================================
MODEL SELECTION (mirrors analysis/llm_provider.py deliberately)
=====================================================================
    1. finbert   ProsusAI/finbert — BERT fine-tuned on financial text.
                 Opt-in, because it costs ~2GB of image and ~500MB RSS.
    2. lexicon   The finance-domain lexicon in lexicon.py. Always
                 available, zero dependencies, no download.

The lexicon is the DEFAULT, not a panic fallback. On headline-length
financial text — which is what almost every source here returns — a
domain lexicon with phrase matching and negation handling is genuinely
competitive, because headlines are short, formulaic, and built from a
small vocabulary of decisive phrases ("cut guidance", "beat estimates")
that the lexicon matches exactly. FinBERT's advantage shows up on longer
free prose, which is why edgar_mdna.py benefits from it most.

Enabling FinBERT (owner action, free, no API key):
    1. add to backend/requirements.txt:   transformers>=4.40  torch>=2.2
    2. docker compose build backend
    3. set SENTIMENT_MODEL=finbert in backend/.env
The first call downloads ~440MB from HuggingFace into a cached volume.
On an 8GB machine already running this stack, check free RAM first.

=====================================================================
ASPECT-BASED SENTIMENT (ABSA)
=====================================================================
The brief's requirement — score sentiment tied to the TARGET ticker, not
to whatever else the article mentions — is handled at the text level
rather than by a specialised ABSA model, and that turns out to be both
cheaper and more robust.

An article headlined "Nvidia soars while Intel slumps on datacenter
share shift" is strongly positive for NVDA and strongly negative for
INTC. Scoring the whole document gives both tickers the same near-zero
number, which is wrong for both. So `target_scope()` splits the text into
sentences and keeps only those that actually mention the target's aliases
before scoring. Competitor sentences never enter the target's score.

Two guards on that:
  - a headline naming the target is always kept, since headlines are
    about their subject by construction;
  - if nothing matches at all we return `scoped=False` and the caller
    downweights the document rather than scoring an unrelated article.
"""

import logging
import re
import threading

from app.core.config import get_settings
from app.sentiment.lexicon import score_text

logger = logging.getLogger("aureus.sentiment.nlp")

ModelName = str  # "finbert" | "lexicon"

# ── FinBERT lazy singleton ────────────────────────────────────────────
_finbert_lock = threading.Lock()
_finbert_pipe = None
_finbert_failed = False


def _load_finbert():
    """
    Load ProsusAI/finbert once per process. Returns None if unavailable,
    and remembers the failure so a missing dependency costs one import
    attempt rather than one per article.
    """
    global _finbert_pipe, _finbert_failed
    if _finbert_pipe is not None or _finbert_failed:
        return _finbert_pipe
    with _finbert_lock:
        if _finbert_pipe is not None or _finbert_failed:
            return _finbert_pipe
        try:
            from transformers import pipeline
            _finbert_pipe = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                truncation=True,
                max_length=512,
            )
            logger.info("FinBERT loaded")
        except Exception as exc:
            _finbert_failed = True
            logger.info("FinBERT unavailable, using the financial lexicon",
                        extra={"error": str(exc)})
    return _finbert_pipe


def available_model() -> ModelName:
    """Which model will actually score text on this machine, right now."""
    if get_settings().sentiment_model == "finbert" and _load_finbert() is not None:
        return "finbert"
    return "lexicon"


# ── Aspect targeting ──────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'$])")

# Suffixes stripped when deriving aliases from a registered company name,
# so "Apple Inc." also matches a headline that just says "Apple".
_CORP_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|"
    r"holdings|holding|group|sa|nv|ag|se|lp|llc|class [abc])\b\.?",
    re.IGNORECASE,
)


def build_aliases(ticker: str, company_name: str | None = None) -> set[str]:
    """
    The surface forms that mean "this company" in running text.

    Kept deliberately tight. A loose alias set is worse than a small one:
    matching the bare word "Apple" inside an article about fruit prices
    injects pure noise into AAPL's score, and there is no downstream step
    that can detect it.
    """
    aliases: set[str] = {ticker.upper(), f"${ticker.upper()}"}
    if company_name:
        cleaned = _CORP_SUFFIXES.sub("", company_name).strip(" ,.")
        if len(cleaned) >= 3:
            aliases.add(cleaned)
            # First token only when it is distinctive enough to stand
            # alone — "Advanced" (from Advanced Micro Devices) is not.
            head = cleaned.split()[0]
            if len(head) >= 5 and head.lower() not in _GENERIC_HEADS:
                aliases.add(head)
    return aliases


_GENERIC_HEADS = frozenset({
    "advanced", "american", "national", "general", "international", "united",
    "global", "first", "new", "north", "south", "east", "west", "central",
    "standard", "federal", "public", "premier", "capital", "financial",
})


def _symbol_aliases(aliases: set[str]) -> set[str]:
    """
    Which aliases are ticker symbols, decided exactly rather than guessed.

    build_aliases() always emits a ticker as the pair {"NVDA", "$NVDA"},
    and never emits a "$" form for a company name. So an alias is a symbol
    precisely when its cash-tagged twin is also in the set. That beats any
    width-or-case heuristic, which is what previously misfiled the
    six-letter, all-caps company name "NVIDIA" as a ticker and made it
    unmatchable against "Nvidia" in prose.
    """
    return {a for a in aliases if a.startswith("$") or f"${a}" in aliases}


def target_scope(headline: str, body: str, aliases: set[str]) -> tuple[str, bool]:
    """
    Reduce a document to the parts that are actually about the target.

    Returns (scoped_text, matched). `matched` is False when the target is
    nowhere in the document, which tells the caller this article is not
    really about this company.
    """
    # Case sensitivity is decided per alias, and NOT by asking whether the
    # alias is upper-case. Company names are frequently all-caps in a
    # registry ("NVIDIA Corporation", "IBM") while appearing in normal
    # case in prose ("Nvidia"), so an isupper() test silently makes those
    # names unmatchable — the exact bug this comment replaces.
    #
    # The real distinction is symbol vs name. A ticker must match exactly,
    # because lowercasing it collides with ordinary words ("all" vs ALL,
    # "on" vs ON). A company name has no such collision risk and should
    # match however a journalist happened to capitalise it.
    symbols = _symbol_aliases(aliases)
    alias_res = [
        re.compile(rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])",
                   0 if a in symbols else re.IGNORECASE)
        for a in aliases if a
    ]

    def mentions(text: str) -> bool:
        return any(r.search(text) for r in alias_res)

    kept: list[str] = []
    headline_hit = bool(headline) and mentions(headline)
    if headline_hit:
        kept.append(headline)

    body_hit = False
    if body:
        for sentence in _SENTENCE_RE.split(body):
            if mentions(sentence):
                kept.append(sentence)
                body_hit = True

    if kept:
        return " ".join(kept), True

    # Nothing named the target. If the document came from a per-ticker
    # feed the association is still implied by the source, so hand back
    # the headline and let the caller decide — but flag it as unscoped.
    return (headline or body or ""), (headline_hit or body_hit)


# ── Scoring ───────────────────────────────────────────────────────────

def _finbert_polarity(text: str) -> float | None:
    """
    FinBERT emits positive / negative / neutral. Collapse to a signed
    scalar by taking the signed probability of the winning directional
    label; a confident neutral is genuinely 0, not a missing value.
    """
    pipe = _load_finbert()
    if pipe is None:
        return None
    try:
        out = pipe(text[:2000])
        if not out:
            return None
        label = str(out[0]["label"]).lower()
        conf = float(out[0]["score"])
        if label.startswith("pos"):
            return round(conf, 4)
        if label.startswith("neg"):
            return round(-conf, 4)
        return 0.0
    except Exception as exc:
        logger.warning("FinBERT scoring failed, falling back to lexicon",
                       extra={"error": str(exc)})
        return None


def score_document(
    headline: str,
    body: str,
    aliases: set[str],
) -> dict:
    """
    Score one document for one target company.

    Returns a dict rather than a scalar because everything downstream —
    the UI catalyst list, the thesis engine, the reasoning text — needs to
    show its work:
        polarity   -1..+1
        model      which model produced it
        scoped     did the text actually mention the target
        evidence   the phrases that moved the score (lexicon only)
    """
    scoped_text, matched = target_scope(headline, body, aliases)
    if not scoped_text.strip():
        return {"polarity": 0.0, "model": "none", "scoped": False, "evidence": []}

    if available_model() == "finbert":
        p = _finbert_polarity(scoped_text)
        if p is not None:
            # Even with FinBERT, run the lexicon for its evidence strings.
            # FinBERT gives a number and no explanation; the phrase hits
            # are what make the number legible to a user.
            _, evidence = score_text(scoped_text)
            return {"polarity": p, "model": "finbert", "scoped": matched,
                    "evidence": evidence}

    polarity, evidence = score_text(scoped_text)
    return {"polarity": polarity, "model": "lexicon", "scoped": matched,
            "evidence": evidence}
