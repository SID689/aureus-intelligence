"""
app/analysis/models.py  (Phase 6 — adds data_completeness + reasoning fields)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

DISCLAIMER = (
    "Aureus Intelligence provides software-generated informational analysis only. "
    "Nothing presented constitutes investment, legal, or tax advice, nor a "
    "recommendation to buy, hold, or sell any security. Past performance is not "
    "indicative of future results. All probabilistic outputs carry inherent "
    "uncertainty and should not be interpreted as guarantees of any outcome."
)


@dataclass
class DCFResult:
    intrinsic_value_per_share: float
    current_price: float
    margin_of_safety: float
    discount_rate: float
    terminal_growth_rate: float
    near_term_growth_rate: float
    projection_years: int


@dataclass
class FundamentalScore:
    ticker: str
    score: float
    dcf_signal: float
    safety_score: float
    growth_score: float
    moat_score: float
    dcf_detail: DCFResult | None
    pe_ratio: float | None
    debt_to_equity: float | None
    gross_margin: float | None
    roe: float | None
    free_cash_flow: float | None
    # Surfaced for the metrics grid and thesis badges. Optional with defaults so
    # existing constructor call sites stay valid.
    pb_ratio: float | None = None
    operating_margin: float | None = None
    revenue_growth_yoy: float | None = None
    current_ratio: float | None = None
    market_cap: float | None = None
    ev_to_ebitda: float | None = None
    price_to_sales: float | None = None
    fcf_yield: float | None = None
    roic: float | None = None
    interest_coverage: float | None = None
    data_completeness: float = 1.0          # NEW: 0-1, how much of this module was backed by real data
    effective_weights: dict = field(default_factory=dict)  # NEW: which sub-signals actually contributed
    # NEW (issue: "reasoning should mention specific things"): each computed
    # sub-signal reports itself here as {label, score, detail, direction},
    # so reasoning.py can point to the SPECIFIC line items driving the
    # score up or down, rather than only the composite number.
    signal_breakdown: list[dict] = field(default_factory=list)
    # NEW: explicit, specific diagnosis of why DCF didn't run — distinguishes
    # "the data provider never returned this figure" from "the company's FCF
    # is genuinely negative" (a real, informative fact, not a data gap).
    dcf_skip_reason: str | None = None
    fundamental_data_provider: str = "unavailable"
    analysis_notes: list[str] = field(default_factory=list)


@dataclass
class SupportResistanceLevel:
    price: float
    level_type: Literal["support", "resistance"]
    strength: float


@dataclass
class TechnicalScore:
    ticker: str
    score: float
    rsi_score: float
    macd_score: float
    sr_score: float
    volume_score: float
    rsi_14: float | None
    macd_histogram: float | None
    macd_line: float | None
    signal_line: float | None
    current_price: float | None
    data_completeness: float = 1.0
    effective_weights: dict = field(default_factory=dict)
    signal_breakdown: list[dict] = field(default_factory=list)
    support_levels: list[SupportResistanceLevel] = field(default_factory=list)
    resistance_levels: list[SupportResistanceLevel] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)


@dataclass
class QuantitativeScore:
    ticker: str
    score: float
    volatility_score: float
    alpha_score: float
    momentum_score: float
    ml_signal_score: float
    rolling_volatility_30d: float | None
    beta_vs_spy: float | None
    alpha_vs_spy: float | None
    sharpe_ratio: float | None
    momentum_12_1: float | None
    data_completeness: float = 1.0
    effective_weights: dict = field(default_factory=dict)
    signal_breakdown: list[dict] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)


@dataclass
class EnsembleSignal:
    ticker: str
    time_horizon: str
    signal: Literal["BUY", "HOLD", "SELL"]
    signal_strength: Literal["STRONG", "MODERATE", "WEAK"]
    confidence_index: float
    fundamental_score: float
    technical_score: float
    quantitative_score: float
    fundamental: FundamentalScore
    technical: TechnicalScore
    quantitative: QuantitativeScore
    market_data_provider: str
    fundamental_data_provider: str
    # NEW fields — this is the direct fix for "scores need explanations"
    reasoning: str = ""                      # human-readable explanation of the score
    reasoning_source: str = "deterministic"  # "deterministic" | "llm_polished"
    sector: str | None = None
    sector_comparison: dict = field(default_factory=dict)  # see analysis/sector_peers.py
    bull_case: dict = field(default_factory=dict)   # see analysis/thesis.py
    bear_case: dict = field(default_factory=dict)
    overall_data_completeness: float = 1.0   # 0-1 across all three modules
    module_weights_used: dict = field(default_factory=dict)  # actual top-level weights after reweighting
    generated_at: datetime = field(default_factory=datetime.utcnow)
    disclaimer: str = field(default=DISCLAIMER)
    uncertainty_note: str = field(
        default=(
            "Confidence index represents a weighted composite of model scores. "
            "It is a heuristic measure, not a calibrated probability estimate. "
            "Reasonable uncertainty bands are ±20 points."
        )
    )
