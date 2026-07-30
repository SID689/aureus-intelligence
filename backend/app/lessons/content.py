"""
app/lessons/content.py
-------------------------
The lesson bank, organized into three difficulty tiers so content gets
genuinely more advanced as a user progresses — not just more of the same
level repeated. All three tiers assume basic trading familiarity as the
floor (never "what is a stock").

Tier 0 (Foundational+): one level past basics — assumes they've placed
  trades and know common terms, goes one layer deeper on mechanism/why.
Tier 1 (Advanced): assumes tier 0 has been absorbed — factor mechanics,
  options greeks, correlation math, market microstructure detail.
Tier 2 (Expert): genuinely institutional-grade — risk model internals,
  crowding/unwind dynamics, execution and tail-risk topics.

Lessons rotate deterministically by day-of-year within whichever tier
the user is currently at, so everyone at the same tier sees the same
lesson on the same calendar day.
"""

from dataclasses import dataclass


@dataclass
class Lesson:
    id: str
    title: str
    category: str
    tier: int             # 0, 1, or 2
    body: str
    key_takeaway: str


TIER_LABELS = {0: "Foundational+", 1: "Advanced", 2: "Expert"}


# ── Tier 0: Foundational+ ──────────────────────────────────────────────────
_TIER_0: list[Lesson] = [
    Lesson("l001", "Why P/E Ratios Lie to You Across Sectors", "Valuation", 0,
        "A price-to-earnings ratio only means something relative to a peer group with similar "
        "capital structure and growth dynamics. A software company trading at 35x earnings and a "
        "regional bank trading at 9x aren't telling you the bank is 'cheaper' — they're telling you "
        "the market expects very different growth trajectories and has very different views on the "
        "durability of each business's earnings.\n\n"
        "The deeper issue: P/E uses trailing or forward earnings, and earnings are an accounting "
        "construct that management has real discretion over — depreciation schedules, revenue "
        "recognition timing, one-time charges. Two companies with identical cash economics can report "
        "meaningfully different earnings depending on accounting choices. That's part of why "
        "professional analysts lean on free cash flow alongside earnings — cash is harder to shape "
        "than reported profit.",
        "A P/E ratio is only informative when compared within a sector, and even then it should be triangulated against cash flow, not read alone."),
    Lesson("l002", "What Beta Actually Measures (and Doesn't)", "Risk", 0,
        "Beta measures how a stock's returns have historically moved relative to a benchmark — a beta "
        "of 1.5 means the stock has tended to move 50% more than the market in either direction. "
        "It's a measure of historical co-movement, not a measure of quality, safety, or future risk.\n\n"
        "The common mistake: treating low beta as synonymous with 'safe.' A low-beta stock can still "
        "carry enormous company-specific risk (fraud, a failed product, a lawsuit) that has nothing to "
        "do with market correlation. Beta captures systematic risk — the risk you can't diversify away "
        "by holding many stocks — but says nothing about idiosyncratic risk specific to that one company.",
        "Beta tells you how correlated a stock is to the market, not how risky the underlying business is."),
    Lesson("l003", "The Difference Between Volume and Liquidity", "Market Mechanics", 0,
        "Daily trading volume and liquidity sound similar but answer different questions. Volume tells "
        "you how many shares changed hands. Liquidity tells you how much you could trade RIGHT NOW "
        "without moving the price against yourself — which depends on order book depth, not just "
        "yesterday's volume total.\n\n"
        "A stock can show healthy average volume while having thin liquidity at any given moment if "
        "that volume is concentrated in a few large block trades rather than continuous two-sided "
        "flow. This matters most when position sizing: a $50,000 order in a stock with $2M average "
        "daily volume might move the price meaningfully more than the same order in a stock with "
        "identical average volume but tighter bid-ask spreads and deeper resting orders.",
        "High average volume doesn't guarantee you can exit a large position without moving the price — check the bid-ask spread and order book depth too."),
    Lesson("l004", "Why Diversification Stops Helping After ~20-30 Stocks", "Portfolio Theory", 0,
        "The classic diversification benefit — reducing risk without sacrificing expected return — "
        "comes almost entirely from eliminating company-specific risk. Each additional holding you add "
        "reduces idiosyncratic risk, but with steeply diminishing returns. Academic estimates generally "
        "put the bulk of the benefit captured by around 20-30 well-chosen, uncorrelated positions.\n\n"
        "Beyond that point, you're mostly just approximating an index fund with extra transaction costs "
        "and monitoring overhead, while the risk that remains — market-wide systematic risk — can't be "
        "diversified away by adding more individual stocks at all. That risk only comes down through "
        "asset allocation (bonds, cash, uncorrelated asset classes), not through owning more stocks.",
        "Adding your 50th holding barely reduces risk versus your 25th — company-specific risk diversifies away fast, market risk never does."),
    Lesson("l005", "Reading a Cash Flow Statement in Three Lines", "Valuation", 0,
        "The cash flow statement has three sections, and the relationship between them tells a story "
        "the income statement can hide. Operating cash flow (cash generated by the core business), "
        "investing cash flow (cash spent on or received from long-term assets), and financing cash "
        "flow (cash raised from or returned to lenders and shareholders).\n\n"
        "A healthy, mature company typically shows positive operating cash flow, negative investing "
        "cash flow (reinvesting in the business), and negative financing cash flow (paying down debt "
        "or returning capital via buybacks/dividends). A company burning cash that shows POSITIVE "
        "financing cash flow every year is funding operations by continuously raising new capital — "
        "worth understanding whether that's growth-stage normal or a warning sign.",
        "Watch the trend across all three cash flow sections together, not any single number in isolation."),
    Lesson("l006", "Why Momentum Works (and Why It Randomly Stops Working)", "Quantitative", 0,
        "Price momentum — the tendency for recent winners to keep outperforming over 3-12 month "
        "windows — is one of the most robust, well-documented factors in academic finance. The leading "
        "behavioral explanation is underreaction: investors are slow to fully price in new information, "
        "so good news gets incorporated gradually rather than instantly.\n\n"
        "The catch is 'momentum crashes' — sharp, sudden reversals that tend to cluster around market "
        "turning points, especially after periods of high volatility. The very thing that makes "
        "momentum profitable (crowding into recent winners) is what makes it dangerous when sentiment "
        "flips fast, because everyone is positioned the same way at once.",
        "Momentum is a real, persistent effect — but it comes with fat-tailed crash risk concentrated around volatility spikes, not a smooth payoff."),
    Lesson("l007", "Stated Risk Tolerance vs. Revealed Risk Tolerance", "Behavioral", 0,
        "Ask most investors how they'd react to a 30% portfolio decline and you'll get a calm, "
        "rational answer — 'I'd hold, maybe buy more.' Actual behavior during real drawdowns tells a "
        "different story: retail outflows accelerate sharply during genuine crashes, well beyond what "
        "stated risk tolerance surveys would predict.\n\n"
        "This gap exists because stated risk tolerance is answered in a calm state, imagining a "
        "hypothetical. Revealed risk tolerance shows up under the actual physiological stress of "
        "watching real money disappear in real time. The practical takeaway: position sizing decisions "
        "made when calm should assume your actual behavior under stress will be somewhat worse than "
        "your stated intentions.",
        "Size positions for how you'll actually behave during a real drawdown, not how you predict you'll behave when you're calm."),
    Lesson("l008", "What the Yield Curve Inversion Actually Signals", "Macro", 0,
        "A yield curve inversion — short-term Treasury yields exceeding long-term yields — has "
        "preceded most U.S. recessions in the past 60 years, which is why it gets so much attention. "
        "The mechanism: an inverted curve typically reflects markets pricing in future rate cuts, which "
        "usually only happen because the central bank expects economic weakness ahead.\n\n"
        "The important nuance: the lag between inversion and recession has historically ranged from "
        "roughly 6 to 24 months, and the curve has also produced false signals. It's a probabilistic "
        "indicator investors watch as one input among many, not a precise, mechanical trading trigger.",
        "Yield curve inversions have real predictive history but poor timing precision — treat it as one macro input, not a trading signal on its own."),
    Lesson("l009", "Options Basics: What Implied Volatility Actually Prices In", "Derivatives", 0,
        "An option's price has two components: intrinsic value (how far in-the-money it already is) "
        "and time value, driven heavily by implied volatility — the market's forward-looking estimate "
        "of how much the underlying will move before expiration, back-solved from the option's price.\n\n"
        "Implied volatility isn't a prediction of direction, only magnitude. A stock can have very high "
        "implied volatility heading into an earnings report with no directional view at all — just high "
        "uncertainty about the SIZE of the move. This is why option premiums spike before binary events "
        "and typically collapse right after, regardless of which direction the stock moved — 'volatility crush.'",
        "High implied volatility means the market expects a big move, not that it expects a move in any particular direction."),
    Lesson("l010", "Why 'Buy the Dip' Isn't a Strategy by Itself", "Behavioral", 0,
        "'Buy the dip' has worked remarkably well across most of the post-2009 bull market, which is "
        "exactly why it's dangerous as an unconditional rule — it was reinforced by a specific, "
        "unusually persistent regime. The strategy has a very different track record during genuine "
        "structural bear markets (2000-2002, 2007-2009), where dips kept dipping for years.\n\n"
        "The distinction that actually matters: is this a sentiment-driven pullback in an intact "
        "fundamental picture, or the market correctly repricing genuine deterioration? Those look "
        "identical in the first few days of a decline and only become distinguishable over time.",
        "'Buy the dip' worked because of a specific market regime, not because it's a timeless law — the same pattern has failed for years at a time in different regimes."),
    Lesson("l011", "Free Cash Flow Yield vs. Dividend Yield", "Valuation", 0,
        "Dividend yield only captures the portion of cash a company chooses to distribute directly. "
        "Free cash flow yield (FCF divided by market cap) captures the TOTAL cash the business is "
        "generating relative to its price, regardless of whether management pays it out, reinvests it, "
        "or uses it for buybacks.\n\n"
        "A company with a 1% dividend yield but a 7% free cash flow yield is generating substantial "
        "cash — it's just choosing to redeploy most of it. Whether that's the right choice depends on "
        "whether management has good reinvestment opportunities; if not, that cash is effectively "
        "earning shareholders nothing until it's returned or productively deployed.",
        "A low dividend yield doesn't mean a company isn't generating cash — check free cash flow yield before drawing conclusions."),
    Lesson("l012", "What Short Interest Actually Tells You", "Market Mechanics", 0,
        "Short interest — the percentage of a stock's float sold short — gets popular attention mostly "
        "around short-squeeze narratives, but its more reliable use is as a proxy for how contested the "
        "bear case is. Very high short interest (25%+ of float) means sophisticated participants have "
        "taken a structural bet against the business.\n\n"
        "The squeeze mechanic is real but rare and hard to time: it requires a specific combination of "
        "high short interest, low float, and a genuine catalyst — not just 'the stock is going up.' Most "
        "high-short-interest stocks never squeeze; the short sellers are often simply right.",
        "High short interest signals genuine disagreement about the bear case — it's a real signal worth investigating, not automatically a squeeze setup."),
    Lesson("l013", "Sequence-of-Returns Risk, Explained Simply", "Risk", 0,
        "Two portfolios can have identical average annual returns over 20 years and produce wildly "
        "different outcomes purely based on the ORDER those returns happened in — this matters most for "
        "anyone regularly withdrawing from (or adding to) a portfolio, not just holding a lump sum.\n\n"
        "If large losses happen early while you're withdrawing, you're forced to sell more shares at "
        "depressed prices to generate the same dollar amount, permanently impairing recovery even if "
        "subsequent average returns match an alternate scenario exactly.",
        "The ORDER returns arrive in matters as much as the average return itself, especially if you're withdrawing money along the way."),
    Lesson("l014", "Why Analyst Price Targets Cluster Around the Current Price", "Behavioral", 0,
        "Sell-side price targets show a well-documented bias: they tend to anchor toward the current "
        "price rather than representing an independent fair-value estimate. Part of this is "
        "career-risk-driven — a wildly out-of-consensus target that's wrong is more damaging to an "
        "analyst's reputation than a modest, consensus-hugging one that's also wrong.\n\n"
        "This doesn't make targets worthless, but the DIRECTION and REASONING behind a revision usually "
        "carries more information than the number itself.",
        "Price target changes carry more signal than price target levels — watch the direction and reasoning, not the specific number."),
    Lesson("l015", "What 'Priced In' Actually Means (and When It's Wrong)", "Market Mechanics", 0,
        "'It's already priced in' is one of the most overused phrases in markets, and it's only "
        "meaningfully true when the market has had the SAME information you have, for long enough to "
        "digest it, AND the expected outcome matches what actually happens.\n\n"
        "Markets are frequently surprised by things that seem obvious in hindsight because the "
        "distribution of likely outcomes was genuinely wide beforehand — a 70%-probability outcome "
        "still surprises the market 30% of the time, and that's not irrationality, that's just probability.",
        "'Priced in' means the market's probability-weighted expectation matches an outcome — it doesn't mean surprises can't happen."),
]

# ── Tier 1: Advanced ────────────────────────────────────────────────────────
_TIER_1: list[Lesson] = [
    Lesson("a001", "Factor Investing: What 'Value' and 'Quality' Actually Measure", "Quantitative", 1,
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
    Lesson("a002", "Options Greeks Beyond Delta: Gamma, Theta, and Vega Interactions", "Derivatives", 1,
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
    Lesson("a003", "Correlation Isn't Fixed: Why Diversification Fails Exactly When You Need It", "Portfolio Theory", 1,
        "Historical correlation matrices used in portfolio construction are backward-looking averages, "
        "but correlations between assets — especially equities — are regime-dependent and tend to spike "
        "toward 1.0 during systemic stress events (2008, March 2020), precisely when diversification "
        "benefits matter most.\n\n"
        "This is sometimes called 'correlation breakdown' or the tendency for 'all correlations go to "
        "one' in a crisis, driven by forced deleveraging and liquidity-seeking selling that hits "
        "otherwise-uncorrelated assets simultaneously. Risk models built purely on historical average "
        "correlations systematically understate tail risk for exactly this reason.",
        "Correlations that look protective in calm markets often compress toward 1 during genuine crises — diversification is weakest exactly when it's needed most."),
    Lesson("a004", "Duration and Convexity: Why Bond Price Sensitivity Isn't Linear", "Fixed Income", 1,
        "Duration approximates a bond's price sensitivity to interest rate changes — a duration of 7 "
        "means roughly a 7% price move for a 1% rate change. But this relationship is a linear "
        "approximation of what's actually a convex (curved) relationship, meaning duration alone "
        "overstates losses when rates rise and understates gains when rates fall.\n\n"
        "Convexity captures this curvature. It matters most for long-duration bonds and becomes "
        "critical in large rate moves, where duration-only estimates can be meaningfully wrong. This is "
        "also why callable bonds exhibit 'negative convexity' near their call price — issuers redeem "
        "them exactly when it's least favorable to the bondholder.",
        "Duration is a linear approximation of a curved relationship — convexity corrects it, and the gap matters most during large rate moves."),
    Lesson("a005", "Market Microstructure: How Payment for Order Flow Actually Works", "Market Mechanics", 1,
        "When a retail broker routes your order to a market maker instead of directly to an exchange, "
        "the market maker typically pays the broker for that order flow (PFOF) and profits from the "
        "bid-ask spread by filling your order internally rather than on a public exchange.\n\n"
        "The real debate isn't whether PFOF exists but whether execution quality — price improvement "
        "versus the National Best Bid and Offer — genuinely offsets the conflict of interest. Studies "
        "have found retail orders often DO get modest price improvement versus quoted spreads, but "
        "market makers still profit from the flow's predictable, generally uninformed nature, which is "
        "structurally different from institutional order flow.",
        "PFOF-routed orders often get measurable price improvement, but that doesn't eliminate the underlying conflict of interest in how your order gets routed."),
    Lesson("a006", "Why Backtested Sharpe Ratios Are Almost Always Overstated", "Quantitative", 1,
        "A backtest's Sharpe ratio reflects one realized historical path, not the true underlying "
        "distribution of outcomes — and strategy development inherently involves iterating parameters "
        "until performance looks good on that specific historical sample, whether or not the researcher "
        "intends to overfit.\n\n"
        "The deflated Sharpe ratio framework explicitly corrects for the number of trials run during "
        "strategy development: testing 100 parameter combinations and reporting only the best one "
        "produces a Sharpe ratio statistically expected to be inflated even with zero true skill, purely "
        "from multiple-comparisons selection bias.",
        "The more parameter combinations tested during strategy development, the more a backtest's best result is expected to be inflated by pure chance — regardless of true skill."),
    Lesson("a007", "Credit Spreads as a Leading Economic Indicator", "Macro", 1,
        "The spread between corporate bond yields and equivalent-maturity Treasuries compensates "
        "investors for default risk, and it widens well before equity markets typically price in "
        "economic deterioration — credit markets often lead equity markets at cyclical turning points "
        "because bondholders are structurally more sensitive to downside risk than equity holders.\n\n"
        "High-yield spreads specifically are watched closely because speculative-grade issuers are most "
        "exposed to tightening financial conditions and slowing growth. A sustained, broad widening in "
        "high-yield spreads — distinct from single-issuer stress — has historically been one of the more "
        "reliable early-warning signals available across public markets.",
        "Credit spread widening often leads equity market weakness because bondholders are structurally more sensitive to downside risk than equity holders."),
    Lesson("a008", "The Mechanics of a Short Squeeze, Precisely", "Market Mechanics", 1,
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

# ── Tier 2: Expert ──────────────────────────────────────────────────────────
_TIER_2: list[Lesson] = [
    Lesson("e001", "Value-at-Risk vs. Conditional VaR: Why VaR Underestimates Tail Risk", "Risk", 2,
        "Value-at-Risk (VaR) reports a threshold loss at a given confidence level (e.g., '95% VaR of $1M' "
        "means a 5% chance of losing more than $1M over the period) — but VaR says nothing about HOW MUCH "
        "more you could lose in that tail 5% of outcomes, which is precisely the scenario that matters "
        "most for solvency.\n\n"
        "Conditional VaR (CVaR, also called Expected Shortfall) addresses this by reporting the average "
        "loss GIVEN that you're already in the tail beyond the VaR threshold — a materially more "
        "conservative and informative risk measure. Basel III's post-2008 shift toward Expected Shortfall "
        "for regulatory capital requirements was a direct response to VaR's tail-blindness during the "
        "financial crisis.",
        "VaR tells you the threshold of a bad outcome; CVaR tells you how bad the bad outcomes actually average out to be — and that's the number that matters for solvency."),
    Lesson("e002", "Factor Crowding and the Mechanics of a Quant Unwind", "Quantitative", 2,
        "When many systematic strategies independently converge on similar factor exposures (a "
        "'crowded trade'), the strategies become correlated with each other in ways their individual "
        "backtests never captured — because no single fund's historical data includes the behavior of "
        "every OTHER fund holding the same positions simultaneously.\n\n"
        "The August 2007 'quant quake' is the canonical case study: several large quant funds, running "
        "ostensibly different strategies, had converged on overlapping factor exposures. When one fund "
        "was forced to deleverage, its selling pressured prices in ways that triggered stop-losses and "
        "margin calls at other funds with correlated exposures, creating a self-reinforcing unwind across "
        "funds that had no direct relationship to each other — a liquidity spiral driven purely by "
        "position overlap, not by any change in fundamentals.",
        "Crowded factor trades create correlation between otherwise-unrelated funds that only becomes visible during a forced unwind — a risk no individual fund's backtest can see."),
    Lesson("e003", "Volatility Term Structure and the Economics of the VIX Futures Curve", "Derivatives", 2,
        "The VIX itself is a spot measure of 30-day implied volatility; VIX futures reference expectations "
        "of where that measure will be at future dates, and the curve connecting them typically slopes "
        "upward (contango) in calm markets — reflecting a persistent risk premium investors demand to "
        "sell volatility protection — and inverts sharply into backwardation during acute stress.\n\n"
        "This term structure is why volatility-linked ETPs that roll futures contracts systematically "
        "bleed value in contango regimes: they're perpetually selling a cheaper near-dated contract and "
        "buying a more expensive longer-dated one, a structural cost embedded in the product's mechanics "
        "independent of whether volatility itself rises or falls.",
        "Long volatility products decay in contango markets because of the structural cost of rolling futures, not because volatility failed to rise."),
    Lesson("e004", "Execution and Market Impact: The Almgren-Chriss Framework, Intuitively", "Market Mechanics", 2,
        "Large institutional orders face a fundamental tradeoff: execute fast and pay more market impact "
        "(moving the price against yourself as you consume liquidity), or execute slowly and reduce impact "
        "but accept more exposure to adverse price drift and volatility risk over the longer execution "
        "window.\n\n"
        "The Almgren-Chriss framework formalizes this as an optimization problem, balancing expected "
        "market impact cost against the variance of execution price risk, producing an optimal trading "
        "trajectory rather than either extreme. This is the theoretical basis for VWAP and "
        "implementation-shortfall algorithms used throughout institutional execution desks — the choice "
        "of execution speed is itself a risk decision, not just a cost-minimization one.",
        "Fast execution minimizes timing risk but maximizes market impact cost; slow execution does the reverse — optimal execution balances both, it doesn't eliminate either."),
    Lesson("e005", "Why Tail Risk Hedges Have a Structurally Negative Expected Return", "Risk", 2,
        "Buying out-of-the-money put protection as portfolio insurance has, over most historical periods, "
        "a negative expected return by design — insurance sellers price in a risk premium, and realized "
        "crash frequency has historically been lower than what implied volatility priced in during "
        "calm periods, meaning systematic tail hedging bleeds value most of the time.\n\n"
        "The honest framing institutional allocators use: tail hedges aren't return-generating positions, "
        "they're a cost paid for a specific payoff structure (convexity during a crash) that changes the "
        "SHAPE of portfolio returns, not the average. Evaluating a tail-hedge program on its standalone "
        "P&L misses the point — the relevant metric is the whole portfolio's behavior during the tail "
        "event the hedge exists to address.",
        "Tail hedges are expected to lose money most of the time by design — their value is in the shape of outcomes during a crash, not standalone P&L."),
    Lesson("e006", "Liquidity Risk Premia and the Illiquidity Discount in Private Markets", "Portfolio Theory", 2,
        "Assets that can't be traded on demand command a return premium versus otherwise-comparable "
        "liquid assets — this illiquidity premium compensates investors for the inability to rebalance "
        "or exit during stress, and it's a documented, persistent feature across private equity, real "
        "estate, and other locked-capital structures.\n\n"
        "The measurement challenge is that private-market valuations are typically appraisal-based and "
        "update infrequently, which artificially smooths reported volatility and correlation to public "
        "markets — a well-documented statistical artifact sometimes called 'volatility laundering' that "
        "makes private assets look less risky and less correlated than they actually are on a "
        "mark-to-market basis.",
        "Private-market assets often look less volatile and less correlated to stocks than they really are — that's largely a reporting artifact of infrequent appraisal-based valuation, not lower true risk."),
    Lesson("e007", "Reflexivity: When Price Action Changes the Fundamentals It's Supposed to Reflect", "Behavioral", 2,
        "Standard theory treats price as a reflection of fundamentals. George Soros's reflexivity thesis "
        "describes cases where the causality runs the other direction too — rising prices can themselves "
        "improve a company's actual fundamentals (cheaper capital raises, easier acquisitions using stock "
        "as currency, improved credit terms), creating a genuine feedback loop rather than a pure "
        "sentiment bubble disconnected from reality.\n\n"
        "This matters for distinguishing 'irrational bubble' narratives from cases where a rising stock "
        "price is mechanically improving the underlying business's actual competitive position — the two "
        "can look identical in the price chart but have very different implications for how the cycle "
        "eventually resolves.",
        "Rising prices can sometimes genuinely improve a company's fundamentals (cheaper capital, stock-funded M&A), not just reflect sentiment disconnected from reality — the two are hard to distinguish in real time."),
]

LESSONS_BY_TIER: dict[int, list[Lesson]] = {0: _TIER_0, 1: _TIER_1, 2: _TIER_2}


def get_lesson_for_date(tier: int, day_of_year: int) -> Lesson:
    """Deterministic rotation within a tier — same lesson for every user at that tier on the same day."""
    tier = max(0, min(2, tier))
    bank = LESSONS_BY_TIER[tier]
    return bank[day_of_year % len(bank)]
