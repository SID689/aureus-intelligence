"""
app/sentiment/lexicon.py
--------------------------
A financial-domain polarity lexicon, plus the negation / intensifier
machinery needed to read it correctly.

=====================================================================
WHY NOT VADER (which this codebase already has installed)
=====================================================================
VADER is tuned on social media and general English. On financial text it
is not merely imprecise, it is wrong in a specific and systematic way:
the vocabulary of accounting is full of words that carry strong negative
affect in ordinary usage and none at all in a filing.

    "liability"  "cost"  "expense"  "debt"  "charge"  "obligation"
    "risk"  "loss"  "depreciation"  "restructuring"  "impairment"

A general lexicon marks those negative, so any article that merely
DESCRIBES a balance sheet scores bearish. That is the single largest
source of error in naive financial sentiment, and it is why the research
literature (Loughran & McDonald 2011) rebuilt the word lists from 10-K
text rather than reusing psychology-derived ones.

This module is a finance-first lexicon in that spirit. Neutral accounting
vocabulary is deliberately absent — a word earns a weight only when its
appearance in market commentary genuinely signals direction.

=====================================================================
WHY PHRASES DOMINATE
=====================================================================
Single words are weak evidence in financial news; short phrases are
strong. "Beat" on its own is ambiguous ("beat a retreat"). "Beat
estimates" is unambiguous and is close to the most informative bigram in
the entire domain. So _PHRASES is scored FIRST and at higher magnitude,
and the words it consumes are masked out before unigram scoring runs, so
a phrase is never double-counted against its own component words.

Weights are on a -1.0 .. +1.0 scale, chosen so that a headline containing
one decisive phrase lands near the polarity extreme while a headline
carrying only mild unigrams stays mid-range.

=====================================================================
THE CATEGORY LISTS
=====================================================================
UNCERTAINTY / LITIGIOUS / CONSTRAINING mirror the Loughran-McDonald
categories and are used by edgar_mdna.py rather than by headline
scoring. In an MD&A section the interesting signal is not "is management
happy" (they always sound reasonably happy) but "has the DENSITY of
hedging and risk language shifted since last quarter". Those lists exist
to measure that, and they are scored as frequencies, not polarity.
"""

import re

# ── Multi-word phrases: the high-precision layer ──────────────────────
# Matched case-insensitively on word boundaries. Longest match wins, so
# "raised full-year guidance" beats the shorter "raised guidance".
_PHRASES: dict[str, float] = {
    # ── Earnings surprise: the strongest routine signal in the domain ──
    "beat estimates": 0.85, "beats estimates": 0.85, "beat expectations": 0.85,
    "beats expectations": 0.85, "topped estimates": 0.85, "tops estimates": 0.85,
    "earnings beat": 0.80, "beat on both": 0.88, "blowout quarter": 0.95,
    "record quarter": 0.85, "record revenue": 0.82, "record profit": 0.85,
    "missed estimates": -0.85, "misses estimates": -0.85, "missed expectations": -0.85,
    "misses expectations": -0.85, "earnings miss": -0.82, "fell short of": -0.70,
    "disappointing quarter": -0.85, "disappointing results": -0.82,
    "worse than expected": -0.80, "better than expected": 0.80,
    "in line with estimates": 0.05, "mixed results": -0.15,

    # ── Guidance: forward-looking, weighted above trailing results ─────
    "raised guidance": 0.90, "raises guidance": 0.90, "boosted guidance": 0.90,
    "raised its outlook": 0.88, "raised full-year": 0.88, "upbeat guidance": 0.85,
    "strong guidance": 0.82, "guidance above": 0.85,
    "cut guidance": -0.92, "cuts guidance": -0.92, "lowered guidance": -0.92,
    "slashed guidance": -0.95, "withdrew guidance": -0.95, "withdraws guidance": -0.95,
    "suspended guidance": -0.92, "weak guidance": -0.85, "guidance below": -0.85,
    "cautious outlook": -0.60, "warns on": -0.80, "profit warning": -0.90,

    # ── Analyst actions ────────────────────────────────────────────────
    "price target raised": 0.70, "raises price target": 0.70, "raised price target": 0.70,
    "upgraded to buy": 0.85, "upgrades to buy": 0.85, "initiated with buy": 0.70,
    "double upgrade": 0.90, "top pick": 0.70, "overweight rating": 0.60,
    "price target cut": -0.70, "cuts price target": -0.70, "lowered price target": -0.70,
    "downgraded to sell": -0.88, "downgrades to sell": -0.88, "downgraded to hold": -0.45,
    "double downgrade": -0.92, "underweight rating": -0.60,

    # ── Capital returns ────────────────────────────────────────────────
    "buyback": 0.55, "share repurchase": 0.55, "increased dividend": 0.70,
    "raises dividend": 0.70, "special dividend": 0.65, "dividend hike": 0.70,
    "cut dividend": -0.88, "cuts dividend": -0.88, "suspended dividend": -0.92,
    "dividend cut": -0.88, "eliminated dividend": -0.92,
    "dilutive offering": -0.65, "secondary offering": -0.45, "equity raise": -0.40,

    # ── Corporate distress: the tail that matters most ─────────────────
    "going concern": -0.95, "chapter 11": -0.98, "files for bankruptcy": -0.98,
    "bankruptcy protection": -0.95, "debt restructuring": -0.70,
    "covenant breach": -0.85, "credit downgrade": -0.75, "liquidity crisis": -0.92,
    "accounting irregularities": -0.95, "material weakness": -0.80,
    "restates earnings": -0.88, "restatement": -0.80, "auditor resigned": -0.92,
    "delisting": -0.90, "short seller report": -0.80, "fraud allegations": -0.92,

    # ── Regulatory / legal ─────────────────────────────────────────────
    "sec investigation": -0.88, "doj investigation": -0.88, "under investigation": -0.80,
    "antitrust lawsuit": -0.70, "class action": -0.65, "regulatory probe": -0.75,
    "fda approval": 0.90, "fda approved": 0.90, "phase 3 success": 0.92,
    "breakthrough designation": 0.80, "patent granted": 0.50,
    "fda rejection": -0.92, "complete response letter": -0.88,
    "clinical hold": -0.85, "trial failed": -0.92, "recalled": -0.65,
    "settled with": 0.20, "settlement reached": 0.25,

    # ── M&A ────────────────────────────────────────────────────────────
    "acquisition target": 0.70, "takeover bid": 0.75, "buyout offer": 0.75,
    "to be acquired": 0.70, "merger agreement": 0.55, "strategic review": 0.35,
    "deal collapsed": -0.70, "terminated the merger": -0.70, "deal blocked": -0.72,

    # ── Operations / leadership ────────────────────────────────────────
    "market share gains": 0.65, "margin expansion": 0.72, "record backlog": 0.70,
    "strong demand": 0.70, "demand surge": 0.75, "capacity expansion": 0.45,
    "margin compression": -0.72, "market share loss": -0.68, "inventory glut": -0.70,
    "demand weakness": -0.75, "soft demand": -0.70, "order cancellations": -0.75,
    "mass layoffs": -0.45, "plant closure": -0.55, "production halt": -0.72,
    "supply chain disruption": -0.62, "ceo resigns": -0.55, "cfo resigns": -0.62,
    "abrupt departure": -0.65, "executive exodus": -0.72,

    # ── Price action language ──────────────────────────────────────────
    "all-time high": 0.72, "record high": 0.70, "breaks out": 0.60,
    "surges": 0.70, "soars": 0.78, "rallies": 0.62, "jumps": 0.62,
    "52-week low": -0.70, "plunges": -0.80, "tumbles": -0.75, "craters": -0.85,
    "sinks": -0.70, "slumps": -0.68, "sell-off": -0.62, "bear market": -0.65,
    "short squeeze": 0.55, "dead cat bounce": -0.55,
}

# ── Single words: the broad, weaker layer ─────────────────────────────
# Note what is NOT here: cost, expense, debt, liability, risk, charge,
# obligation, depreciation, restructuring. Those are the vocabulary of
# accounting, not of direction, and including them is exactly the failure
# mode described in this module's docstring.
_UNIGRAMS: dict[str, float] = {
    # positive
    "outperform": 0.65, "outperformed": 0.65, "outperforming": 0.60,
    "upgrade": 0.65, "upgraded": 0.65, "bullish": 0.70, "optimistic": 0.55,
    "accelerating": 0.55, "accelerated": 0.50, "robust": 0.55, "resilient": 0.45,
    "profitable": 0.55, "profitability": 0.35, "growth": 0.35, "growing": 0.35,
    "expansion": 0.45, "expanding": 0.42, "momentum": 0.42, "rebound": 0.55,
    "recovery": 0.50, "turnaround": 0.55, "breakthrough": 0.70, "innovative": 0.35,
    "exceeded": 0.70, "exceeding": 0.68, "surpassed": 0.70, "strengthened": 0.55,
    "gains": 0.45, "gained": 0.45, "climbed": 0.50, "advanced": 0.42,
    "upside": 0.55, "undervalued": 0.55, "attractive": 0.45, "favorable": 0.50,
    "approval": 0.55, "approved": 0.55, "awarded": 0.45, "secured": 0.40,
    "partnership": 0.35, "expands": 0.42, "launches": 0.30, "unveils": 0.28,

    # negative
    "underperform": -0.65, "underperformed": -0.65, "underperforming": -0.62,
    "downgrade": -0.65, "downgraded": -0.65, "bearish": -0.70, "pessimistic": -0.55,
    "decelerating": -0.55, "slowdown": -0.62, "slowing": -0.55, "sluggish": -0.58,
    "weakness": -0.60, "weakened": -0.60, "weaker": -0.55, "deteriorating": -0.75,
    "declining": -0.58, "declined": -0.55, "decline": -0.52, "shrinking": -0.60,
    "contraction": -0.62, "headwinds": -0.58, "pressured": -0.52, "pressure": -0.35,
    "disappointing": -0.75, "disappointed": -0.70, "concerns": -0.48, "concerned": -0.45,
    "warning": -0.70, "warned": -0.68, "warns": -0.68, "caution": -0.45,
    "cautious": -0.48, "uncertainty": -0.45, "volatile": -0.32, "turmoil": -0.68,
    "overvalued": -0.58, "expensive": -0.35, "unfavorable": -0.55,
    "lawsuit": -0.55, "litigation": -0.48, "probe": -0.58, "subpoena": -0.72,
    "penalty": -0.58, "fine": -0.45, "violation": -0.65, "misconduct": -0.80,
    "resignation": -0.48, "layoffs": -0.42, "closure": -0.48, "halted": -0.62,
    "suspended": -0.62, "delayed": -0.48, "delay": -0.45, "setback": -0.68,
    "shortfall": -0.68, "downturn": -0.65, "recession": -0.60, "default": -0.82,
    "insolvency": -0.90, "writedown": -0.70, "write-down": -0.70, "impaired": -0.55,
}

# ── Modifier machinery ────────────────────────────────────────────────
# Negators flip polarity, but at a discount: "not great" is mildly
# negative, not the mirror image of "great". 0.75 is the standard
# damping factor used in the sentiment literature.
_NEGATORS = frozenset({
    "not", "no", "never", "none", "cannot", "cant", "wont", "isnt", "arent",
    "wasnt", "werent", "didnt", "doesnt", "dont", "without", "lacks", "lacked",
    "lacking", "failed", "fails", "fail", "unable", "absent", "hardly",
    "barely", "scarcely", "rather than", "instead of", "far from",
})
_NEGATION_DAMPING = 0.75
_NEGATION_WINDOW = 3   # tokens to look back for a negator

_INTENSIFIERS: dict[str, float] = {
    "very": 1.30, "extremely": 1.50, "significantly": 1.35, "substantially": 1.35,
    "sharply": 1.40, "dramatically": 1.45, "massively": 1.50, "hugely": 1.45,
    "considerably": 1.30, "notably": 1.20, "markedly": 1.30, "deeply": 1.35,
    "severely": 1.45, "steeply": 1.35, "strongly": 1.30, "materially": 1.30,
    "record": 1.35, "unprecedented": 1.50,
    # downtoners
    "slightly": 0.55, "marginally": 0.50, "somewhat": 0.65, "modestly": 0.60,
    "moderately": 0.70, "mildly": 0.55, "partially": 0.70, "fractionally": 0.45,
    "largely": 0.90, "broadly": 0.90,
}

# ── Loughran-McDonald-style category lists (used by edgar_mdna.py) ────
# Frequencies, not polarity. The MD&A question is whether hedging and
# risk language got DENSER, which is a tone shift even when every
# individual sentence still reads as neutral corporate prose.
UNCERTAINTY_TERMS = frozenset({
    "approximately", "assume", "assumed", "assumes", "assumption", "assumptions",
    "believe", "believes", "could", "depend", "depends", "depending", "may",
    "maybe", "might", "possible", "possibly", "potential", "potentially",
    "predict", "predicted", "preliminary", "probable", "probably", "risk",
    "risks", "risky", "seems", "sometimes", "uncertain", "uncertainty",
    "uncertainties", "unclear", "unknown", "unpredictable", "vary", "varying",
    "volatile", "volatility", "fluctuate", "fluctuations", "exposure",
    "anticipate", "anticipated", "estimate", "estimates", "tentative",
})
LITIGIOUS_TERMS = frozenset({
    "litigation", "lawsuit", "lawsuits", "plaintiff", "plaintiffs", "defendant",
    "court", "courts", "judicial", "arbitration", "settlement", "settlements",
    "subpoena", "testimony", "allegation", "allegations", "alleged", "claimant",
    "damages", "injunction", "indictment", "prosecution", "regulatory",
    "noncompliance", "violation", "violations", "breach", "penalty", "penalties",
    "investigation", "investigations", "sanctions",
})
CONSTRAINING_TERMS = frozenset({
    "restrict", "restricted", "restriction", "restrictions", "constrain",
    "constrained", "constraint", "constraints", "covenant", "covenants",
    "obligate", "obligated", "obligation", "obligations", "require", "required",
    "requirement", "requirements", "mandatory", "prohibit", "prohibited",
    "limitation", "limitations", "encumber", "encumbrance", "impair", "impaired",
})

# ── Compiled matchers ─────────────────────────────────────────────────
# Phrases sorted longest-first so the alternation prefers the most
# specific match ("raised full-year" before "raised guidance").
_PHRASE_RE = re.compile(
    r"\b(" + "|".join(
        re.escape(p) for p in sorted(_PHRASES, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9'\-]+")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def phrase_hits(text: str) -> list[tuple[str, float]]:
    """Every phrase found, with its weight. Exposed for explainability."""
    return [(m.group(0).lower(), _PHRASES[m.group(0).lower()])
            for m in _PHRASE_RE.finditer(_normalise(text))]


def score_text(text: str) -> tuple[float, list[str]]:
    """
    Score one piece of text on -1.0 .. +1.0.

    Returns (polarity, evidence) where `evidence` names the phrases and
    words that actually moved the number — the pillar surfaces these so a
    user can see WHY an article was read as bearish rather than being
    handed a bare score.

    Scoring is deliberately saturating rather than additive: five mildly
    positive words should not out-vote one "cut guidance". The magnitude
    of the strongest single hit sets the floor, and the remaining hits
    can only pull it partway.
    """
    if not text or not text.strip():
        return 0.0, []

    norm = _normalise(text)
    evidence: list[str] = []
    weights: list[float] = []

    # ── 1. Phrases first, then mask them out ──────────────────────────
    masked = norm
    for match in _PHRASE_RE.finditer(norm):
        phrase = match.group(0).lower()
        w = _PHRASES[phrase]
        # A negator immediately before the phrase flips it: "did not beat
        # estimates" must not score +0.85.
        prefix_tokens = _TOKEN_RE.findall(norm[max(0, match.start() - 40):match.start()])
        if any(t in _NEGATORS for t in prefix_tokens[-_NEGATION_WINDOW:]):
            w = -w * _NEGATION_DAMPING
            evidence.append(f"NOT {phrase} ({w:+.2f})")
        else:
            evidence.append(f"{phrase} ({w:+.2f})")
        weights.append(w)
    masked = _PHRASE_RE.sub(" ", norm)

    # ── 2. Unigrams over the masked remainder ─────────────────────────
    tokens = _TOKEN_RE.findall(masked)
    for i, tok in enumerate(tokens):
        base = _UNIGRAMS.get(tok)
        if base is None:
            continue
        w = base
        window = tokens[max(0, i - _NEGATION_WINDOW):i]
        if any(t in _NEGATORS for t in window):
            w = -w * _NEGATION_DAMPING
            label = f"NOT {tok}"
        else:
            label = tok
        for t in window[-2:]:
            if t in _INTENSIFIERS:
                w *= _INTENSIFIERS[t]
                label = f"{t} {label}"
                break
        w = max(-1.0, min(1.0, w))
        evidence.append(f"{label} ({w:+.2f})")
        weights.append(w)

    if not weights:
        return 0.0, []

    # ── 3. Saturating combination ─────────────────────────────────────
    # Anchor on the largest-magnitude hit, then let everything else move
    # it by a damped average. This keeps one decisive phrase decisive.
    # Index-based removal, not value-based: two hits can share a weight,
    # and `w is not dominant` on floats is an identity test that would
    # silently drop the duplicate as well.
    dom_idx = max(range(len(weights)), key=lambda i: abs(weights[i]))
    dominant = weights[dom_idx]
    others = [w for i, w in enumerate(weights) if i != dom_idx]
    if others:
        pull = sum(others) / len(others)
        combined = dominant + 0.35 * (pull - dominant) * (1 - abs(dominant))
    else:
        combined = dominant

    return round(max(-1.0, min(1.0, combined)), 4), evidence[:8]


def score_long_text(text: str, max_sentences: int = 400) -> tuple[float, list[str]]:
    """
    Score a long document (an MD&A section, a full article body).

    `score_text` deliberately saturates: it anchors on the strongest hit
    so that one "cut guidance" cannot be out-voted by mild filler. That is
    right for a headline and badly wrong for a 6,000-word filing, where
    the strongest hit is essentially guaranteed to be some severe term
    buried in a risk paragraph. Applied to a document, saturation makes
    every company look alarming — measured on real 10-Qs it scored both
    Apple and Boeing near -0.5 to -0.7, which is not a distinction.

    So long text is scored sentence by sentence and AVERAGED over the
    sentences that carried any signal. A single severe phrase then moves
    the document a little, and a pervasive change in tone moves it a lot,
    which is the behaviour the MD&A comparison actually needs.
    """
    if not text or not text.strip():
        return 0.0, []

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 4]
    scored: list[float] = []
    evidence: list[str] = []
    for sentence in sentences[:max_sentences]:
        s, ev = score_text(sentence)
        if s != 0.0:
            scored.append(s)
            if len(evidence) < 8 and abs(s) >= 0.5:
                evidence.extend(ev[:2])

    if not scored:
        return 0.0, []
    return round(sum(scored) / len(scored), 4), evidence[:8]


def category_density(text: str) -> dict[str, float]:
    """
    Share of tokens falling in each Loughran-McDonald-style category.

    Used for MD&A tone: absolute levels are not comparable across
    companies (a biotech is always more uncertain than a utility), but a
    shift in the same company's own density between filings is real
    signal.
    """
    tokens = _TOKEN_RE.findall(_normalise(text))
    n = len(tokens)
    if n == 0:
        return {"uncertainty": 0.0, "litigious": 0.0, "constraining": 0.0, "token_count": 0}
    return {
        "uncertainty": round(sum(t in UNCERTAINTY_TERMS for t in tokens) / n, 5),
        "litigious": round(sum(t in LITIGIOUS_TERMS for t in tokens) / n, 5),
        "constraining": round(sum(t in CONSTRAINING_TERMS for t in tokens) / n, 5),
        "token_count": n,
    }
