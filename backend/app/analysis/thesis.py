"""
app/analysis/thesis.py
------------------------
Bull and Bear case synthesis.

=====================================================================
DETERMINISTIC FIRST, LLM SECOND — AND WHY THAT ORDER MATTERS HERE
=====================================================================
The obvious build is "hand the metrics to a model and ask for a bull and
bear case". That fails two ways in this codebase.

First, ANTHROPIC_API_KEY is currently a placeholder, so an LLM-only engine
produces NOTHING at all — every request would 500 or return empty cases.
The established pattern here (see analysis/reasoning.py, voice/conversation.py)
is deterministic-first with optional polish, and this module follows it.

Second, and more important: an LLM asked to argue a side will happily
invent a driver. The brief's own rule — never produce vague filler, always
pair a concrete financial driver with its impact — is far easier to
GUARANTEE structurally than to prompt for. So every bullet here is
constructed from a metric that was actually computed, with the real number
interpolated into the text. A point cannot appear unless the data behind it
exists. The optional LLM pass may only rewrite that prose for flow; it is
given the finished bullets and forbidden to add claims, and its output is
validated by the same guardrails as everything else before it is returned.

=====================================================================
FALSIFIABILITY
=====================================================================
A thesis you cannot be wrong about is worthless. Each case therefore also
carries `what_would_change_this` — the specific, observable condition that
would break the argument. That is the difference between analysis and
advocacy, and it is generated from the same metrics as the case itself.
"""

import logging
from dataclasses import dataclass, field
from typing import Literal

from app.analysis.models import FundamentalScore, QuantitativeScore, TechnicalScore
from app.core.config import get_settings

logger = logging.getLogger("aureus.analysis.thesis")

Horizon = Literal["short_term", "medium_term", "long_term"]

# Which categories lead for each horizon. A five-day view cares about
# positioning and momentum; a multi-year view cares about the business.
_HORIZON_EMPHASIS: dict[Horizon, list[str]] = {
    "short_term":  ["Momentum & Positioning", "Volatility & Levels", "Valuation & Catalysts"],
    "medium_term": ["Momentum & Positioning", "Growth & Profitability", "Valuation & Catalysts", "Risk-Adjusted Performance"],
    "long_term":   ["Growth & Profitability", "Balance Sheet & Durability", "Valuation & Catalysts", "Risk-Adjusted Performance"],
}


@dataclass
class ThesisPoint:
    category: str
    headline: str          # the bolded claim
    detail: str            # driver -> impact, with the real number in it
    metric_label: str      # badge shown in the UI
    metric_value: str


@dataclass
class Thesis:
    stance: Literal["bull", "bear"]
    summary: str
    points: list[ThesisPoint] = field(default_factory=list)
    what_would_change_this: list[str] = field(default_factory=list)
    source: str = "deterministic"

    def to_dict(self) -> dict:
        return {
            "stance": self.stance,
            "summary": self.summary,
            "points": [
                {"category": p.category, "headline": p.headline, "detail": p.detail,
                 "metric_label": p.metric_label, "metric_value": p.metric_value}
                for p in self.points
            ],
            "what_would_change_this": self.what_would_change_this,
            "source": self.source,
        }


def _pct(v: float | None, digits: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{digits}f}%"


# =====================================================================
# Bull case
# =====================================================================

def _bull_points(f: FundamentalScore, t: TechnicalScore, q: QuantitativeScore,
                 fd, horizon: Horizon) -> list[ThesisPoint]:
    pts: list[ThesisPoint] = []

    # ── Growth & Profitability ─────────────────────────────────────
    if fd.gross_margin is not None and fd.gross_margin >= 0.35:
        pts.append(ThesisPoint(
            "Growth & Profitability",
            "Gross margin indicates genuine pricing power",
            f"A {_pct(fd.gross_margin)} gross margin means each incremental dollar of revenue "
            f"carries {_pct(fd.gross_margin)} of contribution before operating costs. That is the "
            f"cushion that funds R&D and buybacks through a downturn without needing external capital.",
            "Gross Margin", _pct(fd.gross_margin),
        ))
    if fd.operating_margin is not None and fd.operating_margin >= 0.15:
        pts.append(ThesisPoint(
            "Growth & Profitability",
            "Operating leverage is already being realised",
            f"An operating margin of {_pct(fd.operating_margin)} shows the cost base is not scaling "
            f"with revenue — incremental sales drop through to profit rather than being consumed by "
            f"headcount and overhead.",
            "Operating Margin", _pct(fd.operating_margin),
        ))
    if fd.revenue_growth_yoy is not None and fd.revenue_growth_yoy >= 0.08:
        pts.append(ThesisPoint(
            "Growth & Profitability",
            "Top line is compounding, not stalling",
            f"Revenue grew {_pct(fd.revenue_growth_yoy)} year-over-year. Sustained at that rate the "
            f"business roughly doubles in {max(1, round(72 / (fd.revenue_growth_yoy * 100)))} years, "
            f"which is what allows a premium multiple to be grown into rather than paid down.",
            "Revenue Growth", _pct(fd.revenue_growth_yoy),
        ))
    if fd.return_on_equity is not None and fd.return_on_equity >= 0.18:
        pts.append(ThesisPoint(
            "Growth & Profitability",
            "Capital is being reinvested at a high return",
            f"ROE of {_pct(fd.return_on_equity)} means retained earnings compound internally at a rate "
            f"most alternative uses of that capital cannot match — the mechanical driver of long-run "
            f"per-share value.",
            "ROE", _pct(fd.return_on_equity),
        ))

    # ── Valuation & Catalysts ──────────────────────────────────────
    if f.dcf_detail and f.dcf_detail.margin_of_safety > 0.10:
        d = f.dcf_detail
        pts.append(ThesisPoint(
            "Valuation & Catalysts",
            "Trading below the model's intrinsic estimate",
            f"A two-stage DCF puts intrinsic value near ${d.intrinsic_value_per_share:.2f} against a "
            f"${d.current_price:.2f} price — a {_pct(d.margin_of_safety)} margin of safety. Closing even "
            f"half that gap is a material return without requiring any operational surprise.",
            "Margin of Safety", _pct(d.margin_of_safety),
        ))
    if fd.pe_ratio is not None and 0 < fd.pe_ratio < 20:
        pts.append(ThesisPoint(
            "Valuation & Catalysts",
            "Earnings multiple leaves room for re-rating",
            f"At a {fd.pe_ratio:.1f}x P/E the market is pricing limited growth. If execution simply "
            f"continues, multiple expansion contributes to return alongside earnings — the two "
            f"compounding together.",
            "P/E", f"{fd.pe_ratio:.1f}x",
        ))

    # ── Balance Sheet & Durability ─────────────────────────────────
    if fd.debt_to_equity is not None and fd.debt_to_equity < 1.0:
        pts.append(ThesisPoint(
            "Balance Sheet & Durability",
            "Leverage is low enough to be optional",
            f"Debt-to-equity of {fd.debt_to_equity:.2f} means the balance sheet is not the binding "
            f"constraint. The company can fund itself through a downturn instead of refinancing into "
            f"one, and retains the option to lever up opportunistically.",
            "Debt/Equity", f"{fd.debt_to_equity:.2f}",
        ))
    if fd.free_cash_flow_ttm is not None and fd.free_cash_flow_ttm > 0 and fd.market_cap:
        fcf_yield = fd.free_cash_flow_ttm / fd.market_cap
        pts.append(ThesisPoint(
            "Balance Sheet & Durability",
            "The business self-funds from real cash flow",
            f"Trailing free cash flow of ${fd.free_cash_flow_ttm / 1e9:.1f}B is a {_pct(fcf_yield)} yield on "
            f"the current market cap. Cash generation at that level pays for buybacks, dividends and "
            f"reinvestment simultaneously rather than forcing a choice between them.",
            "FCF Yield", _pct(fcf_yield),
        ))

    # ── Momentum & Positioning ─────────────────────────────────────
    for s in t.signal_breakdown:
        if s["label"].startswith("MA Alignment") and s["score"] >= 70:
            pts.append(ThesisPoint(
                "Momentum & Positioning",
                "Moving averages are stacked bullishly",
                f"{s['detail']} Every timeframe of buyer is positioned above cost, which historically "
                f"removes the overhead supply that caps rallies.",
                "MA Structure", "Bullish stack",
            ))
        if s["label"] == "Bollinger %B" and s["score"] >= 70:
            pts.append(ThesisPoint(
                "Momentum & Positioning",
                "Price is stretched to the downside of its own range",
                f"{s['detail']} Against this asset's own volatility that is a statistically extended "
                f"reading, which is where mean-reversion entries have their best expectancy.",
                "Bollinger %B", "Lower band",
            ))
        if s["label"] == "RSI (14)" and s["score"] >= 70:
            pts.append(ThesisPoint(
                "Momentum & Positioning", "Momentum is washed out rather than extended",
                f"{s['detail']} Oversold momentum readings mark the point where forced selling is "
                f"typically closer to finished than starting.",
                "RSI (14)", f"{t.rsi_14:.0f}" if t.rsi_14 else "n/a",
            ))

    # ── Risk-Adjusted Performance ──────────────────────────────────
    if q.sharpe_ratio is not None and q.sharpe_ratio > 0.8:
        pts.append(ThesisPoint(
            "Risk-Adjusted Performance",
            "Returns have compensated for the risk taken",
            f"A Sharpe ratio of {q.sharpe_ratio:.2f} means past return has been earned per unit of "
            f"volatility rather than by simply holding a more volatile asset — the distinction between "
            f"skill-like and beta-like performance.",
            "Sharpe (1y)", f"{q.sharpe_ratio:.2f}",
        ))
    if q.alpha_vs_spy is not None and q.alpha_vs_spy > 0:
        pts.append(ThesisPoint(
            "Risk-Adjusted Performance",
            "Outperformance is not explained by market exposure alone",
            f"Rolling alpha versus SPY is {_pct(q.alpha_vs_spy, 2)}, meaning the return is not merely the market "
            f"move scaled by beta. Idiosyncratic performance is what a concentrated position is for.",
            "Alpha vs SPY", _pct(q.alpha_vs_spy, 2),
        ))

    return pts


# =====================================================================
# Bear case
# =====================================================================

def _bear_points(f: FundamentalScore, t: TechnicalScore, q: QuantitativeScore,
                 fd, horizon: Horizon) -> list[ThesisPoint]:
    pts: list[ThesisPoint] = []

    # ── Overstretched Valuation ────────────────────────────────────
    if fd.pe_ratio is not None and fd.pe_ratio > 30:
        pts.append(ThesisPoint(
            "Overstretched Valuation",
            "The multiple already discounts successful execution",
            f"At {fd.pe_ratio:.1f}x earnings, a large share of future growth is in today's price. That "
            f"leaves no cushion for a miss: the same earnings on a de-rated multiple is a loss even if "
            f"the business performs exactly as expected.",
            "P/E", f"{fd.pe_ratio:.1f}x",
        ))
    if f.dcf_detail and f.dcf_detail.margin_of_safety < -0.05:
        d = f.dcf_detail
        pts.append(ThesisPoint(
            "Overstretched Valuation",
            "Price sits above the model's intrinsic estimate",
            f"The DCF implies roughly ${d.intrinsic_value_per_share:.2f} against a ${d.current_price:.2f} "
            f"price — a {_pct(abs(d.margin_of_safety))} premium. Justifying it requires growth or margins "
            f"above what the model already assumes.",
            "DCF Premium", _pct(abs(d.margin_of_safety)),
        ))
    if fd.pb_ratio is not None and fd.pb_ratio > 8:
        pts.append(ThesisPoint(
            "Overstretched Valuation",
            "Very little of the price is backed by book value",
            f"A {fd.pb_ratio:.1f}x price-to-book means the valuation rests almost entirely on intangible "
            f"and future earnings power. Those are the first assumptions repriced when sentiment turns.",
            "P/B", f"{fd.pb_ratio:.1f}x",
        ))

    # ── Margin & Balance-Sheet Headwinds ───────────────────────────
    if fd.debt_to_equity is not None and fd.debt_to_equity > 1.5:
        pts.append(ThesisPoint(
            "Margin & Balance-Sheet Headwinds",
            "Leverage amplifies any operational disappointment",
            f"Debt-to-equity of {fd.debt_to_equity:.2f} means fixed obligations are large relative to the "
            f"equity cushion. Interest expense is not discretionary, so a revenue shortfall hits equity "
            f"holders geared rather than proportionally.",
            "Debt/Equity", f"{fd.debt_to_equity:.2f}",
        ))
    if fd.current_ratio is not None and fd.current_ratio < 1.0:
        pts.append(ThesisPoint(
            "Margin & Balance-Sheet Headwinds",
            "Near-term liabilities exceed near-term assets",
            f"A current ratio of {fd.current_ratio:.2f} means current liabilities are not fully covered by "
            f"current assets. That is survivable for a business with reliable cash generation, but it "
            f"removes the buffer if collections or credit conditions tighten.",
            "Current Ratio", f"{fd.current_ratio:.2f}",
        ))
    if fd.operating_margin is not None and fd.operating_margin < 0.10:
        pts.append(ThesisPoint(
            "Margin & Balance-Sheet Headwinds",
            "Thin operating margin leaves no absorption capacity",
            f"At {_pct(fd.operating_margin)}, a modest rise in input or labour costs consumes a large share "
            f"of operating profit. Margin at this level converts small cost shocks into large earnings moves.",
            "Operating Margin", _pct(fd.operating_margin),
        ))

    # ── Deteriorating Growth ───────────────────────────────────────
    if fd.revenue_growth_yoy is not None and fd.revenue_growth_yoy < 0.03:
        pts.append(ThesisPoint(
            "Deteriorating Growth",
            "Top-line growth has stalled",
            f"Revenue growth of {_pct(fd.revenue_growth_yoy)} is at or below likely inflation, meaning real "
            f"revenue is flat to shrinking. Without volume growth, earnings expansion has to come from "
            f"cost cuts, which is finite.",
            "Revenue Growth", _pct(fd.revenue_growth_yoy),
        ))

    # ── Technical Deterioration ────────────────────────────────────
    for s in t.signal_breakdown:
        if s["label"].startswith("MA Alignment") and s["score"] <= 30:
            pts.append(ThesisPoint(
                "Technical Deterioration",
                "Moving averages are stacked bearishly",
                f"{s['detail']} Each rally into those averages meets holders looking to exit at breakeven, "
                f"which is the mechanism that caps recoveries in a downtrend.",
                "MA Structure", "Bearish stack",
            ))
        if s["label"] == "MACD" and s["score"] <= 40:
            pts.append(ThesisPoint(
                "Technical Deterioration", "Trend momentum is rolling over",
                f"{s['detail']} Momentum turning before price is the usual sequence — it indicates the "
                f"marginal buyer is stepping back while the trend still looks intact.",
                "MACD", "Negative histogram",
            ))
        if s["label"] == "On-Balance Volume" and s["score"] <= 40:
            pts.append(ThesisPoint(
                "Technical Deterioration", "Volume is concentrated in down-days",
                f"{s['detail']} Distribution under the surface often precedes a visible breakdown, because "
                f"size exits into strength rather than announcing itself.",
                "OBV", "Falling",
            ))

    # ── Risk Profile ───────────────────────────────────────────────
    if q.sharpe_ratio is not None and q.sharpe_ratio < 0.3:
        pts.append(ThesisPoint(
            "Risk Profile",
            "Recent returns have not compensated for volatility",
            f"A Sharpe ratio of {q.sharpe_ratio:.2f} means holders absorbed meaningful volatility without "
            f"being paid for it. Capital committed here has been carrying risk it did not earn a return on.",
            "Sharpe (1y)", f"{q.sharpe_ratio:.2f}",
        ))
    if q.beta_vs_spy is not None and q.beta_vs_spy > 1.3:
        pts.append(ThesisPoint(
            "Risk Profile",
            "High beta magnifies any market drawdown",
            f"A beta of {q.beta_vs_spy:.2f} implies roughly {q.beta_vs_spy:.2f}x the market's move. In a broad selloff this "
            f"position is expected to fall considerably harder than the index, independent of company news.",
            "Beta", f"{q.beta_vs_spy:.2f}",
        ))
    if q.rolling_volatility_30d is not None and q.rolling_volatility_30d > 0.45:
        pts.append(ThesisPoint(
            "Risk Profile",
            "Realised volatility is elevated",
            f"30-day annualised volatility of {_pct(q.rolling_volatility_30d)} means wide swings are the base case. "
            f"Position sizing that ignores this converts an acceptable thesis into an unacceptable drawdown.",
            "30d Volatility", _pct(q.rolling_volatility_30d),
        ))

    return pts


# =====================================================================
# Assembly
# =====================================================================

def _order_and_trim(points: list[ThesisPoint], horizon: Horizon, limit: int = 6) -> list[ThesisPoint]:
    """Lead with the categories that matter for this horizon, then trim."""
    priority = _HORIZON_EMPHASIS.get(horizon, _HORIZON_EMPHASIS["medium_term"])

    def rank(p: ThesisPoint) -> int:
        for i, cat in enumerate(priority):
            if p.category.startswith(cat.split(" &")[0]):
                return i
        return len(priority)

    return sorted(points, key=rank)[:limit]


def _falsifiers(stance: str, f: FundamentalScore, t: TechnicalScore, q: QuantitativeScore, fd) -> list[str]:
    out: list[str] = []
    if stance == "bull":
        if fd.revenue_growth_yoy is not None:
            out.append(f"Revenue growth decelerating below {_pct(max(0.0, fd.revenue_growth_yoy - 0.05))} "
                       f"would undercut the compounding argument.")
        if fd.gross_margin is not None:
            out.append(f"Gross margin compressing more than 300bps from {_pct(fd.gross_margin)} would signal "
                       f"the pricing power is not durable.")
        if t.rsi_14 is not None:
            out.append("A close below the 200-day moving average would invalidate the trend-structure case "
                       "regardless of the fundamentals.")
    else:
        if fd.pe_ratio is not None:
            out.append(f"Earnings growing into the {fd.pe_ratio:.1f}x multiple — rather than the multiple "
                       f"de-rating — would defuse the valuation objection.")
        if fd.operating_margin is not None:
            out.append(f"Operating margin expanding from {_pct(fd.operating_margin)} would remove the "
                       f"cost-absorption concern.")
        out.append("A reclaim of the 50-day moving average on expanding volume would break the technical "
                   "deterioration argument.")
    return out[:3]


def _summary(stance: str, ticker: str, points: list[ThesisPoint], horizon: Horizon) -> str:
    label = {"short_term": "the next few weeks", "medium_term": "the next one to six months",
             "long_term": "a multi-year horizon"}[horizon]
    if not points:
        return (f"There is not enough computed data to construct a defensible "
                f"{'bull' if stance == 'bull' else 'bear'} case for {ticker} over {label}. "
                f"Rather than pad this with generic assertions, it is left empty — see the data "
                f"completeness figures above for which inputs are missing.")
    cats = list(dict.fromkeys(p.category for p in points))
    joined = ", ".join(cats[:-1]) + (" and " + cats[-1] if len(cats) > 1 else cats[0])
    direction = "supports" if stance == "bull" else "argues against"
    return (f"Over {label}, the evidence that {direction} {ticker} rests on {joined}. "
            f"Each point below is derived from a metric that actually computed for this ticker; "
            f"nothing is asserted without a number behind it.")


def build_theses(ticker: str, horizon: Horizon,
                 fundamental: FundamentalScore, technical: TechnicalScore,
                 quantitative: QuantitativeScore, fundamental_data) -> tuple[Thesis, Thesis]:
    """Build the bull and bear cases. Always returns both, never raises."""
    bull_pts = _order_and_trim(_bull_points(fundamental, technical, quantitative, fundamental_data, horizon), horizon)
    bear_pts = _order_and_trim(_bear_points(fundamental, technical, quantitative, fundamental_data, horizon), horizon)

    bull = Thesis("bull", _summary("bull", ticker, bull_pts, horizon), bull_pts,
                  _falsifiers("bull", fundamental, technical, quantitative, fundamental_data))
    bear = Thesis("bear", _summary("bear", ticker, bear_pts, horizon), bear_pts,
                  _falsifiers("bear", fundamental, technical, quantitative, fundamental_data))

    return _with_cached_polish(ticker, horizon, bull, bear)


# ── Non-blocking polish ──────────────────────────────────────────────────
# A local 3B model takes ~20s per case on CPU, so polishing inline would put
# ~40s onto every analysis request and re-break the latency work. Instead:
#
#   request 1  -> return deterministic immediately, polish in a background
#                 thread, write the result to Redis
#   request 2+ -> serve the cached polished version instantly
#
# The user never waits on the model, and the cache means the cost is paid
# once per ticker/horizon rather than per page load. If the model is slow,
# broken, or absent, every request simply keeps the deterministic text —
# which is complete and shippable on its own.

_POLISH_CACHE_TTL = 60 * 60 * 12   # theses move slowly; half a day is plenty


def _cache_key(ticker: str, horizon: str, stance: str) -> str:
    return f"thesis_polished:{ticker}:{horizon}:{stance}"


def _with_cached_polish(ticker: str, horizon: Horizon,
                        bull: Thesis, bear: Thesis) -> tuple[Thesis, Thesis]:
    import json as _json

    from app.analysis.llm_provider import available_backend

    if available_backend() == "none":
        return bull, bear

    try:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
    except Exception:
        return bull, bear

    out: list[Thesis] = []
    missing: list[Thesis] = []
    for th in (bull, bear):
        try:
            raw = redis.get(_cache_key(ticker, horizon, th.stance))
        except Exception:
            raw = None
        if raw:
            details = _json.loads(raw)
            if isinstance(details, list) and len(details) == len(th.points):
                for p, d in zip(th.points, details):
                    p.detail = d
                th.source = "llm_polished"
                out.append(th)
                continue
        missing.append(th)
        out.append(th)

    if missing:
        _spawn_background_polish(ticker, horizon, missing)
    return out[0], out[1]


def _spawn_background_polish(ticker: str, horizon: Horizon, theses: list[Thesis]) -> None:
    """Fire-and-forget: polish off the request path and cache the result."""
    import json as _json
    import threading

    def _work() -> None:
        try:
            from app.core.redis_client import get_redis_client
            redis = get_redis_client()
            for th in theses:
                polished = _polish(th, ticker, horizon)
                if polished:
                    redis.setex(
                        _cache_key(ticker, horizon, th.stance),
                        _POLISH_CACHE_TTL,
                        _json.dumps([p.detail for p in polished.points]),
                    )
                    logger.info("Thesis polished and cached",
                                extra={"ticker": ticker, "stance": th.stance})
        except Exception as exc:
            logger.warning("Background thesis polish failed",
                           extra={"ticker": ticker, "error": str(exc)})

    threading.Thread(target=_work, daemon=True, name=f"polish-{ticker}").start()


_POLISH_TEMPLATE = """Rewrite each bullet's DETAIL text below into tighter, more fluent institutional prose.

ABSOLUTE CONSTRAINTS:
- Preserve every number exactly. Do not round differently, drop, or add any figure.
- Do not add any claim, driver, or fact that is not already present.
- Do not change the headline or the category of any point.
- Do NOT restate the category or headline inside the detail text — both are
  already displayed above it, so repeating them reads as duplication.
- Preserve the MEANING precisely. Do not re-attribute a figure to a
  different concept than the original assigned it to.
- Keep each detail to at most three sentences.
- Return JSON only: {{"details": ["...", "..."]}} with exactly {n} entries, in order.

POINTS:
{payload}"""


def _strip_redundant_prefix(detail: str, point: ThesisPoint) -> str:
    """
    Remove a leading "Category:" or "Headline:" echo from model output.

    Small local models reliably ignore a negative instruction like "do not
    restate the category", so the prompt alone doesn't prevent this — and the
    UI already renders both above the detail, so the echo reads as
    duplication. Stripping it deterministically is more dependable than
    asking a 3B model to comply.
    """
    cleaned = detail.strip()
    for prefix in (point.category, point.headline):
        for sep in (":", " -", " —"):
            probe = f"{prefix}{sep}"
            if cleaned.lower().startswith(probe.lower()):
                cleaned = cleaned[len(probe):].lstrip()
                # Re-capitalise so the sentence still reads correctly.
                if cleaned and cleaned[0].islower():
                    cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _polish(thesis: Thesis, ticker: str, horizon: Horizon) -> Thesis | None:
    """
    Optional LLM rewrite of the prose only, through whichever backend is
    available (Ollama first — free and local — then OpenAI, then Anthropic).

    The model never sees a blank page: it receives finished, metric-backed
    bullets and may only restate them. Output is validated by the shared
    guardrails, and any failure at all falls back to the deterministic text,
    which is already complete and shippable.
    """
    from app.agents.guardrails import CORE_ORCHESTRATOR_SYSTEM_PROMPT, validate_llm_output
    from app.analysis.llm_provider import complete_json

    if not thesis.points:
        return None

    payload = "\n".join(f"{i + 1}. [{p.category}] {p.headline}: {p.detail}"
                        for i, p in enumerate(thesis.points))
    data = complete_json(
        CORE_ORCHESTRATOR_SYSTEM_PROMPT,
        _POLISH_TEMPLATE.format(n=len(thesis.points), payload=payload),
        max_tokens=800,
    )
    if not data:
        return None

    details = data.get("details")
    if not isinstance(details, list) or len(details) != len(thesis.points):
        return None
    if not all(isinstance(d, str) and d.strip() for d in details):
        return None

    if not validate_llm_output(" ".join(details)).is_clean:
        logger.warning("Thesis polish failed guardrails — keeping deterministic text",
                       extra={"ticker": ticker, "stance": thesis.stance})
        return None

    for p, new_detail in zip(thesis.points, details):
        p.detail = _strip_redundant_prefix(new_detail, p)
    thesis.source = "llm_polished"
    return thesis
