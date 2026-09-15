"""
app/lessons/tier2_intermediate_b.py
-------------------------------------
TIER 2 — "Intermediate", continued.

The bridge to professional analysis. These assume the reader can already
place trades, read a quote and follow a cash flow statement, and are
ready to do the work rather than read about it — which is why this batch
leans heavily on numeric drills and interactive exercises rather than
prose alone.

Covers the ground the original seven did not: risk-adjusted comparison,
the mechanics of rebalancing, why revenue quality differs from revenue,
the base-rate problem in stock selection, how buybacks actually work,
capital structure, currency exposure, and the difference between an
earnings model and a forecast.
"""

from app.lessons.models import (
    Callout, Checkpoint, Exercise, GlossaryTerm, Lesson, NumericQuestion,
    QuizQuestion, TIER_INTERMEDIATE,
)

TIER_2_INTERMEDIATE_B: list[Lesson] = [

    # ── i008 ──────────────────────────────────────────────────────────────
    Lesson(
        id="i008",
        title="Risk-Adjusted Returns: Comparing Things That Aren't Comparable",
        category="Risk Management",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=8,
        body=(
            "Two strategies returned 12% last year. One did it with quiet 4% swings, the other by "
            "falling 30% in March and recovering. Reporting both as '12%' is technically accurate "
            "and analytically useless. Risk-adjusted measures exist to make that comparison "
            "possible, and each of them is wrong in a specific way worth knowing.\n\n"

            "**Sharpe ratio.** Excess return over the risk-free rate, divided by standard "
            "deviation. It answers: how much return per unit of volatility? A Sharpe of 1.0 is "
            "good, 2.0 is excellent and usually means either a short sample or something "
            "undisclosed about the risk being taken.\n\n"

            "**Where Sharpe misleads.** It treats upside and downside volatility identically. A "
            "strategy that occasionally gains 20% in a month is penalised exactly as much as one "
            "that occasionally loses 20%, which is not how anyone actually experiences those "
            "outcomes. Worse, Sharpe rewards strategies that produce steady small gains and rare "
            "catastrophic losses, because the catastrophe has not happened yet within the sample. "
            "Selling deep out-of-the-money options produces a beautiful Sharpe ratio right up "
            "until it produces a margin call.\n\n"

            "**Sortino ratio.** The same idea using only downside deviation, so upside volatility "
            "is not treated as risk. More faithful to how risk feels, and it still says nothing "
            "about the losses that have not occurred yet.\n\n"

            "**Maximum drawdown.** The largest peak-to-trough decline over the period. Cruder than "
            "the ratios and often more useful, because it is the number that determines whether "
            "an investor actually stayed invested. A strategy with a 0.9 Sharpe and a 55% "
            "drawdown is, for most humans, worse than one with a 0.7 Sharpe and a 20% drawdown, "
            "regardless of what the ratios say.\n\n"

            "**Calmar ratio.** Annualised return divided by maximum drawdown: return per unit of "
            "worst-case pain. Blunt, and closer to the question people actually care about.\n\n"

            "**The sample-length problem underneath all of them.** Every one of these is estimated "
            "from a finite history, and the estimate is noisy. Distinguishing a genuine Sharpe of "
            "1.0 from a lucky 0.5 takes many years of data: more than most strategies have. A "
            "three-year Sharpe is close to a coin flip about the underlying quality, which is why "
            "professional allocators look at the drawdown chart before the ratio table."
        ),
        key_takeaway=(
            "Sharpe penalises upside volatility as if it were risk and cannot see losses that have "
            "not happened yet, which is why option-selling strategies look excellent until they "
            "don't. Maximum drawdown is cruder and often more honest, because it predicts whether "
            "you actually stayed invested."
        ),
        glossary=[
            GlossaryTerm("Sharpe ratio", "Excess return over the risk-free rate divided by standard deviation. Treats upside and downside volatility identically."),
            GlossaryTerm("Sortino ratio", "Like Sharpe but dividing only by downside deviation, so gains are not counted as risk."),
            GlossaryTerm("maximum drawdown", "The largest peak-to-trough decline over a period. The number that best predicts whether an investor abandoned a strategy."),
            GlossaryTerm("Calmar ratio", "Annualised return divided by maximum drawdown: return per unit of worst-case loss."),
            GlossaryTerm("risk-free rate", "The return on a supposedly riskless asset, usually short-term government bills, used as the baseline for excess return."),
        ],
        callouts=[
            Callout("common_mistake", "Trusting a short-sample Sharpe",
                "Sharpe estimated over three years carries enormous error. A strategy reporting 1.8 over "
                "that window is frequently a 0.6 strategy that had a good run, and the difference is "
                "invisible until the sample extends."),
            Callout("why_it_matters", "The shape of a return stream is selectable",
                "A manager can engineer a smooth-looking track record by accepting rare large losses. "
                "Sharpe rewards exactly that shape. Always ask what the worst month looked like, and what "
                "would have to happen for a much worse one to occur."),
        ],
        practice=[
            NumericQuestion(
                question="A strategy returned 14% with 16% standard deviation. The risk-free rate is 4%. What is its Sharpe ratio?",
                answer=0.625, tolerance=0.02,
                hint="Excess return over the risk-free rate, divided by standard deviation.",
                explanation=(
                    "(14% - 4%) / 16% = 0.625. Note how sensitive this is to the risk-free rate: if it were "
                    "1%, the same strategy would report 0.81. Comparing Sharpe ratios computed in different "
                    "rate environments is a common and quiet error."
                ),
            ),
            NumericQuestion(
                question="A portfolio peaks at $240,000 and falls to $156,000 before recovering. What is the maximum drawdown, as a percentage?",
                answer=35, tolerance=0.5,
                unit="%",
                hint="Measured from the peak, not from the starting value.",
                explanation=(
                    "($240,000 - $156,000) / $240,000 = 35%. Recovering from that requires a 53.8% gain on "
                    "the remaining balance, which is why drawdown, not volatility, is what determines "
                    "whether people stay invested."
                ),
            ),
        ],
        exercises=[
            Exercise(
                kind="drawdown_recovery",
                title="Drawdown and the gain required to undo it",
                prompt=(
                    "Set the loss to 35% and read the recovery required. Then try 50% and 70%. The "
                    "convexity here is the reason risk management concentrates on avoiding large losses "
                    "rather than on capturing large gains."
                ),
                params={"loss_pct": 35},
            ),
        ],
        quiz=[
            QuizQuestion(
                "Why can a strategy that sells far out-of-the-money options show an excellent Sharpe ratio?",
                ["Options have no volatility", "It produces steady small gains, and the rare large loss has not occurred within the sample",
                 "Sharpe excludes derivatives", "Option premiums are risk-free"],
                1,
                "Sharpe measures realised volatility over the observed period. A strategy whose risk is "
                "concentrated in rare events looks superb until one occurs: the ratio cannot price a loss "
                "that has not happened yet.",
            ),
            QuizQuestion(
                "What is the main criticism of Sharpe as a risk measure?",
                ["It ignores the risk-free rate", "It penalises upside volatility exactly as much as downside",
                 "It cannot be computed for equities", "It requires daily data"],
                1,
                "Standard deviation is symmetric. A month of unusually large gains raises measured 'risk' "
                "and lowers the ratio, which does not match anyone's actual experience of risk.",
            ),
            QuizQuestion(
                "Why do allocators often look at maximum drawdown before the ratio table?",
                ["It is easier to compute", "It best predicts whether an investor will actually stay invested",
                 "It is required by regulation", "Ratios are unreliable below 1.0"],
                1,
                "The best strategy is worth nothing if its holder abandons it at the bottom. Drawdown is "
                "the number that determines that, which makes it more practically informative than a "
                "smoother statistic.",
            ),
        ],
    ),

    # ── i009 ──────────────────────────────────────────────────────────────
    Lesson(
        id="i009",
        title="Rebalancing: The Only Free Lunch You Have to Work For",
        category="Portfolio Theory",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=7,
        body=(
            "You choose 60% stocks and 40% bonds. Three years later stocks have run and you hold "
            "74/26. You did nothing, yet your portfolio is meaningfully riskier than the one you "
            "chose. Rebalancing is the act of returning to the allocation you actually decided on.\n\n"

            "**Drift is the default, and it always drifts toward risk.** Whatever has performed "
            "best grows as a share of the portfolio. So an unrebalanced portfolio automatically "
            "concentrates into whatever has recently risen, which is exactly the position you "
            "least want going into a reversal. Doing nothing is not neutral; it is a decision to "
            "let recent performance set your risk.\n\n"

            "**Why it feels wrong every single time.** Rebalancing means selling what has done "
            "well to buy what has done badly. It always feels like a mistake, and in any given "
            "year it frequently is: in a sustained bull market, rebalancing out of equities "
            "reduces returns. Its value is not in average return; it is in controlling the risk "
            "you carry into the years you cannot predict.\n\n"

            "**Calendar versus threshold.** Calendar rebalancing acts on a schedule: annually, "
            "say. Threshold rebalancing acts when an allocation drifts more than a set distance "
            "from target, such as five percentage points. Threshold responds to what actually "
            "happened rather than to the calendar, and generally trades less. Both work; what "
            "matters far more is having a rule at all, since the alternative is deciding while "
            "emotionally involved.\n\n"

            "**Rebalancing frequently is not better.** More frequent rebalancing means more "
            "trading, more spread paid, and in taxable accounts more realized gains. It also cuts "
            "short momentum, which is a real effect over months. Annual or threshold-based is a "
            "reasonable default; monthly is usually cost without benefit.\n\n"

            "**Where to do it.** Rebalance inside tax-advantaged accounts first, where selling "
            "triggers nothing. In taxable accounts, direct new contributions toward the "
            "underweight asset instead of selling the overweight one: you reach the same "
            "allocation with no realized gain at all. That single habit removes most of the tax "
            "cost of maintaining a target."
        ),
        key_takeaway=(
            "An unrebalanced portfolio drifts automatically into whatever has recently risen, so "
            "doing nothing is a decision to let past performance set your risk. Rebalance with "
            "new contributions in taxable accounts and you get the allocation back with no "
            "realized gain."
        ),
        glossary=[
            GlossaryTerm("rebalancing", "Selling what has grown beyond its target weight and buying what has fallen below it, to restore a chosen allocation."),
            GlossaryTerm("drift", "The gradual change in portfolio weights caused by differing returns, always toward whatever performed best."),
            GlossaryTerm("threshold rebalancing", "Acting when an allocation moves a set distance from target, rather than on a schedule."),
            GlossaryTerm("target allocation", "The mix of assets you deliberately chose, as opposed to the mix you now hold."),
        ],
        callouts=[
            Callout("key_idea", "Rebalancing is risk control, not return enhancement",
                "In a long bull market it will cost you return. That is not a failure of the technique: "
                "it is the premium you pay for not arriving at the next downturn holding far more equity "
                "than you intended."),
            Callout("example", "Drift in practice",
                "60/40 with equities compounding at 10% and bonds at 3% for five years drifts to roughly "
                "70/30. An investor who chose 60/40 for its ~25% worst-case drawdown is now carrying "
                "closer to 30%, without ever making a decision."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=1,
                question="Your 60/40 portfolio has drifted to 75/25 after a strong equity run. What does that mean about your risk?",
                options=[
                    "It is unchanged, since you did not trade",
                    "It is lower, because equities are performing well",
                    "It is higher than the level you chose, and you never decided to take it",
                    "It cannot be assessed without knowing which equities",
                ],
                correct_index=2,
                explanation=(
                    "Risk follows the weights, not your intentions. Drift silently moved you to an "
                    "allocation you would probably not have chosen deliberately."
                ),
            ),
        ],
        practice=[
            NumericQuestion(
                question="A $500,000 portfolio targets 60% equities but currently holds $355,000 in equities. How many dollars of equities must be sold to return to target?",
                answer=55000, tolerance=500,
                unit="$",
                hint="Work out the target dollar amount first, then the difference.",
                explanation=(
                    "Target equity is $500,000 x 0.60 = $300,000. Current is $355,000, so $55,000 is sold. "
                    "In a taxable account, directing the next $55,000 of contributions into bonds instead "
                    "reaches the same weights with no realized gain."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Why does an unrebalanced portfolio become riskier over time?",
                ["Volatility rises with age", "The best-performing asset grows as a share, concentrating the portfolio into what recently rose",
                 "Fees compound", "Correlations decay"],
                1,
                "Drift is mechanical. Whatever went up becomes a larger fraction, so the portfolio "
                "automatically ends up most concentrated in whatever has run hardest.",
            ),
            QuizQuestion(
                "What is the most tax-efficient way to rebalance a taxable account?",
                ["Sell the overweight asset in December", "Direct new contributions into the underweight asset",
                 "Sell everything and rebuild", "Rebalance monthly to keep amounts small"],
                1,
                "Buying the underweight asset with new money reaches the target allocation without "
                "realizing any gain, avoiding the tax cost of selling the appreciated holding entirely.",
            ),
            QuizQuestion(
                "Why is monthly rebalancing usually worse than annual?",
                ["It is mathematically incorrect", "More trading costs, more realized gains, and it cuts short momentum that persists over months",
                 "Brokers prohibit it", "It increases drift"],
                1,
                "Higher frequency adds spread and tax cost while interrupting a real medium-term momentum "
                "effect. The extra precision buys very little.",
            ),
        ],
    ),

    # ── i010 ──────────────────────────────────────────────────────────────
    Lesson(
        id="i010",
        title="Revenue Quality: Not All Growth Is Worth the Same",
        category="Fundamental Analysis",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=8,
        body=(
            "Two companies both grew revenue 25%. One added recurring subscriptions from customers "
            "who renew at 95%. The other signed three large one-off contracts and offered "
            "extended payment terms to close them. The income statement reports the same growth "
            "rate. They are not the same business.\n\n"

            "**Recurring versus one-off.** Revenue that repeats without being re-won is worth a "
            "multiple of revenue that must be re-sold every period. This is the main reason "
            "software companies trade at higher multiples than project-based engineering firms "
            "with identical growth: the market is pricing the persistence, not the level.\n\n"

            "**Concentration.** A company where one customer is 40% of revenue has an entirely "
            "different risk profile from one with ten thousand customers, at the same growth rate. "
            "The 10-K discloses any customer above 10% of revenue. It is one of the most "
            "informative disclosures in the filing and one of the least read.\n\n"

            "**Days sales outstanding, and why it matters.** DSO is how long, on average, a "
            "company waits to be paid. Rising DSO alongside rising revenue is a specific warning: "
            "it often means sales are being pulled forward with easier terms, or that customers "
            "are struggling. Revenue is booked at the sale; cash arrives later, and sometimes it "
            "does not arrive at all.\n\n"

            "**The receivables-versus-revenue test.** If receivables grow materially faster than "
            "revenue over several quarters, the company is booking sales it has not collected. "
            "That divergence precedes a large share of accounting restatements. It takes about "
            "two minutes to check and almost nobody does it.\n\n"

            "**Deferred revenue as a positive signal.** Deferred revenue is cash collected for a "
            "service not yet delivered: a liability on the balance sheet that is genuinely good "
            "news. Customers paid in advance. Growing deferred revenue alongside growing revenue "
            "is among the healthiest patterns available, and it is the mirror image of the "
            "receivables warning.\n\n"

            "**Organic versus acquired.** A company growing 20% by buying companies is doing "
            "something different from one growing 20% by selling more. Acquired growth costs "
            "capital, carries integration risk, and can be sustained only as long as targets and "
            "financing exist. Most companies disclose the split; the headline rate never does."
        ),
        key_takeaway=(
            "Receivables growing materially faster than revenue means sales are being booked but "
            "not collected: a two-minute check that precedes a large share of restatements. "
            "Deferred revenue growing is the healthy mirror image: customers paying in advance."
        ),
        glossary=[
            GlossaryTerm("recurring revenue", "Revenue that repeats without being re-won each period, such as subscriptions. Valued at a higher multiple than one-off sales."),
            GlossaryTerm("customer concentration", "The share of revenue from the largest customers. Any customer above 10% must be disclosed in the 10-K."),
            GlossaryTerm("days sales outstanding", "Average days between making a sale and collecting cash. Rising DSO with rising revenue is a warning."),
            GlossaryTerm("accounts receivable", "Money owed by customers for sales already booked as revenue but not yet collected."),
            GlossaryTerm("deferred revenue", "Cash collected before delivering the service. A liability on the balance sheet, and a genuinely positive signal."),
        ],
        callouts=[
            Callout("common_mistake", "Comparing growth rates without comparing quality",
                "Screening for '20%+ revenue growth' treats a subscription business and a lumpy contract "
                "business as equivalent. They will not behave equivalently in a downturn, when one renews "
                "and the other has to re-sell everything."),
            Callout("example", "The receivables divergence",
                "Revenue +18%, receivables +47% over the same year. Either collection has deteriorated "
                "sharply or sales were pulled forward with generous terms. Both mean next year's growth "
                "borrowed from itself."),
        ],
        practice=[
            NumericQuestion(
                question="A company has annual revenue of $730 million and accounts receivable of $180 million. What is its DSO, in days?",
                answer=90, tolerance=2,
                unit="days",
                hint="Receivables divided by revenue per day. Use a 365-day year.",
                explanation=(
                    "Revenue per day is $730m / 365 = $2m. $180m / $2m = 90 days. Whether 90 is good depends "
                    "on the industry, but a move from 60 to 90 over a year is a serious deterioration "
                    "regardless of the absolute level."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Receivables grow 45% while revenue grows 15%. What does this most likely indicate?",
                ["Unusually strong demand", "Sales are being booked faster than they are collected: possibly looser terms or struggling customers",
                 "The company is paying suppliers faster", "Deferred revenue is rising"],
                1,
                "Revenue is recognised at the sale; receivables are the uncollected portion. Growing much "
                "faster than revenue means an increasing share of reported sales is not yet cash, and may "
                "never be.",
            ),
            QuizQuestion(
                "Why is rising deferred revenue generally a positive sign despite being a liability?",
                ["It reduces taxes", "It means customers paid in advance for services not yet delivered",
                 "It offsets receivables", "It signals an upcoming acquisition"],
                1,
                "Deferred revenue is cash already in hand for future obligations. It is the opposite of the "
                "receivables problem: the money arrived before the work.",
            ),
            QuizQuestion(
                "Two companies each grew revenue 22%. One did it organically, one through acquisitions. What differs?",
                ["Nothing meaningful", "Acquired growth consumes capital, carries integration risk, and requires a continuing supply of targets and financing",
                 "Organic growth is always taxed higher", "Acquired growth is not reportable"],
                1,
                "Only one of them demonstrates that the underlying business sells more. The other "
                "demonstrates access to capital, which is a different and more fragile capability.",
            ),
        ],
    ),

    # ── i011 ──────────────────────────────────────────────────────────────
    Lesson(
        id="i011",
        title="Base Rates: Why Your Stock Picks Underperform Your Analysis",
        category="Quantitative",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=7,
        body=(
            "You research a company thoroughly, conclude it is undervalued, and buy. Your analysis "
            "may be entirely sound and the position may still be a poor bet, because analysis "
            "quality is only half of the calculation. The other half is the base rate: what "
            "usually happens to companies like this one.\n\n"

            "**The distribution of single-stock outcomes is brutally skewed.** Research on US "
            "stocks over long horizons consistently finds that the median stock underperforms the "
            "index, that a large minority lose money outright over a decade, and that essentially "
            "all of the market's aggregate gain comes from a small percentage of enormous winners. "
            "The average is carried by the tail. Pick a stock at random and you are more likely "
            "than not to trail the index, not because you chose badly, but because that is the "
            "shape of the distribution.\n\n"

            "**What this does to concentrated portfolios.** If most stocks underperform and a few "
            "carry everything, a ten-stock portfolio has a meaningful chance of missing every one "
            "of the winners. Its most likely outcome is below-index, with a small chance of a "
            "spectacular result. The mean is fine; the median is not. Concentration raises the "
            "variance of your outcome far more than it raises its expectation.\n\n"

            "**Inside-view versus outside-view.** The inside view reasons from the specifics: this "
            "management, this product, this market. The outside view asks what happened to the "
            "reference class: companies at this valuation, at this growth rate, in this industry, "
            "historically. People overwhelmingly favour the inside view because it feels like "
            "real analysis, and the outside view is a better predictor almost every time.\n\n"

            "**The correction is not to stop analysing.** It is to hold the base rate alongside "
            "your conclusion. If companies with these characteristics beat the market 35% of the "
            "time historically, your excellent analysis needs to move you meaningfully above 35% "
            "before the position is justified, and to size accordingly. Most analysis moves the "
            "number by less than the analyst believes.\n\n"

            "**Where this cuts hardest.** Narratives that are true and priced. 'This company "
            "dominates a growing market' can be entirely correct and still a bad investment, "
            "because everyone else can see it too and the price reflects it. The base rate for "
            "'obviously excellent company at an obviously high price' is not encouraging."
        ),
        key_takeaway=(
            "The median stock underperforms the index and a handful of enormous winners carry the "
            "average, so a concentrated portfolio's most likely outcome is below-index even when "
            "each pick was reasonable. Hold the base rate alongside your analysis, and size for it."
        ),
        glossary=[
            GlossaryTerm("base rate", "How often an outcome occurs across the whole reference class, before considering the specifics of one case."),
            GlossaryTerm("outside view", "Forecasting by asking what happened to similar cases historically, rather than reasoning from this case's details."),
            GlossaryTerm("inside view", "Forecasting from the specifics of the case at hand. Feels more rigorous and predicts worse."),
            GlossaryTerm("positive skew", "A distribution where the mean is pulled well above the median by a small number of extreme outcomes: the shape of single-stock returns."),
        ],
        callouts=[
            Callout("key_idea", "Mean and median diverge sharply here",
                "The market's average return is real, but it is produced by a minority of holdings. Any "
                "portfolio too small to reliably contain some of them has an expected value near the "
                "average and a most-likely outcome well below it."),
            Callout("common_mistake", "Mistaking a true narrative for an edge",
                "Being right that a company is excellent earns nothing if the price already says so. An "
                "edge requires being right about something the price has wrong."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=2,
                question="If a small minority of stocks generate nearly all of the market's gains, what does that imply for a 10-stock portfolio?",
                options=[
                    "It will outperform, since fewer positions means better ones",
                    "Its expected value is near the market's, but its most likely outcome is below it",
                    "It carries the same risk as an index fund",
                    "It will match the index with lower fees",
                ],
                correct_index=1,
                explanation=(
                    "With returns this skewed, a small portfolio most often misses the extreme winners "
                    "entirely. The average across many such portfolios is fine; any single one is more "
                    "likely than not to disappoint."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "What does the positive skew of single-stock returns mean in practice?",
                ["Most stocks beat the index", "The median stock underperforms while a few extreme winners carry the average",
                 "Returns are normally distributed", "Volatility is symmetric"],
                1,
                "The mean is pulled up by a small tail of enormous outcomes. Picking at random, you are "
                "more likely to land below the index than above it.",
            ),
            QuizQuestion(
                "What is the 'outside view' when evaluating an investment?",
                ["Consulting other analysts", "Asking what historically happened to companies in this reference class",
                 "Reading the company's own guidance", "Looking at the stock chart"],
                1,
                "It anchors on the base rate for similar situations rather than on the compelling specifics "
                "of this one, and it is the better predictor in most forecasting research.",
            ),
            QuizQuestion(
                "You correctly identify that a company dominates a fast-growing market. Why might this still be a poor investment?",
                ["Dominant companies are riskier", "The insight may already be fully reflected in the price",
                 "Growing markets attract regulation", "Large companies grow more slowly"],
                1,
                "Returns come from being right about something the price has wrong. A widely-visible truth "
                "is already embedded in what you pay for it.",
            ),
        ],
    ),

    # ── i012 ──────────────────────────────────────────────────────────────
    Lesson(
        id="i012",
        title="Buybacks: Value Return, Financial Engineering, or Both",
        category="Fundamental Analysis",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=7,
        body=(
            "A share buyback is a company using cash to purchase its own shares, which are then "
            "retired. The remaining shareholders own a larger slice of the same business. Whether "
            "this creates value depends entirely on one variable that almost no coverage of "
            "buybacks mentions: the price paid.\n\n"

            "**The mechanism.** Profit stays the same; share count falls; earnings per share "
            "rises. Nothing about operations changed. This is why EPS growth and business growth "
            "must be tracked separately: a company with flat profit buying back 5% of its shares "
            "reports 5% EPS growth and has grown not at all.\n\n"

            "**When buybacks genuinely create value.** When the shares are bought below intrinsic "
            "value. Then the company is acquiring a dollar of value for less than a dollar, and "
            "continuing holders capture the difference. This is the same logic as any other "
            "investment: it is good if the price is right and bad if it is not.\n\n"

            "**When they destroy it.** When shares are bought above intrinsic value, remaining "
            "shareholders are overpaying to shrink their own company. And the empirical pattern is "
            "uncomfortable: buyback activity peaks near market highs when cash is abundant and "
            "valuations are stretched, and collapses in downturns when shares are cheapest and "
            "cash is scarce. Corporations, in aggregate, buy high and sell low with the same "
            "reliability as retail investors.\n\n"

            "**The compensation problem.** Executive pay is frequently tied to EPS targets. "
            "Buybacks raise EPS mechanically. That is a direct incentive to repurchase shares "
            "regardless of price, and it is disclosed in the proxy statement rather than the "
            "earnings release. Checking whether EPS is a compensation metric takes one search and "
            "changes how you read the buyback.\n\n"

            "**Buybacks that offset dilution are not returns at all.** Many companies issue "
            "substantial stock to employees and repurchase a similar amount to keep the count "
            "flat. The press release announces a buyback; the share count does not fall. That is "
            "not capital returned to shareholders: it is payroll settled in stock and bought "
            "back with cash. The only way to see it is to track shares outstanding over several "
            "years rather than reading the announcement.\n\n"

            "**Buybacks versus dividends.** Buybacks are flexible: a company can quietly stop, "
            "where cutting a dividend is a public admission. That flexibility is genuinely "
            "valuable for cyclical businesses. Buybacks are also more tax-efficient for holders, "
            "since no taxable event occurs until you choose to sell."
        ),
        key_takeaway=(
            "A buyback creates value only if shares are repurchased below intrinsic value, and "
            "corporations reliably buy most at market highs. Check shares outstanding over several "
            "years, not the announcement: many buybacks only offset stock compensation and return "
            "nothing."
        ),
        glossary=[
            GlossaryTerm("share buyback", "A company purchasing and retiring its own shares, raising each remaining holder's proportional ownership."),
            GlossaryTerm("shares outstanding", "The total shares currently held by all investors. The only reliable evidence of whether a buyback actually shrank the count."),
            GlossaryTerm("dilution", "An increase in share count, usually from stock-based compensation, which reduces each existing holder's proportional stake."),
            GlossaryTerm("intrinsic value", "An estimate of what the business is actually worth, against which a repurchase price should be judged."),
        ],
        callouts=[
            Callout("why_it_matters", "Track the share count, not the announcement",
                "Pull shares outstanding for the last five years from the 10-K. If it is flat or rising "
                "despite years of announced buybacks, the repurchases were funding stock compensation, "
                "not returning capital."),
            Callout("common_mistake", "Treating any buyback as shareholder-friendly",
                "Buying overvalued shares destroys value exactly as buying an overvalued acquisition does. "
                "The transaction is only as good as the price."),
        ],
        practice=[
            NumericQuestion(
                question="A company earns $400 million with 200 million shares outstanding, then buys back 20 million shares. With profit unchanged, what is the new EPS in dollars?",
                answer=2.22, tolerance=0.03,
                unit="$",
                hint="Divide unchanged profit by the reduced share count.",
                explanation=(
                    "$400m / 180m shares = $2.22, up from $2.00: an 11% EPS increase with no change "
                    "whatsoever in the business. If executive compensation targets EPS growth, this is a "
                    "meaningful bonus purchased with shareholder cash."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Under what condition does a buyback create value for continuing shareholders?",
                ["Whenever the company has spare cash", "When shares are repurchased below intrinsic value",
                 "When it raises EPS", "When it is announced publicly"],
                1,
                "It is an investment decision like any other. Buying a dollar of value for less than a "
                "dollar creates value; paying more destroys it, regardless of what EPS does.",
            ),
            QuizQuestion(
                "Why does corporate buyback activity tend to peak at market highs?",
                ["Regulation permits it only then", "Cash is most abundant and confidence highest exactly when valuations are most stretched",
                 "Share prices are lowest then", "Tax treatment improves"],
                1,
                "Buybacks are funded from profits and confidence, both of which peak late in a cycle. "
                "Companies therefore repurchase most heavily when their shares are most expensive.",
            ),
            QuizQuestion(
                "A company announces buybacks every year, yet shares outstanding are flat over five years. What happened?",
                ["The buybacks were cancelled", "Repurchases only offset shares issued as employee compensation",
                 "Shares were split", "The count excludes treasury shares"],
                1,
                "Buying back roughly what is issued keeps the count level. No capital was returned to "
                "shareholders: stock compensation was settled with cash, via the market.",
            ),
        ],
    ),

    # ── i013 ──────────────────────────────────────────────────────────────
    Lesson(
        id="i013",
        title="Capital Structure: Why Debt Changes Everything About a Company",
        category="Fundamental Analysis",
        tier=TIER_INTERMEDIATE,
        estimated_read_time_minutes=8,
        body=(
            "Two companies generate identical operating profit. One is funded entirely by equity, "
            "the other is half debt. They are not similar businesses with a financing footnote: "
            "they have different risk, different equity returns and different failure modes.\n\n"

            "**Leverage amplifies in both directions.** Debt is a fixed claim: interest is owed "
            "regardless of results. So when operating profit rises, everything above the interest "
            "payment flows to a smaller equity base and equity returns rise faster than the "
            "business did. When profit falls, the interest is still owed and equity absorbs the "
            "entire shortfall. The same business, financed differently, produces a much wider "
            "distribution of equity outcomes.\n\n"

            "**Why enterprise value exists.** Market capitalisation prices only the equity. If you "
            "want to compare two companies as businesses, you need what it would cost to buy the "
            "whole thing: enterprise value, market cap plus debt minus cash. Comparing two "
            "companies on P/E when one carries heavy debt compares two different questions. "
            "EV/EBITDA is the standard fix, which is why acquirers use it and headlines do not.\n\n"

            "**Interest coverage is the number that predicts trouble.** Operating profit divided "
            "by interest expense. Coverage of 10x means profit could fall 90% before interest "
            "becomes unpayable. Coverage of 1.5x means a moderate downturn is an existential "
            "event. This single ratio does more to predict distress than almost any other, and it "
            "takes seconds to compute.\n\n"

            "**Maturity walls matter more than total debt.** A company with substantial debt and "
            "nothing due for eight years is in a very different position from one with the same "
            "debt maturing next year. Refinancing risk is the real danger: debt must be rolled "
            "over at whatever rates prevail then, and the moments when refinancing is hardest are "
            "exactly the moments when business is worst. The maturity schedule is in the 10-K.\n\n"

            "**Debt is not inherently bad.** It is cheaper than equity: interest is tax-deductible "
            "and lenders accept lower returns for a senior claim, so a moderately leveraged "
            "company can genuinely produce better shareholder returns. Utilities carry heavy debt "
            "sensibly because their cash flows are stable and predictable. The question is never "
            "'is there debt', it is whether the debt is matched to the reliability of the cash "
            "flows servicing it.\n\n"

            "**Where equity holders actually stand.** In liquidation, equity is paid last: secured "
            "lenders, then unsecured, then preferred, then common. This is why a heavily indebted "
            "company's equity can go to zero while the business itself continues operating "
            "perfectly well under new ownership. The business survived; the equity claim did not."
        ),
        key_takeaway=(
            "Interest coverage, operating profit over interest expense, predicts distress better "
            "than almost any other single ratio, and the maturity schedule matters more than the "
            "total. Equity is paid last, which is how a company can survive while its shares go to "
            "zero."
        ),
        glossary=[
            GlossaryTerm("leverage", "The use of borrowed money, which amplifies both gains and losses to equity holders."),
            GlossaryTerm("enterprise value", "Market cap plus debt minus cash: what it would cost to acquire the whole business, independent of how it is financed."),
            GlossaryTerm("EBITDA", "Earnings before interest, tax, depreciation and amortisation. A rough proxy for operating cash generation, used to compare companies with different capital structures."),
            GlossaryTerm("interest coverage", "Operating profit divided by interest expense. How far profit can fall before debt service is at risk."),
            GlossaryTerm("refinancing risk", "The risk that maturing debt must be rolled over on worse terms, typically when conditions are already poor."),
            GlossaryTerm("seniority", "The order of claims in a bankruptcy. Secured lenders first, common equity last."),
        ],
        callouts=[
            Callout("example", "The same business, two structures",
                "Operating profit $100m. Company A has no debt: equity earns $100m. Company B owes $40m of "
                "interest: equity earns $60m on a much smaller equity base, so returns are higher. Now let "
                "profit fall to $45m. A earns $45m; B is not covering its interest at all."),
            Callout("why_it_matters", "P/E is not comparable across capital structures",
                "A leveraged company can show a lower P/E purely because its equity slice is smaller and "
                "riskier. EV/EBITDA compares the businesses; P/E compares the equity stubs."),
        ],
        practice=[
            NumericQuestion(
                question="A company has operating profit of $340 million and interest expense of $85 million. What is its interest coverage ratio?",
                answer=4.0, tolerance=0.1,
                unit="x",
                hint="Operating profit divided by interest expense.",
                explanation=(
                    "$340m / $85m = 4.0x. Operating profit could fall 75% before interest became unpayable. "
                    "Comfortable for a stable business; thin for a cyclical one that routinely sees profits "
                    "halve in a downturn."
                ),
            ),
            NumericQuestion(
                question="A company has a market cap of $2.4 billion, debt of $900 million and cash of $300 million. What is its enterprise value, in billions?",
                answer=3.0, tolerance=0.05,
                unit="$B",
                hint="Market cap plus debt minus cash.",
                explanation=(
                    "$2.4b + $0.9b - $0.3b = $3.0b. An acquirer assumes the debt and receives the cash, so "
                    "this, not the $2.4b market cap: is what buying the business actually costs."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Why is EV/EBITDA preferred over P/E when comparing companies with different debt levels?",
                ["It is easier to compute", "Enterprise value prices the whole business regardless of financing, while P/E prices only the equity slice",
                 "EBITDA is more accurate than earnings", "P/E cannot be computed for indebted companies"],
                1,
                "P/E compares equity claims of different riskiness. EV/EBITDA compares the underlying "
                "businesses, which is the comparison you usually intend to make.",
            ),
            QuizQuestion(
                "A company has interest coverage of 1.6x. What does that tell you?",
                ["It has no debt", "A moderate decline in operating profit would threaten its ability to service debt",
                 "It is highly profitable", "Its debt matures soon"],
                1,
                "Coverage of 1.6x means profit covers interest with little margin. A downturn of the kind "
                "most businesses see periodically would put debt service at risk.",
            ),
            QuizQuestion(
                "Why can a company's equity go to zero while the business keeps operating?",
                ["Equity holders sold out", "Equity is the last claim paid; creditors can take ownership and continue the business",
                 "Regulators seize the shares", "The exchange delists it"],
                1,
                "Bankruptcy restructures claims by seniority. Creditors frequently become the new owners of "
                "a functioning business, and the previous common equity is extinguished.",
            ),
        ],
    ),
]
