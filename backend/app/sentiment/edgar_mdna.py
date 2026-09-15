"""
app/sentiment/edgar_mdna.py
-----------------------------
Corporate tone from the Management's Discussion and Analysis section of
the latest 10-K / 10-Q, plus the shift versus the previous filing.

=====================================================================
WHY MD&A, AND WHY THE *SHIFT* RATHER THAN THE LEVEL
=====================================================================
MD&A is the one part of a filing where management writes prose rather
than reporting numbers, so it is where tone lives. But the absolute tone
of any MD&A is nearly useless on its own: it is drafted by counsel, it is
uniformly measured, and every company sounds cautious because sounding
cautious is legally protective. Comparing Apple's hedging density to
Pfizer's measures industry and house style, not sentiment.

What *is* informative is a company's tone against its own prior filing.
When the same drafting team, in the same house style, materially
increases the density of uncertainty or risk language quarter over
quarter, something changed in how management sees the business. That
delta is the signal this module produces.

So `filing_tone()` returns two things:
    tone_polarity  the MD&A's own directional language (weak signal)
    tone_shift     change in uncertainty/litigious/constraining density
                   versus the previous comparable filing (real signal)

=====================================================================
COST
=====================================================================
Filings are large (a 10-Q primary document is ~1MB of inline XBRL) and
change four times a year. Everything here is cached in Redis for 24h,
and computed on a background thread by the engine, so no user request
ever waits on two megabyte-scale downloads.

Free, no key. SEC requires a declared User-Agent identifying the
requester (sec.gov/os/webmaster-faq#developers) — a browser-spoofing UA
gets a 403.
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.sentiment.lexicon import category_density, score_long_text

logger = logging.getLogger("aureus.sentiment.edgar")

_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"

_CACHE_TTL = 60 * 60 * 24          # a day; filings are quarterly
_TICKER_MAP_TTL = 60 * 60 * 24 * 7  # the ticker->CIK map is near-static
_CACHE_PREFIX = "mdna:"

_MAX_MDNA_CHARS = 60_000


# One or more descriptive words, then a single contact email at the end.
# Exactly one "@" overall, which is what catches the malformed
# "company@domain@gmail.com" shape this validator exists to reject.
_VALID_UA_RE = re.compile(
    r"[^@\s]+(?:\s+[^@\s]+)*\s+[^@\s]+@[^@\s]+\.[A-Za-z]{2,}"
)


# Domains that are obviously stand-ins. SEC does not verify the address, so a
# placeholder passes format validation and gets served normally — which is worse
# than failing, because the fair-access policy exists so SEC can contact a heavy
# requester, and nobody answers at yourdomain.com.
_PLACEHOLDER_UA_DOMAINS = ("yourdomain.", "example.", "domain.com", "changeme")


def _is_placeholder_ua(value: str) -> bool:
    low = value.lower()
    return any(d in low for d in _PLACEHOLDER_UA_DOMAINS)


def _ua() -> str:
    """
    SEC's fair-access policy wants a real contact address.

    The configured value is validated rather than trusted: the default
    placeholder and malformed addresses (e.g. two '@' signs) get a 403
    from SEC, and a 403 here looks exactly like "this company has no
    filings", which is a genuinely confusing failure to debug. Falling
    back to a known-good literal keeps the source working even when the
    setting is wrong, and logs why.
    """
    # Strip surrounding quotes: a .env value written as
    #   SEC_EDGAR_USER_AGENT="Aureus Intelligence you@example.com"
    # can arrive with the quotes attached depending on how the file is
    # loaded, and a leading quote makes the whole string fail validation.
    configured = (get_settings().sec_edgar_user_agent or "").strip().strip('"\'')

    # SEC asks for a declaring name plus a contact address. The name is
    # normally several words ("Aureus Intelligence"), so the prefix must
    # allow multiple tokens — an earlier single-token pattern here
    # rejected every realistic value, including the correct one, and sent
    # a valid agent down the fallback path.
    if _VALID_UA_RE.fullmatch(configured) and not _is_placeholder_ua(configured):
        return configured
    logger.warning(
        "SEC_EDGAR_USER_AGENT is not a valid 'Name email@domain' string: "
        "using a fallback. SEC returns 403 for malformed agents.",
        extra={"configured": configured},
    )
    return "Aureus Intelligence contact@aureusintelligence.com"


def _headers() -> dict[str, str]:
    return {"User-Agent": _ua(), "Accept-Encoding": "gzip, deflate"}


@dataclass
class FilingTone:
    ticker: str
    form: str                       # "10-K" | "10-Q"
    filing_date: str
    accession: str
    url: str
    tone_polarity: float            # -1..+1 directional language in MD&A
    uncertainty_density: float
    litigious_density: float
    constraining_density: float
    word_count: int
    # Change vs the previous comparable filing. Positive = MORE hedging /
    # risk language than last time, which reads as a cautious shift.
    uncertainty_shift: float | None = None
    litigious_shift: float | None = None
    constraining_shift: float | None = None
    prior_filing_date: str | None = None
    label: str = "Neutral"          # "Positive" | "Neutral" | "Cautious"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "form": self.form, "filing_date": self.filing_date,
            "url": self.url, "tone_polarity": self.tone_polarity,
            "uncertainty_density": self.uncertainty_density,
            "litigious_density": self.litigious_density,
            "constraining_density": self.constraining_density,
            "word_count": self.word_count,
            "uncertainty_shift": self.uncertainty_shift,
            "litigious_shift": self.litigious_shift,
            "constraining_shift": self.constraining_shift,
            "prior_filing_date": self.prior_filing_date,
            "label": self.label, "notes": self.notes,
        }


# ── ticker -> CIK ─────────────────────────────────────────────────────

_ticker_map: dict[str, int] | None = None
_map_lock = threading.Lock()


def _load_ticker_map() -> dict[str, int]:
    global _ticker_map
    if _ticker_map is not None:
        return _ticker_map
    with _map_lock:
        if _ticker_map is not None:
            return _ticker_map
        cached = _cache_get("tickermap")
        if cached:
            _ticker_map = {k: int(v) for k, v in cached.items()}
            return _ticker_map
        try:
            r = httpx.get(_SEC_TICKERS_URL, headers=_headers(), timeout=30.0)
            r.raise_for_status()
            rows = r.json()
            _ticker_map = {
                str(row["ticker"]).upper(): int(row["cik_str"])
                for row in rows.values()
            }
            _cache_put("tickermap", _ticker_map, ttl=_TICKER_MAP_TTL)
        except Exception as exc:
            logger.warning("SEC ticker map fetch failed", extra={"error": str(exc)})
            _ticker_map = {}
    return _ticker_map


def resolve_cik(ticker: str) -> int | None:
    return _load_ticker_map().get(ticker.upper().strip())


# ── Redis cache ───────────────────────────────────────────────────────

def _cache_get(key: str):
    try:
        from app.core.redis_client import get_redis_client
        raw = get_redis_client().get(f"{_CACHE_PREFIX}{key}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_put(key: str, value, ttl: int = _CACHE_TTL) -> None:
    try:
        from app.core.redis_client import get_redis_client
        get_redis_client().setex(f"{_CACHE_PREFIX}{key}", ttl, json.dumps(value))
    except Exception:
        pass


# ── Filing discovery ──────────────────────────────────────────────────

def recent_filings(cik: int, forms=("10-K", "10-Q"), limit: int = 4) -> list[dict]:
    """Most recent 10-K/10-Q filings, newest first."""
    try:
        r = httpx.get(_SEC_SUBMISSIONS.format(cik=cik), headers=_headers(), timeout=30.0)
        r.raise_for_status()
        recent = r.json()["filings"]["recent"]
    except Exception as exc:
        logger.warning("SEC submissions fetch failed", extra={"cik": cik, "error": str(exc)})
        return []

    out: list[dict] = []
    for form, date_, acc, doc in zip(
        recent.get("form", []), recent.get("filingDate", []),
        recent.get("accessionNumber", []), recent.get("primaryDocument", []),
    ):
        if form in forms and doc:
            out.append({
                "form": form, "filing_date": date_, "accession": acc,
                "url": _SEC_ARCHIVE.format(cik=cik, accession=acc.replace("-", ""), doc=doc),
            })
            if len(out) >= limit:
                break
    return out


# ── MD&A extraction ───────────────────────────────────────────────────

# The heading we want, in both forms: Item 7 in a 10-K, Item 2 in a 10-Q.
# Requiring the literal words "Management's Discussion" is what separates
# a real section heading from the many in-text cross-references (e.g.
# "...described in Item 1A of the 2025 Form 10-K..."), which a generic
# r"Item\s+\d+" pattern matches dozens of times per filing.
_MDNA_START = re.compile(
    r"Item\s+(?:2|7)\s*[.:—-]?\s*Management[’'`]?s\s+Discussion\s+and\s+Analysis",
    re.IGNORECASE,
)
# The section ends at the next top-level item heading. Listed explicitly
# rather than "any Item N" so cross-references inside MD&A don't truncate
# it early.
_MDNA_END = re.compile(
    r"Item\s+(?:3|4|7A|8)\s*[.:—-]?\s*"
    r"(?:Quantitative\s+and\s+Qualitative|Controls\s+and\s+Procedures|"
    r"Financial\s+Statements\s+and\s+Supplementary|Legal\s+Proceedings)",
    re.IGNORECASE,
)


def _filing_text(url: str) -> str:
    """Fetch a filing and reduce it to prose."""
    r = httpx.get(url, headers=_headers(), timeout=60.0)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # Tables are financial statements — numbers, not tone. Dropping them
    # keeps density ratios from being diluted by thousands of numeric
    # cells that carry no linguistic signal.
    for tag in soup(["script", "style", "table"]):
        tag.decompose()
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_mdna(url: str) -> str | None:
    """MD&A prose from a filing URL, or None if the section can't be located."""
    try:
        text = _filing_text(url)
    except Exception as exc:
        logger.warning("Filing fetch failed", extra={"url": url, "error": str(exc)})
        return None

    start = _MDNA_START.search(text)
    if not start:
        logger.info("MD&A heading not found in filing", extra={"url": url})
        return None

    tail = text[start.end():]
    end = _MDNA_END.search(tail)
    body = tail[:end.start()] if end else tail[:_MAX_MDNA_CHARS]

    # A real MD&A is thousands of words. Anything shorter means the
    # heading matched a table of contents entry rather than the section.
    if len(body) < 1500:
        logger.info("MD&A match too short: likely a contents entry",
                    extra={"url": url, "chars": len(body)})
        return None
    return body[:_MAX_MDNA_CHARS]


# ── Tone ──────────────────────────────────────────────────────────────

# A shift of this many percentage points in category density is treated
# as a material change in tone. Densities run around 1-3% of tokens, so
# 0.4pp is roughly a 15-30% relative move — large enough not to be
# drafting noise, small enough to catch a genuine change in posture.
_MATERIAL_SHIFT = 0.004


def _classify(polarity: float, unc_shift: float | None, lit_shift: float | None) -> tuple[str, list[str]]:
    notes: list[str] = []
    cautious_signals = 0

    if unc_shift is not None and unc_shift > _MATERIAL_SHIFT:
        cautious_signals += 1
        notes.append(
            f"Uncertainty language is {unc_shift*100:.2f}pp denser than the prior filing: "
            "management is hedging more than it was."
        )
    elif unc_shift is not None and unc_shift < -_MATERIAL_SHIFT:
        notes.append(
            f"Uncertainty language is {abs(unc_shift)*100:.2f}pp sparser than the prior filing: "
            "management is hedging less."
        )

    if lit_shift is not None and lit_shift > _MATERIAL_SHIFT:
        cautious_signals += 1
        notes.append(
            f"Litigation and regulatory language is {lit_shift*100:.2f}pp denser than the prior "
            "filing, which usually means a new or escalating matter is being disclosed."
        )

    if cautious_signals >= 1:
        return "Cautious", notes
    if polarity > 0.15:
        notes.append("MD&A language leans constructive on results and outlook.")
        return "Positive", notes
    if polarity < -0.15:
        notes.append("MD&A language leans negative on results and outlook.")
        return "Cautious", notes
    notes.append("MD&A tone is in line with the prior filing: no material shift detected.")
    return "Neutral", notes


def filing_tone(ticker: str) -> FilingTone | None:
    """
    MD&A tone for the most recent filing, with the shift vs the previous
    comparable one. Cached for a day. Returns None when the company has
    no retrievable filings (common for ADRs and foreign issuers, which
    file 20-F/40-F instead).
    """
    ticker = ticker.upper().strip()
    cached = _cache_get(ticker)
    if cached:
        return FilingTone(**cached) if "ticker" in cached else None

    cik = resolve_cik(ticker)
    if cik is None:
        logger.info("No CIK for ticker, not a US domestic filer", extra={"ticker": ticker})
        return None

    filings = recent_filings(cik)
    if not filings:
        return None

    current = filings[0]
    body = extract_mdna(current["url"])
    if not body:
        return None

    density = category_density(body)
    # score_long_text, not score_text: see that function's docstring for
    # why headline-style saturation misreads a multi-thousand-word filing.
    polarity, _ = score_long_text(body)

    # Prior comparable filing: same form where possible, so a 10-K is
    # compared to a 10-K. Year-over-year and quarter-over-quarter
    # language differ structurally, and comparing across form types
    # manufactures a shift that isn't there.
    prior_density = None
    prior_date = None
    for f in filings[1:]:
        if f["form"] != current["form"]:
            continue
        prior_body = extract_mdna(f["url"])
        if prior_body:
            prior_density = category_density(prior_body)
            prior_date = f["filing_date"]
            break

    def shift(key: str) -> float | None:
        if prior_density is None:
            return None
        return round(density[key] - prior_density[key], 5)

    unc_shift, lit_shift, con_shift = shift("uncertainty"), shift("litigious"), shift("constraining")
    label, notes = _classify(polarity, unc_shift, lit_shift)
    if prior_density is None:
        notes.append("No prior comparable filing was retrievable, so this is an absolute "
                     "reading rather than a shift.")

    tone = FilingTone(
        ticker=ticker, form=current["form"], filing_date=current["filing_date"],
        accession=current["accession"], url=current["url"],
        tone_polarity=polarity,
        uncertainty_density=density["uncertainty"],
        litigious_density=density["litigious"],
        constraining_density=density["constraining"],
        word_count=density["token_count"],
        uncertainty_shift=unc_shift, litigious_shift=lit_shift, constraining_shift=con_shift,
        prior_filing_date=prior_date, label=label, notes=notes,
    )
    _cache_put(ticker, tone.to_dict() | {"accession": tone.accession})
    logger.info("MD&A tone computed", extra={
        "ticker": ticker, "form": tone.form, "label": label, "words": tone.word_count,
    })
    return tone


def tone_to_score(tone: FilingTone | None) -> tuple[float, bool]:
    """
    Map filing tone to the pillar's 0-100 scale.

    Anchored at 50 and moved by the tone shift, because the shift is the
    part that carries information (see module docstring). The directional
    polarity of the prose contributes a smaller nudge. Returns
    (score, computed) so the reweighting layer can drop it cleanly when
    no filing was retrievable.
    """
    if tone is None:
        return 50.0, False

    score = 50.0
    # A denser hedging/risk vocabulary than last filing is bearish.
    # 1pp of extra uncertainty language moves the score 25 points.
    if tone.uncertainty_shift is not None:
        score -= max(-25.0, min(25.0, tone.uncertainty_shift * 2500.0))
    if tone.litigious_shift is not None:
        score -= max(-15.0, min(15.0, tone.litigious_shift * 2500.0))
    # Directional prose is a weaker, secondary contribution.
    score += tone.tone_polarity * 12.0
    return round(max(0.0, min(100.0, score)), 2), True
