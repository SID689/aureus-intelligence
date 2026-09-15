"""
app/lessons/tier2_intermediate.py
-----------------------------------
TIER 2 — "Intermediate"

The bridge between Foundational+ and Advanced. Foundational+ explains why
familiar metrics mislead; Advanced assumes comfort with factor models and
greeks. This tier closes that gap.

Its organising theme is DOING THE WORK rather than knowing the term: how to
actually size a position, actually read a filing, actually build a valuation
under uncertainty, and actually measure whether a result was skill or noise.
Every lesson here should leave the reader able to perform a calculation or
a procedure, not just recognise a concept.

Quiz questions live in quizzes.py, keyed by lesson id.
"""

from app.lessons.models import Callout, GlossaryTerm, Lesson, QuizQuestion, TIER_INTERMEDIATE

TIER_2_INTERMEDIATE: list[Lesson] = [

    Lesson(
        id="i001",
        title="Position Sizing: The Math That Matters More Than Stock Picking",
        category="Risk Management",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=8,
        body=(
            "Most retail attention goes to WHAT to buy. Professional risk management is overwhelmingly "
            "concerned with HOW MUCH, because position size, not selection, determines whether a string "
            "of bad outcomes is a setback or a catastrophe.\n\n"

            "**The asymmetry of drawdowns.** Losses and gains are not symmetric, and the gap widens "
            "brutally as losses deepen. To recover from a 10% loss you need +11.1%. From 20%, +25%. From "
            "50%, +100%. From 80%, +400%. This is arithmetic, not opinion, and it's the entire reason "
            "professionals obsess over avoiding large drawdowns rather than maximising good years.\n\n"

            "**Risk per trade, not capital per trade.** The useful question isn't 'what percent of my "
            "portfolio is in this position' but 'what percent of my portfolio do I lose if this position "
            "hits my exit point.' Those are very different numbers.\n\n"
            "  position size = (portfolio × risk %) ÷ (entry price − stop price)\n\n"
            "With a $100,000 portfolio risking 1% ($1,000) on a stock entered at $50 with an exit at $45, "
            "the risk per share is $5, so the position is 200 shares: $10,000, or 10% of the portfolio. "
            "Change the exit to $48 and risk-per-share drops to $2, allowing 500 shares ($25,000). Same "
            "1% risk, very different capital committed. The stop distance, not a fixed percentage of "
            "capital, is what should drive size.\n\n"

            "**Why professionals cluster around 0.5–2% risk per position.** At 1% risk per position, ten "
            "consecutive losses costs roughly 10%: unpleasant but fully recoverable. At 10% risk per "
            "position, ten consecutive losses is a 65% drawdown requiring a 186% gain to recover. Given "
            "that even genuinely skilled strategies routinely produce losing streaks of five to ten, "
            "sizing must survive the streak, not the average.\n\n"

            "**Correlation makes 'diversified' positions one position.** Five separate 2% positions in "
            "five different semiconductor companies is not five independent 2% risks: during a sector "
            "selloff they move together, behaving much closer to a single 10% risk. Real position sizing "
            "requires accounting for correlated exposure across holdings, not just per-holding limits."
        ),
        key_takeaway=(
            "Size by risk-to-your-exit, not by percent of capital: position size = (portfolio × risk%) ÷ "
            "(entry − stop). Because recovering from deep drawdowns requires exponentially larger gains, "
            "sizing must survive a realistic losing streak, and correlated positions must be counted together."
        ),
        glossary=[
            GlossaryTerm("position sizing", "Deciding how much capital to commit to a trade, usually derived from how much you'd lose at your exit point."),
            GlossaryTerm("risk per trade", "The share of total portfolio value lost if a position reaches its predetermined exit."),
            GlossaryTerm("R-multiple", "A trade's profit or loss expressed in units of the amount initially risked. A +3R trade made three times what was risked."),
            GlossaryTerm("drawdown", "Decline from a prior peak. Recovery requires a larger percentage gain than the loss itself."),
            GlossaryTerm("correlated exposure", "Combined risk from positions that tend to move together, which behave as one larger position under stress."),
        ],
        callouts=[
            Callout("example", "Same risk, different capital",
                "$100,000 portfolio, 1% risk = $1,000 at stake. Entry $50 / stop $45 → $5 per share → 200 "
                "shares = $10,000 committed. Entry $50 / stop $48 → $2 per share → 500 shares = $25,000 "
                "committed. The tighter stop justifies a much larger position at identical portfolio risk."),
            Callout("why_it_matters", "Drawdown recovery is not symmetric",
                "-10% needs +11%. -25% needs +33%. -50% needs +100%. -75% needs +300%. Avoiding the deep "
                "hole matters far more than optimising the climb out, which is why risk limits bind before "
                "return targets do."),
        ],
        quiz=[],
    ),

    Lesson(
        id="i002",
        title="Discounted Cash Flow Without the False Precision",
        category="Valuation",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=8,
        body=(
            "A discounted cash flow model rests on one honest idea: a business is worth the cash it will "
            "produce for its owners, adjusted for the fact that cash arriving later is worth less than "
            "cash arriving today. Everything else is implementation detail, and the implementation "
            "details are where most DCFs quietly become fiction.\n\n"

            "**The mechanic.** Project free cash flow for a forecast period (commonly 5–10 years), "
            "discount each year back to today at a rate reflecting risk and opportunity cost, then add a "
            "terminal value capturing everything beyond the forecast window. Sum it, subtract net debt, "
            "divide by shares.\n\n"

            "**Why the terminal value is the problem.** In a typical 10-year DCF, the terminal value "
            "routinely accounts for 60–80% of total computed value. That means the majority of your "
            "'rigorous' answer comes from a single assumption about the perpetual growth rate: an input "
            "nobody can know. Worse, the standard perpetuity formula is violently sensitive near the "
            "discount rate: with a 9% discount rate, moving terminal growth from 2% to 3% raises terminal "
            "value by roughly 17%, and from 2% to 4% by roughly 40%. Small, defensible-sounding tweaks "
            "produce enormous swings.\n\n"

            "**Discount rate sensitivity compounds it.** Shifting the discount rate from 9% to 8% while "
            "holding everything else constant can lift fair value by 20% or more. Two competent analysts "
            "with the same forecasts and mildly different rate assumptions will produce materially "
            "different 'intrinsic values,' both fully defensible.\n\n"

            "**How to use a DCF honestly.** Not as a price target. Its real uses are:\n"
            "  1. **Ranges, not points.** Run pessimistic / base / optimistic and treat the output as a "
            "band. A single number implies precision the method cannot support.\n"
            "  2. **Reverse DCF**: the highest-value technique here. Instead of computing value from "
            "assumptions, take the CURRENT market price and solve for the growth rate that price implies. "
            "This converts an unanswerable question ('what's it worth?') into a tractable one ('is the "
            "market's implied 14% growth for a decade plausible for this business?'), which you can "
            "evaluate against industry data and history.\n"
            "  3. **Sensitivity tables**: show how value shifts across a grid of discount and growth "
            "rates, making the model's fragility explicit rather than hiding it behind one number.\n\n"

            "**When a DCF simply doesn't apply.** Pre-profit companies, businesses with wildly cyclical "
            "cash flows, banks (where debt is raw material rather than financing), and anything whose "
            "value depends on a binary outcome. Forcing a DCF onto these produces a number, but not "
            "information."
        ),
        key_takeaway=(
            "In a typical DCF most of the value sits in the terminal value, driven by an unknowable "
            "perpetual growth rate, so treat DCF output as a range, not a target. The most useful "
            "version is a reverse DCF: solve for the growth the current price already implies, then judge "
            "whether that's plausible."
        ),
        glossary=[
            GlossaryTerm("discounted cash flow", "Valuing a business as the present value of the cash it's expected to generate."),
            GlossaryTerm("free cash flow", "Cash from operations minus capital expenditures: cash genuinely available to capital providers."),
            GlossaryTerm("discount rate", "The rate used to convert future cash into present value, reflecting risk and opportunity cost."),
            GlossaryTerm("terminal value", "The value attributed to all cash flows beyond the explicit forecast window. Usually the majority of a DCF's output."),
            GlossaryTerm("perpetual growth rate", "The assumed forever-growth rate in the terminal value calculation. Must be below long-run economic growth to be coherent."),
            GlossaryTerm("reverse DCF", "Solving for the growth rate implied by the current market price instead of computing a value from assumed growth."),
            GlossaryTerm("net debt", "Total debt minus cash. Subtracted from enterprise value to reach equity value."),
        ],
        callouts=[
            Callout("common_mistake", "Reporting a DCF output as a precise price target",
                "'Fair value is $147.32' implies a precision the method cannot deliver when 70% of that "
                "number derives from a guessed perpetual growth rate. A defensible output is a range with "
                "its assumptions stated, not a figure to two decimal places."),
            Callout("key_idea", "Reverse the question",
                "Rather than asking 'what is this worth,' ask 'what does the current price already assume?' "
                "If the market implies 25% annual growth for ten years, you can check how many companies "
                "have historically sustained that. This is a question with an actual evidence base."),
        ],
        quiz=[],
    ),

    Lesson(
        id="i003",
        title="Reading a 10-K: Where the Real Information Hides",
        category="Fundamental Analysis",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=8,
        body=(
            "An annual report has two distinct halves: the part written to persuade you, and the part "
            "written because the law requires it. Almost all the analytical value is in the second half.\n\n"

            "**Skip the glossy front.** The shareholder letter and highlights section are marketing. They "
            "are not audited, they're written by people whose compensation depends on your impression, "
            "and they reliably emphasise favourable framings. Start at the legally-mandated sections.\n\n"

            "**Item 1A: Risk Factors.** Much of this is boilerplate that every company in the industry "
            "files. The signal is in what CHANGED. A newly added risk factor, or one moved higher in the "
            "ordering, reflects something management and counsel concluded they now had to disclose. "
            "Diffing this section year over year is one of the highest-yield habits in fundamental "
            "analysis: it surfaces deterioration before it reaches the income statement.\n\n"

            "**Item 7: MD&A.** Management's own explanation of results. Read it for the reasons given "
            "for changes, and specifically watch for shifting metrics: a company that reported GAAP "
            "operating income last year and leads with 'adjusted EBITDA' this year has usually changed "
            "the metric because the old one stopped looking good.\n\n"

            "**Item 8: Financial Statements and the notes.** The statements themselves are summaries; "
            "the notes are where the substance is. Revenue recognition policy tells you when a sale "
            "becomes revenue, which determines how aggressive the top line is. Segment reporting shows "
            "which business lines actually generate profit versus which are subsidised by others. "
            "Off-balance-sheet commitments, lease obligations, and contingent liabilities are disclosed "
            "here and nowhere else.\n\n"

            "**Cross-check accruals against cash.** The most reliable single red flag available to a "
            "retail analyst: net income growing steadily while operating cash flow stagnates or declines. "
            "Earnings involve judgment; cash is comparatively hard to manufacture. A widening, persistent "
            "gap between the two means profit is being recognised faster than cash arrives, sometimes "
            "legitimate (a genuinely growing business extending credit), sometimes the earliest visible "
            "symptom of aggressive accounting.\n\n"

            "**Watch dilution.** Compare shares outstanding across several years. A company growing net "
            "income 10% annually while issuing 8% more shares annually is delivering roughly 2% growth "
            "per share: the number that actually accrues to you. Heavy stock-based compensation makes "
            "this common in technology and easy to miss if you only track headline totals."
        ),
        key_takeaway=(
            "The analytical value in a 10-K is in the mandated sections, not the shareholder letter. Diff "
            "Item 1A risk factors year over year, read the notes rather than the summary statements, and "
            "check net income against operating cash flow and share count: profit per SHARE is what you own."
        ),
        glossary=[
            GlossaryTerm("10-K", "The comprehensive annual report US public companies must file with the SEC."),
            GlossaryTerm("MD&A", "Management's Discussion and Analysis: management's narrative explanation of financial results."),
            GlossaryTerm("accruals", "The gap between reported earnings and actual cash flow, arising from timing-based accounting."),
            GlossaryTerm("revenue recognition", "The accounting policy determining when a sale is booked as revenue. A key lever for aggressiveness."),
            GlossaryTerm("segment reporting", "A breakdown of results by business line, revealing which segments actually generate profit."),
            GlossaryTerm("dilution", "The reduction in existing shareholders' ownership share when a company issues additional shares."),
            GlossaryTerm("contingent liability", "A potential obligation that depends on a future event, such as pending litigation."),
        ],
        callouts=[
            Callout("key_idea", "Diff the risk factors",
                "Year-over-year changes in Item 1A are among the most underused signals in public filings. "
                "Companies rarely add a risk factor voluntarily: a new one usually means counsel decided "
                "it had become material enough to require disclosure."),
            Callout("common_mistake", "Tracking net income while ignoring share count",
                "Total profit growing 10% while share count grows 8% is roughly 2% growth for existing "
                "owners. Per-share figures are what you actually own; headline totals can mask persistent "
                "dilution from stock-based compensation."),
        ],
        quiz=[],
    ),

    Lesson(
        id="i004",
        title="Expected Value: Why Win Rate Is a Misleading Statistic",
        category="Quantitative",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=6,
        body=(
            "Win rate, the percentage of trades that were profitable, is the most quoted and least "
            "informative performance statistic in retail investing. A 90% win rate can be a losing "
            "strategy and a 35% win rate can be an excellent one, because win rate says nothing about "
            "the SIZE of wins versus losses.\n\n"

            "**Expected value is the actual measure.**\n"
            "  EV = (win rate × average win) − (loss rate × average loss)\n\n"
            "Strategy A wins 90% of the time, averaging +$100, and loses 10% of the time, averaging "
            "−$1,200. EV = (0.9 × 100) − (0.1 × 1200) = 90 − 120 = **−$30 per trade.** It feels good "
            "almost every time and loses money reliably.\n\n"
            "Strategy B wins 35% of the time, averaging +$500, and loses 65% averaging −$150. "
            "EV = (0.35 × 500) − (0.65 × 150) = 175 − 97.5 = **+$77.50 per trade.** It feels bad most "
            "days and is clearly superior.\n\n"

            "**Why high win rates attract capital anyway.** Strategy A's shape: frequent small gains, "
            "rare large losses: is psychologically comfortable and produces an impressive-looking track "
            "record right up until the tail event. This payoff profile is common in strategies that sell "
            "options, sell insurance, or bet against volatility, and it's why 'consistent' returns "
            "deserve scrutiny about what happens in the bad state rather than admiration.\n\n"

            "**Sample size and the streak problem.** A genuinely positive-EV strategy that wins 35% of "
            "the time will produce a run of eight straight losses with meaningful regularity: that's "
            "roughly a 3% probability on any given eight-trade window, which over hundreds of trades is "
            "close to inevitable. Abandoning a sound strategy during a statistically ordinary losing "
            "streak is one of the most common ways good processes get discarded.\n\n"

            "**Thinking in R.** Expressing results as R-multiples: profit or loss in units of the amount "
            "risked: makes strategies comparable across position sizes. A strategy averaging +0.3R over "
            "many trades is profitable regardless of whether R is $100 or $10,000, and the R framing "
            "makes it obvious when a single oversized loss has distorted results."
        ),
        key_takeaway=(
            "Win rate is nearly meaningless alone: EV = (win rate × avg win) − (loss rate × avg loss). A "
            "90%-win strategy with rare huge losses can be negative-EV, while a 35%-win strategy with "
            "large winners can be strongly positive. Judge the payoff distribution, not the hit rate."
        ),
        glossary=[
            GlossaryTerm("expected value", "The probability-weighted average outcome per trade. The correct headline measure of an edge."),
            GlossaryTerm("win rate", "Percentage of trades that were profitable. Uninformative without average win and loss sizes."),
            GlossaryTerm("payoff ratio", "Average win divided by average loss. Combined with win rate, determines expected value."),
            GlossaryTerm("R-multiple", "Result expressed in units of initial risk, making outcomes comparable across position sizes."),
            GlossaryTerm("tail risk", "Risk of rare, extreme outcomes, often concealed by strategies with very high win rates."),
        ],
        callouts=[
            Callout("example", "A 90% win rate that loses money",
                "Win 90% of the time at +$100, lose 10% of the time at −$1,200. Per 100 trades: 90 wins × "
                "$100 = +$9,000; 10 losses × $1,200 = −$12,000. Net −$3,000 despite winning nine times out "
                "of ten. The hit rate was never the relevant number."),
            Callout("why_it_matters", "Ordinary streaks look like broken strategies",
                "At a 35% win rate, eight consecutive losses occurs with roughly 3% probability per window "
                ": effectively certain to happen repeatedly over a few hundred trades. Distinguishing an "
                "expected streak from genuine strategy decay requires knowing the distribution in advance."),
        ],
        quiz=[],
    ),

    Lesson(
        id="i005",
        title="What an Index Fund Actually Owns (and Why Weighting Decides Your Risk)",
        category="Portfolio Theory",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=6,
        body=(
            "'Buy the index' is sound advice that hides a consequential design decision: the weighting "
            "scheme. Two funds tracking the same 500 companies can behave quite differently depending on "
            "how much of each they hold.\n\n"

            "**Market-cap weighting is the default, and it's momentum by construction.** In a cap-weighted "
            "index, each company's weight equals its share of total market value. As a stock rises, its "
            "weight automatically rises with it: you hold more of what has already gone up, without ever "
            "placing a trade. This is a feature (it's self-rebalancing and low-turnover, which keeps costs "
            "and taxes down) and a risk (concentration builds silently during a sustained run).\n\n"

            "**Concentration is the practical consequence.** In recent years the largest handful of "
            "companies has represented an unusually large share of the S&P 500's total weight by "
            "historical standards. An investor holding 'the whole market' can therefore have a much larger "
            "effective bet on a small number of correlated mega-cap technology companies than the phrase "
            "'diversified across 500 companies' suggests. Checking a fund's top-ten weight is a two-minute "
            "task that materially changes your understanding of what you own.\n\n"

            "**Equal weighting is a different strategy wearing the same label.** An equal-weighted S&P 500 "
            "fund holds 0.2% of each company regardless of size, which tilts meaningfully toward smaller "
            "companies and requires regular rebalancing (higher turnover, higher costs, more taxable "
            "events). It is neither better nor worse in the abstract: it is a distinct set of exposures "
            "that will diverge from the cap-weighted version, sometimes for years.\n\n"

            "**Tracking difference is the honest cost measure.** The expense ratio is the advertised fee, "
            "but total real-world cost also includes trading costs from rebalancing, cash drag, and "
            "securities-lending revenue offsetting fees. Comparing a fund's actual return to its index's "
            "return, the tracking difference, captures all of it in one number, which the headline "
            "expense ratio does not.\n\n"

            "**Index membership is a committee decision.** Index providers apply rules and judgment about "
            "inclusion. When a company joins a major index, funds tracking it must buy: creating "
            "documented, predictable demand around rebalance dates. 'Passive' investing is passive with "
            "respect to your decisions, not with respect to the index provider's."
        ),
        key_takeaway=(
            "Cap-weighted index funds automatically hold more of whatever has already risen, so "
            "'diversified across 500 companies' can still mean heavy concentration in a few correlated "
            "mega-caps: check the top-ten weight. Compare funds on tracking difference, not just the "
            "advertised expense ratio."
        ),
        glossary=[
            GlossaryTerm("market-cap weighting", "Weighting each index holding by its share of total market value: the default scheme for most major indices."),
            GlossaryTerm("equal weighting", "Holding the same dollar amount of every constituent, requiring periodic rebalancing."),
            GlossaryTerm("expense ratio", "The advertised annual fee of a fund, expressed as a percentage of assets."),
            GlossaryTerm("tracking difference", "The actual gap between a fund's return and its index's return, capturing all real costs."),
            GlossaryTerm("turnover", "How much of a fund's holdings are traded per year. Higher turnover means higher costs and more taxable events."),
            GlossaryTerm("concentration risk", "Risk from a large share of a portfolio sitting in a few holdings or one correlated group."),
        ],
        callouts=[
            Callout("key_idea", "Cap weighting is a momentum tilt you didn't choose",
                "Because weight tracks market value, a cap-weighted fund mechanically increases its "
                "allocation to winners and decreases it in losers with no trading. That's efficient and "
                "cheap, and it means concentration quietly grows during a long run in a few names."),
            Callout("why_it_matters", "Check the top-ten weight before assuming diversification",
                "It takes two minutes on any fund's fact sheet and frequently reveals that a nominally "
                "500-company portfolio has a large share of its risk in a handful of correlated names."),
        ],
        quiz=[],
    ),

    Lesson(
        id="i006",
        title="Interest Rates: The Gravity Behind Every Asset Price",
        category="Macro",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=7,
        body=(
            "Interest rates influence virtually every asset price through one mechanism: they set the "
            "rate at which future money is converted into present money. Warren Buffett's framing, that "
            "rates act on asset values like gravity acts on matter: is unusually precise rather than "
            "merely poetic.\n\n"

            "**The discounting channel.** An asset's value is the present value of its future cash flows. "
            "Raise the discount rate and every future dollar is worth less today, so present value falls "
            ": mechanically, before any change in the business itself.\n\n"

            "**Duration explains which assets fall hardest.** The further into the future an asset's cash "
            "flows sit, the more sensitive its present value is to rate changes. A profitable utility "
            "generating steady cash now is relatively insensitive. An unprofitable growth company whose "
            "value depends on large cash flows a decade out is extremely sensitive: the same rate move "
            "compounds across many more discounting periods. This is why rising-rate environments hit "
            "long-duration growth equities disproportionately, while the underlying businesses may be "
            "entirely unchanged. It is a repricing of time, not a verdict on the company.\n\n"

            "**The competition channel.** Rates set the return available on the risk-free alternative. "
            "When Treasury bills yield near zero, an equity earning 5% looks compelling. When bills yield "
            "5%, that same equity must justify its additional risk against a genuinely competitive "
            "riskless option. Higher rates raise the hurdle every risk asset must clear.\n\n"

            "**The real-economy channel, with a lag.** Rate changes affect borrowing costs for mortgages, "
            "corporate debt, and capital projects, but that transmission takes quarters, not days. This "
            "lag is why markets can react instantly to a rate decision while the economic consequences "
            "arrive much later, and why the two are frequently mistaken for each other.\n\n"

            "**Expectations, not levels, drive the move.** Markets price in anticipated rate paths "
            "continuously. A rate hike that was fully expected often produces little reaction, while an "
            "unchanged rate accompanied by unexpectedly hawkish commentary can move markets sharply. What "
            "matters is the surprise relative to what was already priced, which is why 'rates went up "
            "but stocks rallied' is not a paradox.\n\n"

            "**Real versus nominal.** The nominal rate minus expected inflation gives the real rate, and "
            "real rates are what govern actual economic decisions. A 6% nominal rate with 5% inflation is "
            "materially looser than a 3% nominal rate with 0.5% inflation, despite the higher headline."
        ),
        key_takeaway=(
            "Rates set the conversion rate between future and present money, so higher rates mechanically "
            "reduce asset values: hardest for long-duration assets whose cash flows are far in the future. "
            "Markets respond to the SURPRISE versus what was already priced, not the level itself."
        ),
        glossary=[
            GlossaryTerm("discount rate", "The rate converting future cash flows into present value. Rises with interest rates."),
            GlossaryTerm("duration (equity)", "How far in the future an asset's cash flows sit. Longer duration means greater rate sensitivity."),
            GlossaryTerm("risk-free rate", "The return on government debt considered free of default risk: the baseline every risk asset competes against."),
            GlossaryTerm("real interest rate", "The nominal rate minus expected inflation. What actually governs economic decisions."),
            GlossaryTerm("hawkish / dovish", "Hawkish favours tighter policy (higher rates); dovish favours looser policy."),
            GlossaryTerm("priced in", "Already reflected in market prices, so only deviations from the expectation move markets."),
        ],
        callouts=[
            Callout("key_idea", "Rate moves reprice time, not business quality",
                "When rising rates crush a long-duration growth stock, nothing about the company has "
                "necessarily changed. The market has repriced how much its distant future cash is worth "
                "today. Distinguishing repricing from deterioration is central to intermediate analysis."),
            Callout("common_mistake", "Expecting a hike to always sink stocks",
                "If a hike is fully anticipated it's already in prices, and markets can rally on the "
                "accompanying guidance. Direction of surprise beats direction of policy."),
        ],
        quiz=[],
    ),

    Lesson(
        id="i007",
        title="Survivorship Bias and Why Most Backtests Are Optimistic",
        category="Quantitative",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=6,
        body=(
            "Before trusting any historical performance claim, your own or someone else's, it's worth "
            "knowing the specific ways historical data systematically flatters strategies.\n\n"

            "**Survivorship bias.** A dataset containing only companies that exist today has silently "
            "deleted every company that went bankrupt, was delisted, or was acquired in distress. "
            "Backtesting 'the S&P 500's current members over 20 years' measures the performance of "
            "companies selected partly for having survived: a criterion unavailable to anyone investing "
            "20 years ago. The same problem afflicts mutual fund databases, where closed and merged funds "
            "vanish, inflating the apparent average performance of the category.\n\n"

            "**Look-ahead bias.** Using information in a backtest that wasn't available at the simulated "
            "decision time. The most common form is subtle: financial statement data is timestamped to "
            "the fiscal period it describes, but wasn't public until the filing date weeks or months "
            "later. A backtest keyed to period end rather than filing date is trading on information "
            "nobody had.\n\n"

            "**Restatement bias.** Financial databases often store the LATEST restated figures rather "
            "than what was originally reported. A strategy screening on historical earnings may be using "
            "corrected numbers that only became known after the fact.\n\n"

            "**Data mining and multiple comparisons.** Test enough rules against the same history and "
            "some will look excellent through chance alone. Testing 100 variations and reporting the best "
            "produces an impressive result even with zero real edge: this is a statistical certainty, "
            "not a possibility. The published result is the maximum of many draws, not a typical draw.\n\n"

            "**Ignoring costs.** Backtests that omit commissions, bid-ask spreads, slippage, and taxes "
            "systematically overstate returns, and the distortion scales with turnover. A strategy trading "
            "daily can look strong gross and be clearly unprofitable net.\n\n"

            "**Practical defenses.** Reserve a holdout period never examined during development. Prefer "
            "point-in-time data. Count and disclose how many variations you tested. Model realistic costs. "
            "Most usefully: prefer strategies with a mechanistic explanation for WHY the edge should "
            "exist: a pattern with no plausible cause is far more likely to be an artifact of the sample."
        ),
        key_takeaway=(
            "Historical data flatters strategies through survivorship, look-ahead, and restatement bias, "
            "and testing many variations guarantees a good-looking best result even with no real edge. "
            "Use point-in-time data, hold out a period, model costs, and prefer edges with a mechanism."
        ),
        glossary=[
            GlossaryTerm("survivorship bias", "Distortion from analysing only entities that survived, excluding those that failed or were delisted."),
            GlossaryTerm("look-ahead bias", "Using information in a simulation that wasn't actually available at the decision time."),
            GlossaryTerm("point-in-time data", "Data reflecting exactly what was known and published on a given historical date."),
            GlossaryTerm("restatement bias", "Using later-corrected financial figures rather than what was originally reported."),
            GlossaryTerm("overfitting", "Tuning a model so closely to historical data that it captures noise rather than a durable pattern."),
            GlossaryTerm("holdout period", "Data deliberately excluded during development, reserved to test the final strategy once."),
        ],
        callouts=[
            Callout("common_mistake", "Backtesting an index's CURRENT members",
                "Today's S&P 500 constituents were partly selected by having survived and succeeded. "
                "Running them back 20 years measures a portfolio nobody could have assembled 20 years ago."),
            Callout("why_it_matters", "The best of 100 tests is not a typical result",
                "If you test 100 parameter sets, the top performer is the maximum of 100 random draws. "
                "That's expected to look good even with zero skill, which is why the number of variations "
                "tested is itself a required disclosure in serious quantitative work."),
        ],
        quiz=[],
    ),
]
