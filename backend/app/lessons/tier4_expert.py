"""
app/lessons/tier4_expert.py
-----------------------------
TIER 4 — "Expert"

Genuinely institutional-grade. Risk model internals, factor crowding and
unwind dynamics, execution theory, volatility term structure, and the
places where standard models structurally fail rather than merely
lose accuracy.

Originally numbered tier 2; renumbered to 4 when the beginner and
intermediate tiers were added. Quizzes live in quizzes.py.
"""

from app.lessons.models import Lesson, TIER_EXPERT

TIER_4_EXPERT: list[Lesson] = [

    Lesson("e001", "Value-at-Risk vs. Conditional VaR: Why VaR Underestimates Tail Risk", "Risk", TIER_EXPERT,
        "Value-at-Risk (VaR) reports a threshold loss at a given confidence level (e.g., '95% VaR of $1M' "
        "means a 5% chance of losing more than $1M over the period), but VaR says nothing about HOW MUCH "
        "more you could lose in that tail 5% of outcomes, which is precisely the scenario that matters "
        "most for solvency.\n\n"
        "Conditional VaR (CVaR, also called Expected Shortfall) addresses this by reporting the average "
        "loss GIVEN that you're already in the tail beyond the VaR threshold: a materially more "
        "conservative and informative risk measure. Basel III's post-2008 shift toward Expected Shortfall "
        "for regulatory capital requirements was a direct response to VaR's tail-blindness during the "
        "financial crisis.",
        "VaR tells you the threshold of a bad outcome; CVaR tells you how bad the bad outcomes actually average out to be, and that's the number that matters for solvency."),
    Lesson("e002", "Factor Crowding and the Mechanics of a Quant Unwind", "Quantitative", TIER_EXPERT,
        "When many systematic strategies independently converge on similar factor exposures (a "
        "'crowded trade'), the strategies become correlated with each other in ways their individual "
        "backtests never captured, because no single fund's historical data includes the behavior of "
        "every OTHER fund holding the same positions simultaneously.\n\n"
        "The August 2007 'quant quake' is the canonical case study: several large quant funds, running "
        "ostensibly different strategies, had converged on overlapping factor exposures. When one fund "
        "was forced to deleverage, its selling pressured prices in ways that triggered stop-losses and "
        "margin calls at other funds with correlated exposures, creating a self-reinforcing unwind across "
        "funds that had no direct relationship to each other: a liquidity spiral driven purely by "
        "position overlap, not by any change in fundamentals.",
        "Crowded factor trades create correlation between otherwise-unrelated funds that only becomes visible during a forced unwind: a risk no individual fund's backtest can see."),
    Lesson("e003", "Volatility Term Structure and the Economics of the VIX Futures Curve", "Derivatives", TIER_EXPERT,
        "The VIX itself is a spot measure of 30-day implied volatility; VIX futures reference expectations "
        "of where that measure will be at future dates, and the curve connecting them typically slopes "
        "upward (contango) in calm markets: reflecting a persistent risk premium investors demand to "
        "sell volatility protection, and inverts sharply into backwardation during acute stress.\n\n"
        "This term structure is why volatility-linked ETPs that roll futures contracts systematically "
        "bleed value in contango regimes: they're perpetually selling a cheaper near-dated contract and "
        "buying a more expensive longer-dated one, a structural cost embedded in the product's mechanics "
        "independent of whether volatility itself rises or falls.",
        "Long volatility products decay in contango markets because of the structural cost of rolling futures, not because volatility failed to rise."),
    Lesson("e004", "Execution and Market Impact: The Almgren-Chriss Framework, Intuitively", "Market Mechanics", TIER_EXPERT,
        "Large institutional orders face a fundamental tradeoff: execute fast and pay more market impact "
        "(moving the price against yourself as you consume liquidity), or execute slowly and reduce impact "
        "but accept more exposure to adverse price drift and volatility risk over the longer execution "
        "window.\n\n"
        "The Almgren-Chriss framework formalizes this as an optimization problem, balancing expected "
        "market impact cost against the variance of execution price risk, producing an optimal trading "
        "trajectory rather than either extreme. This is the theoretical basis for VWAP and "
        "implementation-shortfall algorithms used throughout institutional execution desks: the choice "
        "of execution speed is itself a risk decision, not just a cost-minimization one.",
        "Fast execution minimizes timing risk but maximizes market impact cost; slow execution does the reverse: optimal execution balances both, it doesn't eliminate either."),
    Lesson("e005", "Why Tail Risk Hedges Have a Structurally Negative Expected Return", "Risk", TIER_EXPERT,
        "Buying out-of-the-money put protection as portfolio insurance has, over most historical periods, "
        "a negative expected return by design: insurance sellers price in a risk premium, and realized "
        "crash frequency has historically been lower than what implied volatility priced in during "
        "calm periods, meaning systematic tail hedging bleeds value most of the time.\n\n"
        "The honest framing institutional allocators use: tail hedges aren't return-generating positions, "
        "they're a cost paid for a specific payoff structure (convexity during a crash) that changes the "
        "SHAPE of portfolio returns, not the average. Evaluating a tail-hedge program on its standalone "
        "P&L misses the point: the relevant metric is the whole portfolio's behavior during the tail "
        "event the hedge exists to address.",
        "Tail hedges are expected to lose money most of the time by design: their value is in the shape of outcomes during a crash, not standalone P&L."),
    Lesson("e006", "Liquidity Risk Premia and the Illiquidity Discount in Private Markets", "Portfolio Theory", TIER_EXPERT,
        "Assets that can't be traded on demand command a return premium versus otherwise-comparable "
        "liquid assets: this illiquidity premium compensates investors for the inability to rebalance "
        "or exit during stress, and it's a documented, persistent feature across private equity, real "
        "estate, and other locked-capital structures.\n\n"
        "The measurement challenge is that private-market valuations are typically appraisal-based and "
        "update infrequently, which artificially smooths reported volatility and correlation to public "
        "markets: a well-documented statistical artifact sometimes called 'volatility laundering' that "
        "makes private assets look less risky and less correlated than they actually are on a "
        "mark-to-market basis.",
        "Private-market assets often look less volatile and less correlated to stocks than they really are: that's largely a reporting artifact of infrequent appraisal-based valuation, not lower true risk."),
    Lesson("e007", "Reflexivity: When Price Action Changes the Fundamentals It's Supposed to Reflect", "Behavioral", TIER_EXPERT,
        "Standard theory treats price as a reflection of fundamentals. George Soros's reflexivity thesis "
        "describes cases where the causality runs the other direction too: rising prices can themselves "
        "improve a company's actual fundamentals (cheaper capital raises, easier acquisitions using stock "
        "as currency, improved credit terms), creating a genuine feedback loop rather than a pure "
        "sentiment bubble disconnected from reality.\n\n"
        "This matters for distinguishing 'irrational bubble' narratives from cases where a rising stock "
        "price is mechanically improving the underlying business's actual competitive position: the two "
        "can look identical in the price chart but have very different implications for how the cycle "
        "eventually resolves.",
        "Rising prices can sometimes genuinely improve a company's fundamentals (cheaper capital, stock-funded M&A), not just reflect sentiment disconnected from reality: the two are hard to distinguish in real time."),
]
