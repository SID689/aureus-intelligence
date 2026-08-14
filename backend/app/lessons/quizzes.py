"""
app/lessons/quizzes.py
------------------------
Quiz bank for tiers 1–4, keyed by lesson id.

WHY THESE AREN'T INLINE WITH THE LESSONS
Module 0 (tier0_beginner.py) carries its quizzes inline because those
lessons and their assessments were written together as one teaching unit.
Tiers 1, 3 and 4 predate the quiz system entirely — their prose was
already written and reviewed, so quizzes are attached here rather than by
editing 30 existing lesson bodies. Keeping them in one bank also makes
coverage auditable at a glance: any lesson id missing from this dict has
no quiz, which `content.py` reports via `lessons_without_quizzes()`.

Tier 2 (Intermediate) is also banked here for consistency with the other
non-beginner tiers.

AUTHORING RULES
  - Every question must be answerable from the lesson body alone.
  - Distractors must be plausible — a question whose wrong answers are
    obviously absurd tests nothing.
  - The explanation is the teaching payload. It runs on both correct and
    incorrect answers, so it must explain WHY, not just confirm.
"""

from app.lessons.models import QuizQuestion

QUIZ_BANK: dict[str, list[QuizQuestion]] = {

    # ── Tier 1 — Foundational+ ────────────────────────────────────────────
    "l001": [
        QuizQuestion(
            "A software company trades at 35x earnings; a regional bank trades at 9x. What does this most reliably tell you?",
            ["The bank is cheaper and a better buy", "The market expects very different growth and earnings durability for each", "The bank's earnings are more trustworthy", "The software company is overvalued"],
            1,
            "P/E is only comparable within a peer group with similar capital structure and growth dynamics. Across "
            "sectors the ratio mostly reflects differing growth expectations, not relative cheapness.",
        ),
        QuizQuestion(
            "Why do professional analysts triangulate P/E against free cash flow?",
            ["Free cash flow is reported more frequently", "Earnings are an accounting construct management has real discretion over; cash is harder to shape", "P/E is only valid for unprofitable companies", "Cash flow always exceeds earnings"],
            1,
            "Depreciation schedules, revenue recognition timing and one-time charges all let two companies with "
            "identical cash economics report different earnings. Cash is the harder number to manipulate.",
        ),
    ],
    "l002": [
        QuizQuestion(
            "A stock has a beta of 0.6. What does this tell you?",
            ["The business is fundamentally safe", "It has historically moved about 60% as much as the market", "It cannot lose more than 60% of its value", "It has low company-specific risk"],
            1,
            "Beta measures historical co-movement with a benchmark — systematic risk only. It says nothing about the "
            "quality or safety of the underlying business.",
        ),
        QuizQuestion(
            "Which risk does beta specifically fail to capture?",
            ["Market-wide systematic risk", "Idiosyncratic risk such as fraud, a failed product, or litigation", "Interest rate risk", "Currency risk"],
            1,
            "Beta captures only the component of risk correlated with the market. Company-specific catastrophes are "
            "invisible to it, which is why low beta is not a synonym for safe.",
        ),
    ],
    "l003": [
        QuizQuestion(
            "What is the key difference between volume and liquidity?",
            ["They are the same measure", "Volume is shares already traded; liquidity is how much you could trade now without moving the price", "Liquidity applies only to bonds", "Volume is forward-looking, liquidity is historical"],
            1,
            "Volume is a backward-looking count. Liquidity is about current order book depth — how much size the market "
            "can absorb right now without the price moving against you.",
        ),
        QuizQuestion(
            "A stock shows healthy average daily volume but you still struggle to exit a large position cleanly. Why is that possible?",
            ["Average volume is always fabricated", "That volume may be concentrated in a few block trades rather than continuous two-sided flow", "Volume only counts buy orders", "Large positions cannot legally be sold quickly"],
            1,
            "Average volume can be produced by a handful of large block trades. What matters for your exit is the depth "
            "of resting orders and the spread at the moment you trade.",
        ),
    ],
    "l004": [
        QuizQuestion(
            "Roughly where do the benefits of adding more individual stocks largely flatten out?",
            ["Around 5 holdings", "Around 20–30 well-chosen, uncorrelated holdings", "Around 200 holdings", "Diversification benefits never diminish"],
            1,
            "Company-specific risk falls steeply with the first ~20–30 uncorrelated positions and then with sharply "
            "diminishing returns. Beyond that you mostly add costs and monitoring overhead.",
        ),
        QuizQuestion(
            "What risk can never be diversified away by owning more individual stocks?",
            ["Fraud at a single company", "Sector concentration risk", "Market-wide systematic risk", "Liquidity risk in one name"],
            2,
            "Systematic risk affects all equities together. Reducing it requires different asset classes — bonds, cash, "
            "genuinely uncorrelated assets — not additional stocks.",
        ),
    ],
    "l005": [
        QuizQuestion(
            "A mature, healthy company typically shows which cash flow pattern?",
            ["Negative operating, positive investing, positive financing", "Positive operating, negative investing, negative financing", "Negative operating, negative investing, positive financing", "Positive operating, positive investing, positive financing"],
            1,
            "Positive operating cash flow (the business generates cash), negative investing (reinvesting in assets), and "
            "negative financing (paying down debt or returning capital) is the classic mature profile.",
        ),
        QuizQuestion(
            "A company shows consistently negative operating cash flow and positive financing cash flow year after year. What does that indicate?",
            ["It is highly profitable", "It is funding operations by continuously raising new capital", "It is paying down debt aggressively", "It has no capital expenditures"],
            1,
            "Persistently raising capital to cover operating cash burn may be normal for a growth-stage company, or a "
            "warning sign — but either way the business is not yet self-funding.",
        ),
    ],
    "l006": [
        QuizQuestion(
            "What is the leading behavioural explanation for why momentum works?",
            ["Investors overreact instantly to all news", "Investors underreact, so new information gets priced in gradually rather than instantly", "Momentum is purely a data artifact", "Central banks target momentum"],
            1,
            "Underreaction means good news is incorporated over weeks and months rather than in one jump, producing the "
            "3–12 month continuation that momentum strategies capture.",
        ),
        QuizQuestion(
            "When do momentum crashes tend to cluster?",
            ["During long periods of low volatility", "Around market turning points, especially after high-volatility periods", "Only in bond markets", "Uniformly at random"],
            1,
            "The crowding that makes momentum profitable is exactly what makes it dangerous when sentiment flips — "
            "everyone is positioned the same way, so the unwind is violent.",
        ),
    ],
    "l007": [
        QuizQuestion(
            "Why does stated risk tolerance typically overstate actual risk tolerance?",
            ["Surveys are poorly worded", "Stated tolerance is given in a calm state imagining a hypothetical; real drawdowns involve genuine physiological stress", "Investors deliberately lie to advisors", "Risk tolerance is fixed and unchanging"],
            1,
            "The gap is situational, not dishonest. Answering calmly about a hypothetical is a fundamentally different "
            "task from watching real money disappear in real time.",
        ),
        QuizQuestion(
            "What is the practical implication for position sizing?",
            ["Ignore risk tolerance entirely", "Assume your behaviour under real stress will be somewhat worse than your stated intentions", "Take more risk since you'll adapt", "Only invest during calm markets"],
            1,
            "Size for how you will actually behave in a drawdown, not for the disciplined version of yourself you "
            "imagine while calm.",
        ),
    ],
    "l008": [
        QuizQuestion(
            "What does a yield curve inversion most directly reflect?",
            ["Guaranteed recession within 6 months", "Markets pricing in future rate cuts, which usually accompany expected economic weakness", "A shortage of Treasury bonds", "Rising inflation expectations"],
            1,
            "The mechanism is expectation of future cuts. Cuts are usually anticipated because the central bank is "
            "expected to respond to weakness — which is why inversion correlates with recessions.",
        ),
        QuizQuestion(
            "What is the main practical limitation of the inversion signal?",
            ["It has never preceded a recession", "The lag has historically ranged from roughly 6 to 24 months, and false signals occur", "It only applies outside the US", "It can only be observed after a recession ends"],
            1,
            "The directional record is real but the timing precision is poor. It's one probabilistic macro input, not a "
            "mechanical trading trigger.",
        ),
    ],
    "l009": [
        QuizQuestion(
            "What does high implied volatility tell you?",
            ["The stock will rise sharply", "The market expects a large move, without indicating direction", "The option is mispriced", "The stock will fall sharply"],
            1,
            "Implied volatility prices magnitude, not direction. A stock can have very high IV before earnings with no "
            "directional view embedded at all.",
        ),
        QuizQuestion(
            "Why do option premiums often collapse immediately after an earnings release regardless of which way the stock moved?",
            ["Exchanges reset prices after events", "The uncertainty the premium was pricing has resolved — 'volatility crush'", "Traders stop buying options after earnings", "Time value increases after events"],
            1,
            "Premium was elevated to compensate for uncertainty about the size of the move. Once the event resolves, "
            "that uncertainty disappears and the implied volatility component deflates.",
        ),
    ],
    "l010": [
        QuizQuestion(
            "Why is 'buy the dip' risky as an unconditional rule?",
            ["It never worked historically", "It was reinforced by a specific persistent regime and has failed for years at a time in structural bear markets", "It only applies to bonds", "Dips are impossible to identify"],
            1,
            "The strategy's strong record across the post-2009 period reflects that regime. In 2000–2002 and 2007–2009 "
            "dips kept dipping for years.",
        ),
        QuizQuestion(
            "What is the distinction that actually matters when a stock declines?",
            ["Whether volume was high", "Whether it's a sentiment-driven pullback in an intact fundamental picture or the market correctly repricing genuine deterioration", "Whether the decline exceeded 10%", "Whether analysts downgraded it"],
            1,
            "Those two cases look identical in the first days of a decline and only separate over time — which is "
            "precisely why an unconditional rule is dangerous.",
        ),
    ],
    "l011": [
        QuizQuestion(
            "A company has a 1% dividend yield and a 7% free cash flow yield. What does this indicate?",
            ["The dividend is unsustainable", "The business generates substantial cash but management redeploys most of it rather than distributing it", "The company is unprofitable", "The free cash flow figure must be an error"],
            1,
            "Dividend yield captures only what's distributed. FCF yield captures total cash generation relative to "
            "price, regardless of how management chooses to allocate it.",
        ),
        QuizQuestion(
            "What determines whether retaining cash instead of paying it out is the right choice?",
            ["It is always better to pay dividends", "Whether management has good reinvestment opportunities for that capital", "The company's share price level", "The dividend yields of competitors"],
            1,
            "Retained cash creates value only if reinvested at attractive returns. Absent good opportunities, it earns "
            "shareholders little until it's returned or productively deployed.",
        ),
    ],
    "l012": [
        QuizQuestion(
            "What is the more reliable interpretation of very high short interest?",
            ["A squeeze is imminent", "Sophisticated participants have taken a structural bet against the business — the bear case is contested", "The company is committing fraud", "The stock is guaranteed to fall"],
            1,
            "High short interest signals genuine, researched disagreement. Most high-short-interest stocks never squeeze; "
            "frequently the short sellers are simply correct.",
        ),
        QuizQuestion(
            "What combination does a genuine short squeeze require?",
            ["High short interest alone", "High short interest, limited float/borrow supply, AND a real catalyst", "Any stock rising more than 10%", "High trading volume alone"],
            1,
            "All three conditions must coincide. Any one alone produces an ordinary price move, not the forced covering "
            "that defines a squeeze.",
        ),
    ],
    "l013": [
        QuizQuestion(
            "Two portfolios have identical 20-year average annual returns but very different final values. What explains this?",
            ["One had lower fees", "The ORDER in which returns occurred, combined with contributions or withdrawals", "Averages are always misleading", "One was measured in different currency"],
            1,
            "Sequence-of-returns risk: with cash flows in or out, the order matters as much as the average, because you "
            "transact at whatever the value happens to be at that moment.",
        ),
        QuizQuestion(
            "Why are early large losses especially damaging for someone withdrawing from a portfolio?",
            ["Taxes are higher early on", "You must sell more shares at depressed prices for the same dollar amount, permanently impairing recovery", "Early losses are always larger", "Withdrawals are prohibited during drawdowns"],
            1,
            "Selling more shares to fund the same withdrawal permanently reduces the share count that participates in "
            "the eventual recovery.",
        ),
    ],
    "l014": [
        QuizQuestion(
            "Why do sell-side price targets tend to cluster near the current price?",
            ["Regulation requires it", "Career risk — a wildly out-of-consensus wrong call damages an analyst more than a consensus-hugging wrong call", "Analysts lack valuation models", "Targets are set by exchanges"],
            1,
            "The asymmetric professional consequence of being wrong alone versus wrong with everyone else creates a "
            "documented anchoring bias toward the current price.",
        ),
        QuizQuestion(
            "What carries more information in an analyst update?",
            ["The precise target number", "The direction of the revision and the reasoning behind it", "The analyst's firm size", "The date it was published"],
            1,
            "The level is anchored and therefore low-signal. A revision reveals that the analyst's view of the business "
            "changed, and the stated reasoning is the substance.",
        ),
    ],
    "l015": [
        QuizQuestion(
            "When is 'it's already priced in' genuinely true?",
            ["Whenever an event has been discussed in the news", "When the market had the same information for long enough to digest it AND the outcome matches expectations", "Always, because markets are efficient", "Never — markets are always surprised"],
            1,
            "All three conditions matter. Information being public is not sufficient if the realised outcome differs "
            "from the market's probability-weighted expectation.",
        ),
        QuizQuestion(
            "A 70%-probability outcome fails to occur and the market moves sharply. What does this demonstrate?",
            ["The market was irrational", "Ordinary probability — a 70% likely event does not happen 30% of the time", "The probability estimate was fabricated", "Prices are random"],
            1,
            "Surprise at a 30% outcome isn't evidence of irrationality. Wide outcome distributions mean 'obvious in "
            "hindsight' events genuinely weren't obvious beforehand.",
        ),
    ],

    # ── Tier 2 — Intermediate ─────────────────────────────────────────────
    "i001": [
        QuizQuestion(
            "A $100,000 portfolio risks 1% per position. Entry is $80, stop is $76. What position size does the formula give?",
            ["1,000 shares ($80,000)", "250 shares ($20,000)", "125 shares ($10,000)", "500 shares ($40,000)"],
            1,
            "Risk budget = $1,000. Risk per share = $80 − $76 = $4. Position = $1,000 ÷ $4 = 250 shares, or $20,000 of "
            "capital. Note the capital committed (20%) is far larger than the risk taken (1%).",
        ),
        QuizQuestion(
            "Why do five 2% positions in five semiconductor companies not equal five independent 2% risks?",
            ["Semiconductor stocks are more volatile individually", "They are highly correlated, so in a sector selloff they behave closer to a single 10% risk", "Position limits do not apply to sectors", "Correlation only matters for bonds"],
            1,
            "Correlated positions concentrate rather than diversify. Real sizing accounts for combined exposure across "
            "holdings, not just a per-holding cap.",
        ),
        QuizQuestion(
            "Recovering from a 50% drawdown requires what gain?",
            ["50%", "75%", "100%", "150%"],
            2,
            "Halving your capital means you must double what remains to get back to even. This asymmetry — and its "
            "acceleration at deeper losses — is why professionals prioritise avoiding large drawdowns.",
        ),
    ],
    "i002": [
        QuizQuestion(
            "In a typical 10-year DCF, roughly how much of computed value comes from the terminal value?",
            ["Under 10%", "Around 25%", "Commonly 60–80%", "Exactly 50% by construction"],
            2,
            "The majority of a DCF's output usually rests on the terminal value, which is driven by an unknowable "
            "perpetual growth assumption — the main reason DCF precision is illusory.",
        ),
        QuizQuestion(
            "What makes a reverse DCF more practically useful than a standard one?",
            ["It requires fewer inputs", "It converts an unanswerable question into a checkable one: is the growth the price already implies plausible?", "It always produces a higher valuation", "It eliminates the need for a discount rate"],
            1,
            "Instead of guessing growth to produce a value, you take the observable market price and solve for the "
            "implied growth — which you can then test against industry history and base rates.",
        ),
    ],
    "i003": [
        QuizQuestion(
            "What makes year-over-year changes in Item 1A (Risk Factors) valuable?",
            ["The section is audited", "Companies rarely add risk factors voluntarily, so a new one signals something counsel concluded was now material", "It contains forward earnings guidance", "It lists competitor weaknesses"],
            1,
            "Much of Item 1A is boilerplate. The signal is the delta — additions and reordering often surface "
            "deterioration before it reaches the income statement.",
        ),
        QuizQuestion(
            "Net income has grown steadily for three years while operating cash flow has stagnated. What does this most likely indicate?",
            ["The company is unusually efficient", "Profit is being recognised faster than cash arrives — possibly legitimate growth, possibly aggressive accounting", "Cash flow statements are unreliable", "The company has no debt"],
            1,
            "A persistent, widening accrual gap is one of the most accessible red flags. It warrants investigation "
            "rather than an automatic conclusion — but it should never be ignored.",
        ),
    ],
    "i004": [
        QuizQuestion(
            "A strategy wins 90% of the time averaging +$100 and loses 10% of the time averaging −$1,200. What is its expected value per trade?",
            ["+$90", "−$30", "+$100", "−$120"],
            1,
            "EV = (0.9 × 100) − (0.1 × 1200) = 90 − 120 = −$30. A 90% win rate can absolutely be a losing strategy when "
            "the rare losses are large enough.",
        ),
        QuizQuestion(
            "Why can a 35% win rate strategy be excellent?",
            ["Win rate is inversely related to quality", "Because average wins can be far larger than average losses, producing positive expected value", "Because it trades less frequently", "It cannot be — 35% is always unprofitable"],
            1,
            "EV depends on the payoff distribution. Large winners against small losers can produce strong positive "
            "expectancy despite losing most individual trades.",
        ),
    ],
    "i005": [
        QuizQuestion(
            "Why is a market-cap-weighted index fund described as having a built-in momentum tilt?",
            ["It actively trades winners", "A holding's weight rises automatically as its price rises, with no trade required", "It excludes declining companies", "Managers pick recent winners"],
            1,
            "Weight tracks market value, so rising stocks mechanically become a larger share of the fund. This keeps "
            "turnover low but lets concentration build silently.",
        ),
        QuizQuestion(
            "Why is tracking difference a more honest cost measure than the expense ratio?",
            ["It is calculated by the SEC", "It captures rebalancing costs, cash drag, and lending revenue — the full real-world gap versus the index", "It is always lower than the expense ratio", "It excludes management fees"],
            1,
            "The expense ratio is only the advertised fee. Tracking difference measures what actually happened to your "
            "return relative to the index, incorporating every hidden cost and offset.",
        ),
    ],
    "i006": [
        QuizQuestion(
            "Why do rising rates hit unprofitable long-duration growth companies hardest?",
            ["They carry more debt by definition", "Their value depends on cash flows far in the future, which are discounted across more periods", "They are always overvalued", "Their revenues fall when rates rise"],
            1,
            "Rate sensitivity scales with how distant the cash flows are. The same rate move compounds across many more "
            "discounting periods for a company whose payoff is a decade out.",
        ),
        QuizQuestion(
            "A widely anticipated rate hike is announced and stocks rally. Why is this not a contradiction?",
            ["Markets are irrational", "The expected hike was already priced in; what moved markets was the surprise in accompanying guidance", "Rate hikes always help stocks", "The hike must have been cancelled"],
            1,
            "Markets price anticipated paths continuously. Only deviations from what was already expected move prices — "
            "which is why direction of surprise beats direction of policy.",
        ),
    ],
    "i007": [
        QuizQuestion(
            "Why does backtesting an index's CURRENT members overstate historical returns?",
            ["Current members have higher fees", "Those companies were partly selected by having survived and succeeded — a criterion unavailable at the time", "Index membership never changes", "Historical prices are inaccurate"],
            1,
            "Survivorship bias: every company that went bankrupt, was delisted, or acquired in distress has been "
            "silently deleted from the sample.",
        ),
        QuizQuestion(
            "You test 100 parameter combinations and report the best one. Why is that result likely inflated?",
            ["Computers introduce rounding errors", "The best of 100 draws is expected to look good through chance alone, even with zero true edge", "More tests always reduce accuracy", "Backtests cannot handle 100 variations"],
            1,
            "Reporting a maximum from many trials is a multiple-comparisons problem. The number of variations tested is "
            "itself required information for interpreting the result.",
        ),
    ],

    # ── Tier 3 — Advanced ─────────────────────────────────────────────────
    "a001": [
        QuizQuestion(
            "Value underperformed growth for over a decade before reversing. What does this best illustrate?",
            ["The value factor was permanently arbitraged away", "Factor premiums are real but cyclical, with extended drawdowns as an expected property", "Factor investing is pseudoscience", "Growth is structurally superior"],
            1,
            "Factor cyclicality is a documented, expected feature. A long stretch of underperformance is not by itself "
            "evidence the premium has disappeared.",
        ),
        QuizQuestion(
            "How is the 'quality' factor typically measured?",
            ["Analyst ratings", "Profitability, earnings stability, and low leverage", "Market capitalisation", "Dividend yield alone"],
            1,
            "Quality is constructed from balance-sheet and income-statement characteristics, not from opinion-based "
            "ratings.",
        ),
    ],
    "a002": [
        QuizQuestion(
            "What does gamma measure?",
            ["Sensitivity to time decay", "The rate of change of delta as the underlying moves", "Sensitivity to interest rates", "Implied volatility level"],
            1,
            "Gamma is the second derivative — it governs how quickly your directional exposure itself changes, which is "
            "why short-gamma positions can see accelerating losses.",
        ),
        QuizQuestion(
            "Why are short-dated at-the-money options described as the highest-convexity instrument in the standard toolkit?",
            ["They have the lowest premium", "Gamma and theta are both enormous simultaneously, so small moves cause large P&L swings while decay accelerates", "They cannot expire worthless", "They have no vega exposure"],
            1,
            "The simultaneous concentration of gamma and theta near expiry produces violent, non-linear P&L behaviour "
            "in both directions.",
        ),
    ],
    "a003": [
        QuizQuestion(
            "What happens to correlations between equities during systemic stress events?",
            ["They fall toward zero", "They tend to spike toward 1.0, precisely when diversification is most needed", "They remain stable", "They become negative"],
            1,
            "Forced deleveraging and liquidity-seeking selling hit otherwise-uncorrelated assets simultaneously — "
            "'all correlations go to one' in a crisis.",
        ),
        QuizQuestion(
            "Why do risk models built on historical average correlations systematically understate tail risk?",
            ["They use too much data", "Average correlations reflect calm regimes and miss the crisis-period compression toward 1.0", "Correlation is impossible to compute", "They over-weight recent data"],
            1,
            "A backward-looking average blends calm and crisis periods, understating how tightly assets move together "
            "in exactly the scenarios that determine survival.",
        ),
    ],
    "a004": [
        QuizQuestion(
            "Duration alone overstates losses when rates rise and understates gains when rates fall. Why?",
            ["Duration is calculated incorrectly by convention", "The true price/yield relationship is convex, and duration is a linear approximation of it", "Bond prices do not respond to rates", "Duration only applies to equities"],
            1,
            "Convexity captures the curvature that the linear duration estimate misses. The error grows with the size "
            "of the rate move and the bond's duration.",
        ),
        QuizQuestion(
            "Why do callable bonds exhibit negative convexity near the call price?",
            ["They have no maturity date", "Issuers redeem them exactly when it is least favourable to the bondholder, capping upside", "They pay no coupon", "Their duration is always zero"],
            1,
            "The embedded call option truncates price appreciation — as rates fall and the bond would otherwise rally, "
            "the likelihood of early redemption caps the gain.",
        ),
    ],
    "a005": [
        QuizQuestion(
            "How do market makers profit from payment for order flow arrangements?",
            ["Fees charged to the exchange", "By internalising the order and capturing the bid-ask spread on generally uninformed retail flow", "By front-running the customer's order", "Commissions charged to the retail investor"],
            1,
            "Retail flow is predictable and generally uninformed, which is structurally different from institutional "
            "flow and therefore valuable to internalise.",
        ),
        QuizQuestion(
            "What does research generally find about execution quality on PFOF-routed retail orders?",
            ["They consistently fill worse than the quoted spread", "They often receive modest price improvement versus the NBBO, though the conflict of interest remains", "Execution quality is identical to institutional orders", "They never fill"],
            1,
            "Measurable price improvement and a real structural conflict of interest can both be true simultaneously — "
            "which is why the debate persists.",
        ),
    ],
    "a006": [
        QuizQuestion(
            "What does the deflated Sharpe ratio explicitly correct for?",
            ["Inflation", "The number of trials run during strategy development", "Currency effects", "Survivorship bias only"],
            1,
            "It adjusts for multiple-comparisons selection bias — testing many configurations and reporting the best "
            "inflates the apparent Sharpe even with zero true skill.",
        ),
        QuizQuestion(
            "Why is a backtest's Sharpe ratio described as reflecting one realised path rather than the true distribution?",
            ["Sharpe ratios are always wrong", "History delivered one sequence of outcomes out of many that could have occurred", "Sharpe requires daily data", "It excludes the risk-free rate"],
            1,
            "The single historical path is a sample, not the population. Strategy development that iterates against "
            "that one path compounds the problem.",
        ),
    ],
    "a007": [
        QuizQuestion(
            "Why do credit markets often lead equity markets at cyclical turning points?",
            ["Bond traders receive information earlier", "Bondholders are structurally more sensitive to downside risk than equity holders", "Credit markets are larger", "Equities are not affected by recessions"],
            1,
            "Bondholders have capped upside and full downside exposure to default, making them highly attentive to "
            "deterioration that equity holders may still price optimistically.",
        ),
        QuizQuestion(
            "Why are high-yield spreads watched more closely than investment-grade spreads as an early warning?",
            ["They are less volatile", "Speculative-grade issuers are most exposed to tightening financial conditions and slowing growth", "They are government-guaranteed", "They are unaffected by defaults"],
            1,
            "The most marginal borrowers feel a squeeze first, so broad high-yield spread widening tends to surface "
            "stress earlier than investment grade.",
        ),
    ],
    "a008": [
        QuizQuestion(
            "What does a high 'days to cover' ratio indicate?",
            ["Shorts can exit easily", "An orderly unwind would take many days, so shorts cannot exit in size without moving the price against themselves", "The stock has no short interest", "The company is about to be acquired"],
            1,
            "Days to cover = short interest ÷ average daily volume. High values mean the exit is crowded relative to "
            "available liquidity — the structural precondition for a squeeze.",
        ),
        QuizQuestion(
            "What distinguishes a genuine short squeeze from an ordinary rally?",
            ["The size of the price move", "Forced buying by short sellers who cannot wait it out, driven by limited borrow supply", "High trading volume", "Positive earnings news"],
            1,
            "Forced covering is the defining mechanism. Without constrained borrow supply compelling shorts to buy, a "
            "rising price is just a rally.",
        ),
    ],

    # ── Tier 4 — Expert ───────────────────────────────────────────────────
    "e001": [
        QuizQuestion(
            "What does a '95% VaR of $1M' tell you?",
            ["Your maximum possible loss is $1M", "There is a 5% chance of losing more than $1M — with no information about how much more", "You will lose $1M 5% of the time exactly", "Your average loss is $1M"],
            1,
            "VaR reports a threshold, not a magnitude beyond it. Its silence about the depth of the tail is precisely "
            "its central weakness.",
        ),
        QuizQuestion(
            "Why did Basel III shift toward Expected Shortfall for regulatory capital?",
            ["It is simpler to compute", "VaR's tail-blindness during the financial crisis; CVaR reports the average loss GIVEN you are in the tail", "Expected Shortfall always produces lower capital requirements", "VaR was found to be illegal"],
            1,
            "CVaR conditions on already being in the tail and averages those outcomes, making it materially more "
            "informative about solvency-threatening scenarios.",
        ),
    ],
    "e002": [
        QuizQuestion(
            "Why can't an individual fund's backtest capture factor crowding risk?",
            ["Backtests exclude factor data", "Its historical data contains no information about the positions every OTHER fund holds simultaneously", "Crowding is not measurable", "Backtests only cover one year"],
            1,
            "Crowding is a property of the aggregate system, invisible in any single participant's own return history — "
            "which is why it only reveals itself during a forced unwind.",
        ),
        QuizQuestion(
            "In the August 2007 quant quake, what drove the correlated losses across funds?",
            ["A shared fundamental shock to the companies held", "Overlapping factor exposures — one fund's forced deleveraging pressured prices and triggered stop-losses at others", "A coordinated regulatory action", "A single exchange outage"],
            1,
            "The funds had no direct relationship. Position overlap alone created a self-reinforcing liquidity spiral "
            "with no change in fundamentals.",
        ),
    ],
    "e003": [
        QuizQuestion(
            "Why do volatility-linked ETPs that roll futures systematically bleed value in contango?",
            ["Management fees are unusually high", "They perpetually sell a cheaper near-dated contract and buy a more expensive longer-dated one", "Volatility always falls", "They are required to hold cash"],
            1,
            "The roll cost is structural, embedded in the product's mechanics, and occurs independently of whether "
            "spot volatility rises or falls.",
        ),
        QuizQuestion(
            "What does an upward-sloping (contango) VIX futures curve in calm markets primarily reflect?",
            ["An expectation that volatility will definitely rise", "A persistent risk premium investors demand to sell volatility protection", "A data error", "Central bank intervention"],
            1,
            "The typical upward slope reflects compensation for bearing volatility risk, not a forecast. The curve "
            "inverts into backwardation during acute stress.",
        ),
    ],
    "e004": [
        QuizQuestion(
            "What tradeoff does the Almgren-Chriss framework formalise?",
            ["Commission versus taxes", "Market impact cost from fast execution versus price/volatility risk from slow execution", "Long versus short positioning", "Equity versus fixed income allocation"],
            1,
            "It treats execution speed as an optimisation between impact cost and timing risk, producing a trajectory "
            "rather than either extreme.",
        ),
        QuizQuestion(
            "What is the key implication for institutional traders?",
            ["Always execute as fast as possible", "Execution speed is itself a risk decision, not merely a cost-minimisation one", "Market impact can be eliminated entirely", "Only order size matters"],
            1,
            "Because both extremes carry distinct risks, the choice of trajectory is a risk-management decision — the "
            "theoretical basis for VWAP and implementation-shortfall algorithms.",
        ),
    ],
    "e005": [
        QuizQuestion(
            "Why do systematic tail hedges have a structurally negative expected return?",
            ["They are always mispriced by exchanges", "Insurance sellers price in a risk premium, and realised crash frequency has historically been lower than implied volatility priced", "Puts cannot be exercised", "They are taxed punitively"],
            1,
            "The seller's risk premium plus the historical gap between implied and realised crash frequency means "
            "systematic protection bleeds value most of the time by design.",
        ),
        QuizQuestion(
            "How do institutional allocators correctly evaluate a tail-hedge program?",
            ["On its standalone P&L", "On the whole portfolio's behaviour during the tail event the hedge exists to address", "On its Sharpe ratio in isolation", "On annual premium spend alone"],
            1,
            "The hedge changes the SHAPE of portfolio outcomes, not the average. Judging it standalone misses its "
            "entire purpose.",
        ),
    ],
    "e006": [
        QuizQuestion(
            "What is 'volatility laundering' in private-market valuations?",
            ["Illegal manipulation of returns", "Appraisal-based, infrequently-updated valuations artificially smoothing reported volatility and correlation", "A hedging technique", "A tax optimisation strategy"],
            1,
            "It's a statistical artifact of the valuation method, not fraud — but it does make private assets appear "
            "less risky and less correlated than they are on a mark-to-market basis.",
        ),
        QuizQuestion(
            "What does the illiquidity premium compensate investors for?",
            ["Higher management fees", "The inability to rebalance or exit during stress", "Currency risk", "Regulatory complexity"],
            1,
            "Locked capital removes optionality precisely when it's most valuable, and the premium is compensation for "
            "surrendering that flexibility.",
        ),
    ],
    "e007": [
        QuizQuestion(
            "What does Soros's reflexivity thesis describe?",
            ["Prices always revert to fundamental value", "Cases where rising prices themselves improve a company's actual fundamentals, creating a genuine feedback loop", "That fundamentals are irrelevant", "That markets are perfectly efficient"],
            1,
            "Cheaper capital raises, stock-funded acquisitions, and improved credit terms mean price can causally "
            "affect fundamentals, not merely reflect them.",
        ),
        QuizQuestion(
            "Why does reflexivity complicate identifying bubbles in real time?",
            ["Bubbles are always obvious", "A genuine price-driven improvement in competitive position looks identical on a chart to pure sentiment detached from reality", "Reflexivity only applies to bonds", "Price charts are unreliable"],
            1,
            "Both produce the same rising chart but resolve very differently, and the distinction is usually only clear "
            "in hindsight.",
        ),
    ],
    "l016": [
        QuizQuestion(
            "What does a sentiment score actually measure?",
            ["The quality of the underlying business",
             "How a company is currently being talked about and believed in",
             "Whether a stock is undervalued",
             "The company's future earnings"],
            1,
            "Sentiment measures belief, not reality. A company can be beloved and unprofitable, or "
            "excellent and ignored — sentiment reports the popularity in both cases, which is why it "
            "is one pillar of three rather than a verdict on its own.",
        ),
        QuizQuestion(
            "Why is sentiment VELOCITY tracked separately from the sentiment level?",
            ["Velocity is easier to compute",
             "The level is largely already reflected in the price, while a change is not",
             "Velocity is more accurate",
             "Regulators require it"],
            1,
            "If a company has been covered positively for months, that optimism is already in the price. "
            "The information that is not yet priced in is the shift — which is why the change is tracked "
            "as its own signal.",
        ),
        QuizQuestion(
            "Aureus weights sentiment at 40% for a short horizon but only 15% for a long one. Why?",
            ["Long-term data is harder to get",
             "Sentiment decays quickly — this quarter's mood says little about a business in five years",
             "Long-term investors don't read news",
             "It is an arbitrary choice"],
            1,
            "Sentiment has the shortest half-life of the three pillars. A news catalyst is fully absorbed "
            "within weeks, so it dominates short horizons and becomes close to noise over multi-year ones, "
            "where fundamentals do the work instead.",
        ),
    ],
    "l017": [
        QuizQuestion(
            "Why do general-purpose sentiment tools systematically misread financial filings?",
            ["Filings are too long",
             "Ordinary accounting words like 'liability', 'cost' and 'debt' sound negative in everyday English but are neutral in a filing",
             "Filings contain too many numbers",
             "They are written in legal language"],
            1,
            "This is the core failure and it has a direction: every company has liabilities and reports "
            "expenses, so a general model reads routine accounting description as distress and scores "
            "ordinary businesses negative.",
        ),
        QuizQuestion(
            "A general sentiment model scores 'the company did not beat estimates' as exactly neutral. What did it miss?",
            ["That 'company' is a positive word",
             "That 'beat estimates' is a decisive financial phrase, and 'did not' inverts it",
             "That estimates are always wrong",
             "Nothing — the sentence is neutral"],
            1,
            "Two failures at once: it does not recognise 'beat estimates' as a phrase carrying strong "
            "positive meaning, and it does not handle the negation that flips it. In financial text, short "
            "phrases carry far more signal than individual words.",
        ),
    ],
}


def quiz_for(lesson_id: str) -> list[QuizQuestion]:
    """Return the banked quiz for a lesson, or an empty list if none is authored."""
    return QUIZ_BANK.get(lesson_id, [])
