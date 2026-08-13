"""
app/lessons/tier3_advanced.py
-------------------------------
TIER 3 — "Advanced"

Assumes Foundational+ and Intermediate are absorbed. Factor mechanics,
options greeks interactions, correlation regime behaviour, fixed-income
convexity, and market microstructure detail.

Originally numbered tier 1; renumbered to 3 when the beginner and
intermediate tiers were added. Quizzes live in quizzes.py.
"""

from app.lessons.models import Lesson, TIER_ADVANCED

TIER_3_ADVANCED: list[Lesson] = [

    Lesson("a001", "Factor Investing: What 'Value' and 'Quality' Actually Measure", "Quantitative", TIER_ADVANCED,
        "Academic factor models decompose stock returns into exposures to systematic factors — market, "
        "size, value, momentum, quality, low-volatility — each with a documented long-run premium and a "
        "behavioral or risk-based explanation. 'Value' is typically measured by book-to-market or "
        "earnings yield; 'quality' by profitability, earnings stability, and low leverage.\n\n"
        "The critical nuance most retail discussion misses: factor premiums are NOT constant. They go "
        "through extended drawdowns of their own — value underperformed growth for over a decade "
        "(2007-2020) before a sharp reversal. A factor 'not working' for years doesn't mean the premium "
        "is gone; factor cyclicality is itself a well-documented, expected property of factor investing, "
        "not evidence the factor is broken.",
        "Factor premiums are real but cyclical — a decade of underperformance doesn't necessarily mean a factor has stopped working."),
    Lesson("a002", "Options Greeks Beyond Delta: Gamma, Theta, and Vega Interactions", "Derivatives", TIER_ADVANCED,
        "Delta gets the most attention (directional exposure), but gamma — the rate of change of delta — "
        "determines how your directional exposure itself changes as the stock moves, which is why "
        "short-gamma positions (short options) can experience accelerating losses as a move extends, "
        "while long-gamma positions accelerate gains.\n\n"
        "Theta (time decay) and vega (volatility sensitivity) interact non-linearly near expiration: an "
        "at-the-money option close to expiry has enormous gamma and theta simultaneously, meaning small "
        "price moves cause large P&L swings while time decay accelerates — the combination is why "
        "professional options traders describe short-dated ATM options as the highest-risk, "
        "highest-convexity instrument in the standard options toolkit.",
        "Gamma determines how fast your directional exposure changes — high-gamma positions near expiration can swing violently on small price moves."),
    Lesson("a003", "Correlation Isn't Fixed: Why Diversification Fails Exactly When You Need It", "Portfolio Theory", TIER_ADVANCED,
        "Historical correlation matrices used in portfolio construction are backward-looking averages, "
        "but correlations between assets — especially equities — are regime-dependent and tend to spike "
        "toward 1.0 during systemic stress events (2008, March 2020), precisely when diversification "
        "benefits matter most.\n\n"
        "This is sometimes called 'correlation breakdown' or the tendency for 'all correlations go to "
        "one' in a crisis, driven by forced deleveraging and liquidity-seeking selling that hits "
        "otherwise-uncorrelated assets simultaneously. Risk models built purely on historical average "
        "correlations systematically understate tail risk for exactly this reason.",
        "Correlations that look protective in calm markets often compress toward 1 during genuine crises — diversification is weakest exactly when it's needed most."),
    Lesson("a004", "Duration and Convexity: Why Bond Price Sensitivity Isn't Linear", "Fixed Income", TIER_ADVANCED,
        "Duration approximates a bond's price sensitivity to interest rate changes — a duration of 7 "
        "means roughly a 7% price move for a 1% rate change. But this relationship is a linear "
        "approximation of what's actually a convex (curved) relationship, meaning duration alone "
        "overstates losses when rates rise and understates gains when rates fall.\n\n"
        "Convexity captures this curvature. It matters most for long-duration bonds and becomes "
        "critical in large rate moves, where duration-only estimates can be meaningfully wrong. This is "
        "also why callable bonds exhibit 'negative convexity' near their call price — issuers redeem "
        "them exactly when it's least favorable to the bondholder.",
        "Duration is a linear approximation of a curved relationship — convexity corrects it, and the gap matters most during large rate moves."),
    Lesson("a005", "Market Microstructure: How Payment for Order Flow Actually Works", "Market Mechanics", TIER_ADVANCED,
        "When a retail broker routes your order to a market maker instead of directly to an exchange, "
        "the market maker typically pays the broker for that order flow (PFOF) and profits from the "
        "bid-ask spread by filling your order internally rather than on a public exchange.\n\n"
        "The real debate isn't whether PFOF exists but whether execution quality — price improvement "
        "versus the National Best Bid and Offer — genuinely offsets the conflict of interest. Studies "
        "have found retail orders often DO get modest price improvement versus quoted spreads, but "
        "market makers still profit from the flow's predictable, generally uninformed nature, which is "
        "structurally different from institutional order flow.",
        "PFOF-routed orders often get measurable price improvement, but that doesn't eliminate the underlying conflict of interest in how your order gets routed."),
    Lesson("a006", "Why Backtested Sharpe Ratios Are Almost Always Overstated", "Quantitative", TIER_ADVANCED,
        "A backtest's Sharpe ratio reflects one realized historical path, not the true underlying "
        "distribution of outcomes — and strategy development inherently involves iterating parameters "
        "until performance looks good on that specific historical sample, whether or not the researcher "
        "intends to overfit.\n\n"
        "The deflated Sharpe ratio framework explicitly corrects for the number of trials run during "
        "strategy development: testing 100 parameter combinations and reporting only the best one "
        "produces a Sharpe ratio statistically expected to be inflated even with zero true skill, purely "
        "from multiple-comparisons selection bias.",
        "The more parameter combinations tested during strategy development, the more a backtest's best result is expected to be inflated by pure chance — regardless of true skill."),
    Lesson("a007", "Credit Spreads as a Leading Economic Indicator", "Macro", TIER_ADVANCED,
        "The spread between corporate bond yields and equivalent-maturity Treasuries compensates "
        "investors for default risk, and it widens well before equity markets typically price in "
        "economic deterioration — credit markets often lead equity markets at cyclical turning points "
        "because bondholders are structurally more sensitive to downside risk than equity holders.\n\n"
        "High-yield spreads specifically are watched closely because speculative-grade issuers are most "
        "exposed to tightening financial conditions and slowing growth. A sustained, broad widening in "
        "high-yield spreads — distinct from single-issuer stress — has historically been one of the more "
        "reliable early-warning signals available across public markets.",
        "Credit spread widening often leads equity market weakness because bondholders are structurally more sensitive to downside risk than equity holders."),
    Lesson("a008", "The Mechanics of a Short Squeeze, Precisely", "Market Mechanics", TIER_ADVANCED,
        "A short squeeze requires three conditions simultaneously: high short interest relative to "
        "float, a genuine upward price catalyst, and a limited pool of shares available to borrow, which "
        "forces some short sellers to buy back shares (covering) at rising prices rather than waiting it "
        "out — that forced buying is what distinguishes a squeeze from an ordinary rally.\n\n"
        "'Days to cover' (short interest divided by average daily volume) approximates how long an "
        "orderly unwind would take — a high days-to-cover ratio combined with a sudden volume and price "
        "spike is the classic squeeze signature, because it signals shorts literally cannot exit in size "
        "without moving the price further against themselves.",
        "A genuine squeeze needs high short interest AND limited borrow supply AND a real catalyst simultaneously — any one alone just produces an ordinary price move."),
]
