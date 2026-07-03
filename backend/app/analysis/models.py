"""
app/analysis/models.py
----------------------
Canonical output schemas for every analysis module.
Using dataclasses with __post_init__ validation instead of Pydantic here
because analysis results are purely internal — they get serialised to
Pydantic models only at the API boundary (api/v1/analysis.py).
This keeps the analysis layer dependency-free from FastAPI/Pydantic.
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


# ── Fundamental ────────────────────────────────────────────────────────────────

@dataclass
class DCFResult:
    intrinsic_value_per_share: float
    current_price: float
    margin_of_safety: float          # (intrinsic - price) / intrinsic
    discount_rate: float             # WACC approximation used
    terminal_growth_rate: float
    near_term_growth_rate: float
    projection_years: int

@dataclass
class FundamentalScore:
    ticker: str
    score: float                     # 0–100
    dcf_signal: float                # 0–100 sub-score
    safety_score: float              # 0–100 (balance-sheet health)
    growth_score: float              # 0–100 (revenue/earnings growth)
    moat_score: float                # 0–100 (ROE, gross margin, consistency)
    dcf_detail: DCFResult | None
    # Raw values for display
    pe_ratio: float | None
    debt_to_equity: float | None
    gross_margin: float | None
    roe: float | None
    free_cash_flow: float | None
    analysis_notes: list[str] = field(default_factory=list)


# ── Technical ──────────────────────────────────────────────────────────────────

@dataclass
class SupportResistanceLevel:
    price: float
    level_type: Literal["support", "resistance"]
    strength: float                  # number of touches/confirmation count

@dataclass
class TechnicalScore:
    ticker: str
    score: float                     # 0–100
    rsi_score: float                 # 0–100 sub-score
    macd_score: float                # 0–100
    sr_score: float                  # 0–100 (support/resistance positioning)
    volume_score: float              # 0–100
    # Raw indicator values
    rsi_14: float | None
    macd_histogram: float | None
    macd_line: float | None
    signal_line: float | None
    current_price: float | None
    support_levels: list[SupportResistanceLevel] = field(default_factory=list)
    resistance_levels: list[SupportResistanceLevel] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)


# ── Quantitative ───────────────────────────────────────────────────────────────

@dataclass
class QuantitativeScore:
    ticker: str
    score: float                     # 0–100
    volatility_score: float          # 0–100 (lower vol = higher score)
    alpha_score: float               # 0–100 (positive alpha vs SPY)
    momentum_score: float            # 0–100 (medium-term price momentum)
    ml_signal_score: float           # 0–100 (ridge regression signal)
    # Raw metrics
    rolling_volatility_30d: float | None   # annualised
    beta_vs_spy: float | None
    alpha_vs_spy: float | None             # annualised
    sharpe_ratio: float | None
    momentum_12_1: float | None            # 12-month minus 1-month return
    analysis_notes: list[str] = field(default_factory=list)


# ── Ensemble ───────────────────────────────────────────────────────────────────

@dataclass
class EnsembleSignal:
    """
    The unified output surfaced to the user.
    confidence_index is on a [0, 100] scale; it is NOT a probability
    (explicitly to avoid implying any specific mathematical certainty).
    """
    ticker: str
    time_horizon: str
    signal: Literal["BUY", "HOLD", "SELL"]
    signal_strength: Literal["STRONG", "MODERATE", "WEAK"]
    confidence_index: float           # 0–100
    # Module scores
    fundamental_score: float
    technical_score: float
    quantitative_score: float
    # Full breakdowns
    fundamental: FundamentalScore
    technical: TechnicalScore
    quantitative: QuantitativeScore
    # Provenance
    market_data_provider: str
    fundamental_data_provider: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    disclaimer: str = field(default=DISCLAIMER)
    uncertainty_note: str = field(
        default=(
            "Confidence index represents a weighted composite of model scores. "
            "It is a heuristic measure, not a calibrated probability estimate. "
            "Reasonable uncertainty bands are ±20 points."
        )
    )
