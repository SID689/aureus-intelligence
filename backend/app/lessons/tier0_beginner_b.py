"""
app/lessons/tier0_beginner_b.py
---------------------------------
MODULE 0 — "New to Investing", continued.

A second file rather than a longer first one: tier0_beginner.py was
already 500 lines, and lesson banks are read by humans editing prose, not
just by the loader. Same tier, same editorial rules as tier0_beginner.py
— no unexplained jargon, concrete numbers over abstractions, never imply
a recommendation, and name the beginner mistake explicitly.

These ten lessons cover the ground a first-time investor hits in their
first month that the original five did not: what a brokerage account
actually is, what a dividend actually does to the share price, why fees
matter far more than they look, the tax events nobody warns you about,
and the specific psychology that costs beginners the most money.
"""

from app.lessons.models import (
    Callout, Checkpoint, Exercise, GlossaryTerm, Lesson, NumericQuestion,
    QuizQuestion, TIER_BEGINNER,
)

TIER_0_BEGINNER_B: list[Lesson] = [

    # ── b006 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b006",
        title="What a Brokerage Account Actually Is",
        category="Market Basics",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "A brokerage account is not a bank account that happens to hold stocks. It is a "
            "custody arrangement, and understanding that difference explains most of what "
            "confuses people about how their money is held.\n\n"

            "**Who actually owns your shares.** When you buy 100 shares, they are almost never "
            "registered in your name. They are held in 'street name' — registered to the broker, "
            "with the broker's internal records saying those particular shares belong to you. This "
            "sounds alarming and is actually fine: it is what makes settlement fast enough to be "
            "practical. But it does mean your claim is a record in a company's books, which is why "
            "the next paragraph exists.\n\n"

            "**SIPC is not FDIC.** Bank deposits are insured by the FDIC against the bank losing "
            "your money. Brokerage accounts are covered by SIPC, which is a narrower promise: it "
            "protects against the BROKER FAILING and your assets going missing, up to $500,000 "
            "(of which $250,000 for cash). It does not protect against your investments losing "
            "value. If your broker collapses, SIPC works to make you whole. If your stock drops "
            "60%, SIPC has nothing to say about it. People conflate these constantly.\n\n"

            "**Cash accounts versus margin accounts.** A cash account can only buy with money you "
            "have. A margin account lets you borrow against your holdings to buy more. Brokers "
            "often open margin accounts by default because it is better business for them — they "
            "earn interest on the loan and can lend your shares to short sellers. For someone "
            "starting out, a cash account removes an entire category of ways to lose money "
            "quickly. You can usually switch.\n\n"

            "**Settlement, and why the money 'isn't there yet'.** US stock trades settle T+1: the "
            "actual exchange of shares for cash happens one business day after the trade. Sell on "
            "Monday and the cash is genuinely usable Tuesday. In a cash account, spending money "
            "that has not settled and then selling the new position before settlement is a "
            "'good-faith violation', and a few of those get your account restricted.\n\n"

            "**What to actually check before funding one.** Whether it is a cash or margin "
            "account. Whether they charge for the things you will actually do. Whether they accept "
            "payment for order flow, which is not automatically bad but is worth knowing. And "
            "whether transferring out later costs anything, because the time to discover an exit "
            "fee is before you are trying to leave."
        ),
        key_takeaway=(
            "SIPC protects you if your broker fails, not if your investments fall — those are "
            "completely different risks and conflating them is the most common misunderstanding "
            "about how brokerage accounts work."
        ),
        glossary=[
            GlossaryTerm("street name", "Shares registered to your broker rather than to you personally, with the broker's records tracking your ownership. Standard practice, and what makes fast settlement possible."),
            GlossaryTerm("SIPC", "Securities Investor Protection Corporation. Covers up to $500,000 if your BROKER fails and assets go missing. It does not cover investment losses."),
            GlossaryTerm("margin account", "An account that lets you borrow against your holdings to buy more securities. Amplifies both gains and losses, and the broker may lend out your shares."),
            GlossaryTerm("cash account", "An account that can only buy with settled cash. No borrowing, and correspondingly fewer ways to lose money fast."),
            GlossaryTerm("settlement", "The actual transfer of shares and cash after a trade. US equities settle one business day later, written T+1."),
        ],
        callouts=[
            Callout("common_mistake", "Assuming your account is FDIC insured",
                "It is not. Cash sitting uninvested at a broker may be swept into partner banks that "
                "carry FDIC coverage, but your stocks never are. Nothing insures you against a "
                "position falling in value, and any product implying otherwise deserves suspicion."),
            Callout("why_it_matters", "Margin gets opened by default",
                "Many brokers enable margin unless you opt out, because they profit from it. If you "
                "did not deliberately choose margin, check which type you have — it is usually one "
                "screen in account settings."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=2,
                question="Your broker goes bankrupt. Separately, one of your stocks falls 40%. Which does SIPC address?",
                options=[
                    "Both — that is what the coverage is for",
                    "Only the broker's failure",
                    "Only the stock's decline",
                    "Neither; SIPC covers cash only",
                ],
                correct_index=1,
                explanation=(
                    "SIPC exists for custodial failure — the broker losing or misappropriating assets it "
                    "held for you. Market losses are the risk you deliberately took by investing, and no "
                    "insurance scheme covers them."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "What does SIPC coverage actually protect against?",
                ["Your investments falling in value", "Your broker failing and assets going missing",
                 "A company you own going bankrupt", "Losses from a bad trade"],
                1,
                "SIPC addresses custodial failure only, up to $500,000. Market losses — whether from a "
                "falling stock or a bankrupt issuer — are outside its scope entirely.",
            ),
            QuizQuestion(
                "Why do brokers frequently open margin accounts by default?",
                ["Regulators require it", "It is cheaper to administer",
                 "They earn interest on margin loans and can lend your shares out", "Cash accounts settle more slowly"],
                2,
                "A margin account is more profitable for the broker: interest on the borrowed balance, plus "
                "the ability to lend your shares to short sellers. Neither is sinister, but neither is done "
                "for your benefit.",
            ),
            QuizQuestion(
                "You sell a stock on Monday. Under T+1 settlement, when is the cash genuinely settled?",
                ["Immediately", "Tuesday", "Friday", "The following Monday"],
                1,
                "T+1 means one business day after the trade. Your broker may show buying power sooner, but "
                "the actual settlement — and therefore the point at which spending it cannot cause a "
                "good-faith violation — is Tuesday.",
            ),
        ],
    ),

    # ── b007 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b007",
        title="Dividends: What They Are, and What They Aren't",
        category="Market Basics",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "A dividend is a company paying out part of its profits to shareholders in cash. If a "
            "company declares a $0.50 quarterly dividend and you own 200 shares, $100 appears in "
            "your account. That part is simple. The part that surprises almost everyone is what "
            "happens to the share price.\n\n"

            "**The price drops by roughly the dividend.** On the ex-dividend date, the stock opens "
            "lower by approximately the dividend amount. This is not a coincidence or a market "
            "reaction — it is arithmetic. The company just sent cash out the door, so it is worth "
            "that much less. A $100 stock paying a $1 dividend becomes, all else equal, a $99 "
            "stock plus $1 in your pocket.\n\n"

            "**Which means a dividend is not free money.** You did not gain $1. You converted $1 "
            "of share value into $1 of cash, and in a taxable account you now owe tax on it. This "
            "is the single most misunderstood thing in retail investing, and it is the engine "
            "behind a specific bad strategy: buying a stock just before the ex-dividend date to "
            "'capture' the payment. You capture the dividend and lose the same amount in price. "
            "The only reliable outcome is the tax bill.\n\n"

            "**The four dates.** Declaration date: the company announces it. Ex-dividend date: buy "
            "on or after this day and you do NOT receive the dividend. Record date: who the "
            "company checks its books for. Payment date: when cash actually arrives, often weeks "
            "later. The only one that governs whether you get paid is the ex-dividend date.\n\n"

            "**Dividend yield, and why a high one is a warning as often as a reward.** Yield is "
            "annual dividend divided by share price. If the price falls and the dividend has not "
            "been cut yet, the yield mechanically rises. So the highest-yielding stocks in any "
            "screen are disproportionately companies the market expects to cut. A 12% yield is "
            "not a 12% return; it is frequently the market pricing in that the payment will not "
            "survive.\n\n"

            "**So why do dividends matter at all?** Because paying one is a hard commitment. "
            "Earnings can be presented flatteringly; cash leaving the building every quarter "
            "cannot. A long record of maintained and rising dividends is real evidence about a "
            "business's cash generation and its management's discipline. That is the signal — not "
            "the yield number itself."
        ),
        key_takeaway=(
            "A dividend moves value from the share price into your pocket; it does not create "
            "value. The share price drops by roughly the payment on the ex-dividend date, which is "
            "why 'dividend capture' cannot work and why a very high yield is usually a warning."
        ),
        glossary=[
            GlossaryTerm("dividend", "A cash payment from a company's profits to its shareholders, usually quarterly."),
            GlossaryTerm("ex-dividend date", "The cutoff. Buy on or after it and you do not receive the upcoming dividend. The share price drops by roughly the dividend amount that morning."),
            GlossaryTerm("dividend yield", "Annual dividend divided by share price, as a percentage. Rises mechanically when the price falls, which is why high yields often signal distress."),
            GlossaryTerm("payout ratio", "The share of earnings paid out as dividends. Above 100% means the company is paying out more than it earns, which cannot continue indefinitely."),
        ],
        callouts=[
            Callout("example", "Why dividend capture does not work",
                "A stock trades at $50 and pays a $1 dividend. You buy 100 shares for $5,000 the day "
                "before the ex-date. Next morning it opens near $49 and you receive $100. You hold "
                "$4,900 of stock plus $100 cash — still $5,000 — and now owe tax on the $100. You did "
                "the trade, paid the spread twice, and are behind."),
            Callout("common_mistake", "Screening for the highest yield",
                "Sorting a stock screener by dividend yield descending returns, more often than not, a "
                "list of companies whose price has collapsed and whose dividend is about to be cut. "
                "Yield is a ratio, and its denominator is a falling number."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=2,
                question="A $40 stock pays a $0.60 dividend. What roughly happens on the ex-dividend morning?",
                options=[
                    "It opens near $40.60 because the dividend attracts buyers",
                    "It opens near $39.40 because the company paid cash out",
                    "It is unchanged; dividends do not affect price",
                    "It doubles the spread but the price is unchanged",
                ],
                correct_index=1,
                explanation=(
                    "The cash has left the company, so the business is worth that much less per share. The "
                    "drop is mechanical, not a market judgement."
                ),
            ),
        ],
        practice=[
            NumericQuestion(
                question="A stock trades at $80 and pays $0.75 per quarter. What is its annual dividend yield, as a percentage?",
                answer=3.75, tolerance=0.06,
                unit="%",
                hint="Annualise the quarterly payment first, then divide by the price.",
                explanation=(
                    "$0.75 x 4 = $3.00 a year. $3.00 / $80 = 0.0375, or 3.75%. Note that if the price fell "
                    "to $40 with no change in the payment, the yield would read 7.5% — the same dividend, "
                    "a much worse-looking company."
                ),
            ),
            NumericQuestion(
                question="You own 340 shares of a company declaring a $0.42 quarterly dividend. How much cash do you receive this quarter, in dollars?",
                answer=142.80, tolerance=0.5,
                unit="$",
                hint="Shares times the per-share payment. This is one quarter, not a year.",
                explanation=(
                    "340 x $0.42 = $142.80. In a taxable account this is income in the year received, even "
                    "if you immediately reinvest it — reinvestment does not defer the tax."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Why does a share price fall on the ex-dividend date?",
                ["Investors sell after collecting the dividend", "The company transferred cash out, so it is worth that much less",
                 "Market makers widen the spread", "It is a regulatory requirement"],
                1,
                "It is arithmetic, not behaviour. Cash left the business, so each share represents a "
                "slightly less valuable company. The drop happens at the open regardless of who trades.",
            ),
            QuizQuestion(
                "A screener shows a stock with a 14% dividend yield. What is the most likely explanation?",
                ["Exceptional management returning capital", "The share price has collapsed and the market expects a cut",
                 "The company is growing unusually fast", "It is a data error"],
                1,
                "Yield rises automatically when price falls. An extreme yield usually means the market has "
                "already decided the dividend is unsustainable — it is a distress signal more often than "
                "a bargain.",
            ),
            QuizQuestion(
                "Which date determines whether you receive an upcoming dividend?",
                ["Declaration date", "Ex-dividend date", "Record date", "Payment date"],
                1,
                "You must own the shares before the ex-dividend date. Buying on it or after means the "
                "seller keeps the payment, which is exactly why the price adjusts that morning.",
            ),
        ],
    ),

    # ── b008 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b008",
        title="Index Funds and ETFs: The Default Answer",
        category="Asset Classes",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=7,
        body=(
            "An index fund is a fund that does not try to pick winners. It buys everything in a "
            "defined list — the S&P 500, the total US market, the world — in proportion to size, "
            "and holds it. That is the entire strategy, and it is the one most professional "
            "investors fail to beat.\n\n"

            "**Why 'not trying' works.** The market's return is the average of all participants' "
            "returns before costs. That is not a theory, it is arithmetic: every share is owned by "
            "someone at all times. So the average active investor must earn the market return "
            "before fees, and less than it after. Index funds simply take that average and charge "
            "almost nothing for it. Beating them requires being better than the average of every "
            "professional you are trading against, consistently, by more than your costs.\n\n"

            "**ETF versus mutual fund.** An ETF (exchange-traded fund) trades on an exchange like "
            "a stock, all day, at whatever price the market quotes. A traditional mutual fund is "
            "priced once, after the close, and you transact at that single price. For most people "
            "the practical differences are small — ETFs are usually more tax-efficient in taxable "
            "accounts and easier to buy in small amounts, mutual funds are easier to automate "
            "contributions into.\n\n"

            "**What the expense ratio means.** It is the annual percentage the fund deducts. A "
            "0.03% expense ratio on $10,000 is $3 a year. A 0.75% ratio on the same $10,000 is "
            "$75. That gap looks trivial in year one and is not trivial over thirty years, "
            "because the money taken out is money that never compounds. Broad index funds are "
            "available at three to five basis points; anything charging over 0.5% to track a "
            "standard index is charging for something it is not providing.\n\n"

            "**What indexing does not protect you from.** It removes the risk of picking the wrong "
            "company. It does nothing about the market falling — an S&P 500 fund fell roughly 50% "
            "in 2008 and roughly 34% in weeks during March 2020. Diversification across companies "
            "is not diversification across market risk. Believing otherwise is how people discover "
            "their real risk tolerance at the worst possible moment.\n\n"

            "**Concentration hides inside 'diversified' funds.** A cap-weighted S&P 500 fund holds "
            "500 companies, but the largest handful can be a quarter or more of it. You own the "
            "index; you also own an unusually large bet on a few very big companies. That is not "
            "an argument against it — it is an argument for knowing what you actually hold."
        ),
        key_takeaway=(
            "The average active investor must, by arithmetic, earn the market return before costs "
            "and less after. Index funds take that average for almost nothing — but they protect "
            "you from picking wrong, not from the market falling."
        ),
        glossary=[
            GlossaryTerm("index fund", "A fund that mechanically holds everything in a defined index rather than selecting individual holdings."),
            GlossaryTerm("ETF", "Exchange-traded fund. A fund that trades on an exchange throughout the day like a stock."),
            GlossaryTerm("expense ratio", "The annual percentage of your balance a fund deducts as its fee. Charged whether the fund gains or loses."),
            GlossaryTerm("basis point", "One hundredth of a percent. A 5 basis point fee is 0.05%. Finance uses these because 'a 0.02% difference' is easy to misread."),
            GlossaryTerm("cap-weighted", "Holdings sized in proportion to company value, so the largest companies dominate the fund."),
        ],
        callouts=[
            Callout("key_idea", "Costs are the one variable you control",
                "You cannot choose next year's return. You can choose, with certainty, whether you pay "
                "0.03% or 0.75% for it. Over a long horizon that decision moves more money than most "
                "stock picks do."),
            Callout("common_mistake", "Treating 'diversified' as 'safe'",
                "Owning 500 companies removes single-company risk. It leaves market risk entirely intact. "
                "Both 2008 and March 2020 hit every one of those 500 at once."),
        ],
        exercises=[
            Exercise(
                kind="fee_drag",
                title="What a fee actually costs over time",
                prompt=(
                    "Set the balance to $10,000 and the horizon to 30 years, then compare a 0.03% fee "
                    "with a 0.75% one. The difference is not 0.72% — it is that percentage compounding "
                    "against you every year, on a balance that would otherwise have been growing."
                ),
                params={"balance": 10000, "annual_return": 7, "years": 30, "fee_a": 0.03, "fee_b": 0.75},
            ),
        ],
        practice=[
            NumericQuestion(
                question="A fund charges a 0.60% expense ratio. On a $25,000 balance, what does it deduct in one year, in dollars?",
                answer=150, tolerance=1,
                unit="$",
                hint="Expense ratio is an annual percentage of the balance.",
                explanation=(
                    "$25,000 x 0.0060 = $150 a year, deducted whether the fund rose or fell. The same "
                    "balance in a 0.03% fund pays $7.50 — and the $142.50 difference then compounds for "
                    "as long as you hold."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Why must the average active investor underperform the market after costs?",
                ["Active managers are less skilled", "The market return IS the average of all participants, so after fees the average must trail it",
                 "Index funds get better prices", "Regulation favours passive funds"],
                1,
                "Every share is held by someone at all times, so participants collectively earn the market "
                "return before costs. Subtract fees and trading expenses and the average necessarily lands "
                "below it. This is arithmetic, not a claim about talent.",
            ),
            QuizQuestion(
                "What risk does a broad index fund NOT remove?",
                ["The risk of picking the wrong company", "The risk that one holding goes bankrupt",
                 "The risk of the whole market falling", "The risk of paying high fees"],
                2,
                "Diversification across companies neutralises single-company risk. Market risk is common to "
                "all of them and cannot be diversified away by owning more of the same market.",
            ),
            QuizQuestion(
                "What is an expense ratio?",
                ["A one-time purchase commission", "The annual percentage of your balance the fund deducts",
                 "The fund's trading costs, billed separately", "The tax rate on fund distributions"],
                1,
                "It is charged annually against your balance regardless of performance. Because the deducted "
                "money stops compounding, small differences grow into large ones over long horizons.",
            ),
        ],
    ),

    # ── b009 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b009",
        title="Taxes: The Events Nobody Warns You About",
        category="Risk & Return",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=7,
        body=(
            "This lesson describes how the US tax rules generally work so that nothing surprises "
            "you. It is not tax advice, and situations vary enough that anything consequential is "
            "worth checking with someone qualified.\n\n"

            "**You are taxed when you sell, not when you gain.** A position that has doubled and "
            "is still held creates no tax. The gain is 'unrealized'. The moment you sell, it "
            "becomes 'realized' and enters that year's return. This one distinction explains why "
            "trading frequently is expensive in ways the commission-free label hides: every "
            "profitable sale pulls forward a tax bill that a held position defers indefinitely.\n\n"

            "**Holding period changes the rate a lot.** Sell at a profit within one year and the "
            "gain is short-term, taxed as ordinary income — the same rate as your salary. Hold "
            "beyond one year and it is long-term, taxed at preferential rates that for most people "
            "are 0%, 15% or 20%. The difference between selling at day 360 and day 366 can be "
            "more than a third of the gain. The clock starts the day after purchase.\n\n"

            "**Dividends have their own split.** 'Qualified' dividends — most US corporate "
            "dividends, if you held the shares long enough around the ex-date — get the long-term "
            "rates. Non-qualified ones, including most REIT distributions and interest, are taxed "
            "as ordinary income. Your broker reports which is which on a 1099-DIV.\n\n"

            "**Losses are useful, and there is a trap.** Realized losses offset realized gains "
            "dollar for dollar, and up to $3,000 of net loss can offset ordinary income each year, "
            "with the rest carried forward. Deliberately realising losses to offset gains is "
            "called tax-loss harvesting. The trap is the **wash sale rule**: if you buy the same "
            "or a 'substantially identical' security within 30 days before or after the sale, the "
            "loss is disallowed for now. It is not lost — it is added to the cost basis of the new "
            "position — but it does not do what you wanted this year. Buying back the same fund a "
            "week later is exactly the pattern that triggers it.\n\n"

            "**Tax-advantaged accounts change the calculus entirely.** Inside a 401(k) or IRA, "
            "buying and selling generates no current tax at all. The trading that is expensive in "
            "a taxable account is free of tax friction there. This is why the same person can "
            "reasonably rebalance often inside a retirement account and rarely outside one.\n\n"

            "**The mutual fund distribution surprise.** A mutual fund can distribute capital gains "
            "to you in December — creating a tax bill — even in a year the fund lost money, "
            "because the distribution reflects the fund's internal sales, not your return. ETFs "
            "largely avoid this, which is the main reason they are preferred in taxable accounts."
        ),
        key_takeaway=(
            "Tax is triggered by selling, not by gaining, and the one-year holding line changes "
            "the rate dramatically. The wash sale rule quietly cancels harvested losses if you buy "
            "back within 30 days — the single most common accidental mistake in this area."
        ),
        glossary=[
            GlossaryTerm("realized gain", "Profit locked in by selling. Only realized gains are taxable; an unsold winner is not."),
            GlossaryTerm("unrealized gain", "Profit on paper in a position you still hold. Not a taxable event."),
            GlossaryTerm("short-term capital gain", "Gain on something held one year or less, taxed at ordinary income rates."),
            GlossaryTerm("long-term capital gain", "Gain on something held more than one year, taxed at preferential rates."),
            GlossaryTerm("wash sale", "Selling at a loss and buying the same or substantially identical security within 30 days either side, which disallows the loss for the current year."),
            GlossaryTerm("cost basis", "What you paid, used to compute gain or loss on sale. A disallowed wash-sale loss is added to the new position's basis."),
        ],
        callouts=[
            Callout("example", "What the one-year line is worth",
                "A $10,000 gain for someone in a 32% bracket: sold at 11 months, roughly $3,200 of tax. "
                "Sold at 13 months at a 15% long-term rate, roughly $1,500. Same trade, same profit, "
                "$1,700 difference for waiting eight weeks."),
            Callout("common_mistake", "Harvesting a loss, then buying straight back in",
                "You sell an index fund at a loss in December for the tax benefit, then buy it back the "
                "next week because you still want the exposure. That is a wash sale, the loss is "
                "disallowed this year, and most people never notice until the 1099 arrives."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=1,
                question="Your position is up $8,000 and you have not sold. What is the tax consequence this year?",
                options=[
                    "You owe tax on $8,000 of gain",
                    "You owe tax on half of it",
                    "None — the gain is unrealized until you sell",
                    "You owe tax only if it is a dividend-paying stock",
                ],
                correct_index=2,
                explanation=(
                    "Appreciation is not a taxable event. This is why simply holding is tax-efficient: the "
                    "deferred tax stays invested and compounds on your behalf."
                ),
            ),
        ],
        practice=[
            NumericQuestion(
                question="You bought at $30 and sold 200 shares at $54 after 14 months. At a 15% long-term rate, what tax is owed on the gain, in dollars?",
                answer=720, tolerance=5,
                unit="$",
                hint="Work out the gain per share, multiply by shares, then apply the rate.",
                explanation=(
                    "Gain is ($54 - $30) x 200 = $4,800. At 15%, tax is $720. Had you sold at 11 months and "
                    "been in a 32% ordinary bracket, the same $4,800 gain would have cost $1,536."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "When does a capital gain become taxable?",
                ["As soon as the position rises in value", "When you sell and realize it",
                 "At the end of every calendar year", "When the company reports earnings"],
                1,
                "Only realized gains are taxed. An appreciating position you continue to hold defers the "
                "liability indefinitely, which is a real and underrated advantage of not trading.",
            ),
            QuizQuestion(
                "You sell a fund at a loss on 1 December and buy the same fund back on 20 December. What happens?",
                ["The loss is fully deductible", "The loss is disallowed as a wash sale and added to the new cost basis",
                 "The loss doubles", "Nothing; wash sale rules apply only to individual stocks"],
                1,
                "Repurchasing within 30 days either side triggers the wash sale rule. The loss is not "
                "destroyed — it moves into the replacement position's basis — but it does not offset this "
                "year's gains, which was the entire point.",
            ),
            QuizQuestion(
                "Why is frequent trading often more expensive inside a taxable account than it looks?",
                ["Brokers charge hidden commissions", "Each profitable sale realizes a gain and pulls forward tax that holding would defer",
                 "Short-term trades have wider spreads by rule", "Tax rates rise with the number of trades"],
                1,
                "Zero-commission does not mean zero-cost. Every profitable sale converts a deferred, "
                "compounding liability into a bill due this year — and if held under a year, at the higher "
                "ordinary rate.",
            ),
        ],
    ),

    # ── b010 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b010",
        title="Fees, and Why 1% Is Not a Small Number",
        category="Risk & Return",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=5,
        body=(
            "Most people evaluate a fee by comparing it to zero and concluding it is small. The "
            "correct comparison is to the return, and over time, to the compounding that fee "
            "prevents.\n\n"

            "**A fee is a percentage of your balance, not of your gains.** A 1% advisory fee on "
            "$200,000 is $2,000 a year whether the account rose 20% or fell 20%. In a bad year "
            "you pay it out of a shrinking balance. This is different from how people intuitively "
            "model it — as a cut of profits — and it is why fees hurt most exactly when you can "
            "least afford them.\n\n"

            "**The compounding argument.** Money removed as a fee is not just gone, it is gone "
            "along with everything it would have earned. $10,000 growing at 7% for 30 years "
            "becomes about $76,100. The same $10,000 at 6% — one percentage point of fee — "
            "becomes about $57,400. That single point cost roughly $18,700, or nearly a quarter "
            "of the final balance, on a fee that felt like a rounding error each year.\n\n"

            "**The fees to actually look for.** Expense ratios on funds, charged automatically and "
            "invisibly. Advisory fees, usually 0.5% to 1.5% of assets annually. Trading spreads, "
            "which never appear as a line item. Account and transfer-out fees. And, in some "
            "products, sales loads — a percentage taken off the top before a dollar is invested.\n\n"

            "**What a fee should buy.** Paying more is not automatically wrong. Financial planning, "
            "tax coordination and — genuinely — being talked out of selling everything in a panic "
            "can be worth well over 1% a year. What is not worth paying for is a fund charging "
            "0.8% to hold roughly the same companies an index fund holds for 0.04%. The question "
            "is never 'is this fee small', it is 'what am I receiving that the cheap alternative "
            "does not provide'."
        ),
        key_takeaway=(
            "A fee is charged on the balance, not the gains, and the money taken stops compounding. "
            "One percentage point over thirty years costs roughly a quarter of the final balance — "
            "which is why the right question is what the fee buys, not whether it looks small."
        ),
        glossary=[
            GlossaryTerm("advisory fee", "An annual percentage of assets charged by an adviser managing your money, typically 0.5%-1.5%."),
            GlossaryTerm("sales load", "A commission deducted when buying (front-end) or selling (back-end) certain funds, before any investment happens."),
            GlossaryTerm("fee drag", "The cumulative effect of fees on long-run returns, including the compounding forgone on money removed."),
        ],
        callouts=[
            Callout("key_idea", "Compare fees to returns, not to zero",
                "1% sounds negligible against a balance. Against a 7% return it is a seventh of your gain, "
                "every year, in good years and bad."),
        ],
        exercises=[
            Exercise(
                kind="fee_drag",
                title="One percent, thirty years",
                prompt=(
                    "Leave fee A at 0% and set fee B to 1%. Watch the gap at year 30, then shorten the "
                    "horizon to 10 years and watch it shrink. Fees and time multiply each other — which "
                    "is why this decision matters most for the youngest investors."
                ),
                params={"balance": 10000, "annual_return": 7, "years": 30, "fee_a": 0.0, "fee_b": 1.0},
            ),
        ],
        practice=[
            NumericQuestion(
                question="An adviser charges 1.2% annually on a $150,000 account. What is the fee in one year, in dollars?",
                answer=1800, tolerance=10,
                unit="$",
                hint="The fee applies to the whole balance, not to the gains.",
                explanation=(
                    "$150,000 x 0.012 = $1,800, charged whether the account gained or lost. Over ten years, "
                    "before counting the compounding forgone, that is $18,000."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "An advisory fee is normally charged on what?",
                ["Only on gains", "The total account balance, regardless of performance",
                 "Each trade placed", "Dividends received"],
                1,
                "Asset-based fees apply to the balance. In a losing year you still pay, out of a smaller "
                "account — the opposite of how most people assume it works.",
            ),
            QuizQuestion(
                "Why does a 1% fee cost far more than 1% over a long horizon?",
                ["Fees rise with inflation", "The money removed would otherwise have compounded, so the loss grows every year",
                 "Taxes are charged on fees", "Fees are deducted twice annually"],
                1,
                "Each dollar taken stops earning. Over thirty years at a 7% base return, one percentage "
                "point of fee costs roughly a quarter of the ending balance.",
            ),
        ],
    ),

    # ── b011 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b011",
        title="What Actually Moves a Stock Day to Day",
        category="Market Basics",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "New investors usually assume prices move on news about the company being good or bad. "
            "That is roughly a third of the story, and the least useful third.\n\n"

            "**Prices move on surprise, not on news.** If a company is widely expected to earn "
            "$2.00 and earns $2.00, the stock frequently does nothing — the good result was "
            "already in the price. If it earns $1.80, the stock falls, even though $1.80 is a "
            "profit. What matters is the gap between the outcome and what was already expected. "
            "This is why 'the company reported record earnings and the stock dropped' is not a "
            "paradox: records can still miss expectations.\n\n"

            "**Guidance often matters more than results.** Reported earnings describe a quarter "
            "that already happened. Guidance — management's forecast for the next one — describes "
            "the future the price is actually based on. A beat with lowered guidance regularly "
            "falls harder than a miss with raised guidance.\n\n"

            "**Rates and the macro backdrop move everything at once.** A stock is a claim on "
            "future cash. When interest rates rise, future cash is discounted more heavily, so "
            "prices fall — and companies whose profits sit furthest in the future fall most. On "
            "days when a central bank speaks, most stocks move together, and the movement says "
            "nothing about any individual business.\n\n"

            "**Flows move prices with no information at all.** Index rebalances, fund inflows, "
            "options hedging and forced selling all create real buying and selling pressure from "
            "participants who are not expressing a view. A stock added to a major index rises "
            "because index funds must buy it, not because it became a better company that "
            "afternoon.\n\n"

            "**Most daily movement is noise.** A typical large-cap moves around 1% on an ordinary "
            "day for no identifiable reason. Financial media narrates these moves anyway, because "
            "'stocks drifted for reasons nobody can isolate' is not publishable. Learning to "
            "ignore the daily narration is one of the highest-value habits available to a new "
            "investor."
        ),
        key_takeaway=(
            "Prices move on the gap between outcome and expectation, not on whether news is good. "
            "Record earnings can still miss, guidance often outweighs results, and much of the "
            "daily move is flow and noise that the financial press narrates as if it were meaning."
        ),
        glossary=[
            GlossaryTerm("guidance", "Management's own forecast for upcoming results. Frequently moves the price more than the reported quarter does."),
            GlossaryTerm("earnings surprise", "The difference between reported earnings and the consensus expectation. The surprise, not the level, is what the price reacts to."),
            GlossaryTerm("consensus estimate", "The average of analyst forecasts — the bar the market has already priced in."),
            GlossaryTerm("flows", "Buying and selling driven by mechanics like index rebalancing or fund redemptions rather than by any view on value."),
        ],
        callouts=[
            Callout("why_it_matters", "This is why headlines mislead",
                "'Company beats earnings, stock falls 8%' reads as irrational and almost never is. The beat "
                "was smaller than hoped, or guidance was cut, or the whole sector fell on rates. The "
                "headline reports the result; the price reacted to the surprise."),
            Callout("common_mistake", "Explaining every move",
                "The urge to attribute a 2% drop to a cause is strong and usually unsatisfiable. Much daily "
                "movement is the aggregate of unrelated flows. Accepting that is a skill."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=1,
                question="A company reports its highest-ever quarterly profit and the stock falls 6%. What is the most likely reason?",
                options=[
                    "The market is behaving irrationally",
                    "The result was strong but below what was already expected, or guidance disappointed",
                    "Record profits always trigger profit-taking",
                    "The exchange halted trading",
                ],
                correct_index=1,
                explanation=(
                    "The price already embedded an expectation. Beating last year while missing this "
                    "quarter's consensus is a negative surprise, however good the absolute number looks."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "A company earns exactly what analysts expected. What typically happens to the stock?",
                ["It rises, because earnings were positive", "Little — the expected result was already in the price",
                 "It falls, because there was no beat", "It becomes more volatile for a week"],
                1,
                "Prices embed expectations in advance. Meeting them delivers no new information, so there "
                "is usually little to react to.",
            ),
            QuizQuestion(
                "Why do most stocks move together on days when a central bank changes rates?",
                ["Traders panic uniformly", "Rates change how all future cash flows are discounted, which affects every company at once",
                 "Exchanges coordinate pricing", "Index funds are forced to rebalance"],
                1,
                "A stock is a claim on future cash. Changing the discount rate re-prices every such claim "
                "simultaneously, hitting long-dated growth companies hardest.",
            ),
            QuizQuestion(
                "A stock jumps 5% on being added to a major index. What does that move indicate about the business?",
                ["It just became more profitable", "Essentially nothing — index funds are mechanically required to buy it",
                 "Its risk fell", "Analysts upgraded it"],
                1,
                "Index inclusion forces buying from funds tracking that index. It is a flow event, not "
                "information about the company's operations.",
            ),
        ],
    ),

    # ── b012 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b012",
        title="Diversification Without Overcomplicating It",
        category="Risk & Return",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "Diversification is the one thing in investing that genuinely reduces risk without "
            "reducing expected return. It is also routinely done badly, in a specific way worth "
            "naming.\n\n"

            "**What it actually does.** Holding many things means no single failure can ruin you. "
            "If one position is 2% of your portfolio, a total loss costs 2%. If it is 40%, a total "
            "loss is close to unrecoverable. The benefit is not that you earn more — it is that "
            "the range of outcomes narrows, and specifically that the catastrophic tail gets "
            "cut off.\n\n"

            "**The benefit comes from things NOT moving together.** Two companies in the same "
            "industry, exposed to the same customers and the same input costs, fall together. "
            "Owning both is barely more diversified than owning one. What reduces risk is "
            "combining holdings driven by different things — which is why the useful axes are "
            "sector, geography and asset class, not simply count.\n\n"

            "**The mistake: diversification theatre.** Someone holds eight funds and feels "
            "diversified. On inspection, six are US large-cap equity funds holding substantially "
            "the same fifty companies. That is one position wearing six labels, with six expense "
            "ratios. Counting holdings measures nothing; what matters is whether they respond to "
            "different forces.\n\n"

            "**Diminishing returns arrive quickly.** Moving from one stock to twenty removes most "
            "single-company risk. Moving from twenty to two hundred removes a little more. Beyond "
            "that you are mostly adding admin. This is why a single broad index fund is a "
            "defensible entire equity allocation for many people — it is already thousands of "
            "companies.\n\n"

            "**What diversification cannot do.** In a genuine crisis, correlations rise: things "
            "that normally move independently fall together, precisely when you needed them not "
            "to. Diversification is not a hedge against systemic collapse. It is protection "
            "against being wrong about any one thing — which is the risk you are far more likely "
            "to actually face."
        ),
        key_takeaway=(
            "Diversification works because holdings respond to different forces, not because there "
            "are many of them. Six US large-cap funds holding the same fifty companies is one "
            "position with six expense ratios."
        ),
        glossary=[
            GlossaryTerm("diversification", "Spreading capital across holdings driven by different forces, so no single failure is ruinous."),
            GlossaryTerm("correlation", "How closely two holdings move together. Low correlation is what makes diversification work; correlations tend to rise in crises."),
            GlossaryTerm("concentration risk", "The risk from having too much in one position, sector or theme."),
            GlossaryTerm("systemic risk", "Risk affecting the entire market at once, which cannot be diversified away by holding more of that market."),
        ],
        callouts=[
            Callout("common_mistake", "Counting funds instead of exposures",
                "Open each fund's top ten holdings and compare. People regularly discover their 'diversified' "
                "portfolio is the same mega-caps four times over — and that they are paying four fees for "
                "one bet."),
            Callout("example", "Why position size decides survivability",
                "A position that goes to zero at 2% of the portfolio costs 2%, recoverable in a normal year. "
                "The same outcome at 40% requires a 67% gain on what remains just to get back to even."),
        ],
        practice=[
            NumericQuestion(
                question="A holding is 25% of your portfolio and goes to zero. What percentage gain on the remaining 75% is needed to get back to the original value?",
                answer=33.3, tolerance=1.0,
                unit="%",
                hint="You need to grow the remainder back to 100 from 75.",
                explanation=(
                    "You need 100/75 = 1.333, a 33.3% gain. At a 50% position it would take 100%. This "
                    "asymmetry — losses needing larger gains to undo — is the whole argument for limiting "
                    "position size."
                ),
            ),
        ],
        exercises=[
            Exercise(
                kind="drawdown_recovery",
                title="The asymmetry of losses",
                prompt=(
                    "Drag the loss from 10% to 50% to 80% and watch the required recovery. The relationship "
                    "is not linear — which is why avoiding large losses matters more than capturing large "
                    "gains."
                ),
                params={"loss_pct": 25},
            ),
        ],
        quiz=[
            QuizQuestion(
                "What makes diversification actually reduce risk?",
                ["Owning a large number of positions", "Owning things that respond to different forces",
                 "Owning only large companies", "Rebalancing frequently"],
                1,
                "The benefit comes from imperfect correlation. Many holdings that all move together provide "
                "very little of it.",
            ),
            QuizQuestion(
                "A portfolio holds six US large-cap funds. What is the most likely problem?",
                ["Too few positions", "Substantial overlap — largely the same companies, with six fees",
                 "Excessive international exposure", "Insufficient trading"],
                1,
                "US large-cap funds hold heavily overlapping mega-caps. The portfolio has one real exposure "
                "and six expense ratios paying for it.",
            ),
            QuizQuestion(
                "What happens to correlations during a severe market crisis?",
                ["They fall, improving diversification", "They rise, so holdings fall together",
                 "They stay constant", "They become undefined"],
                1,
                "Correlations tend toward one in a crisis. Diversification helps least exactly when it would "
                "help most — which is why it protects against being wrong about one thing, not against "
                "systemic collapse.",
            ),
        ],
    ),

    # ── b013 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b013",
        title="The Four Traps That Cost Beginners the Most",
        category="Risk & Return",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "Most of the money new investors lose is not lost to bad analysis. It is lost to four "
            "predictable behaviours, each of which feels completely reasonable at the time.\n\n"

            "**1. Selling in the drop, buying in the rally.** The most expensive habit in "
            "investing. A falling market feels dangerous, so people sell; a rising one feels safe, "
            "so they buy back higher. Studies of investor returns versus fund returns consistently "
            "find a gap of one to two percentage points a year attributable to this timing alone — "
            "the funds performed, the investors did not, because of when they were in them.\n\n"

            "**2. Loss aversion, and holding losers to avoid admitting them.** A loss hurts "
            "roughly twice as much as an equivalent gain feels good. The practical consequence is "
            "that people sell winners early to bank a good feeling, and hold losers indefinitely "
            "because selling makes the loss real. This is backwards from a tax perspective and "
            "usually backwards from an investment one. The market does not know your purchase "
            "price, and your cost basis has no bearing on what the position is worth tomorrow.\n\n"

            "**3. Recency bias.** Whatever has happened lately feels like what happens generally. "
            "After three good years, risk feels theoretical and people lever up. After a crash, "
            "recovery feels impossible and people stay in cash through the rebound. Both are the "
            "same error: treating a recent sample as the whole distribution.\n\n"

            "**4. Confusing a good outcome with a good decision.** A concentrated bet that pays "
            "off feels like skill and is remembered as such. But a decision with a 20% chance of "
            "working is a bad decision even on the occasions it works. Judging yourself on "
            "outcomes rather than process means learning the wrong lesson from your luckiest "
            "trades — and then repeating it with more money.\n\n"

            "**What actually helps.** Not willpower — a written plan made in advance, when you are "
            "calm, about what you will do when things fall. Automating contributions so the "
            "decision is not re-made monthly. Checking the portfolio less often, since more "
            "frequent checking demonstrably increases trading and decreases returns. And keeping "
            "a short record of why you bought something, so that later you can tell whether you "
            "were right for your reasons or lucky for someone else's."
        ),
        key_takeaway=(
            "The gap between fund returns and investor returns is behaviour, not analysis. A plan "
            "written while calm about what you will do in a drawdown is worth more than any "
            "amount of resolve summoned during one."
        ),
        glossary=[
            GlossaryTerm("loss aversion", "The tendency for losses to hurt about twice as much as equivalent gains please, which pushes people to hold losers and sell winners."),
            GlossaryTerm("recency bias", "Over-weighting recent experience as if it represented the full range of outcomes."),
            GlossaryTerm("disposition effect", "The documented pattern of selling winners too early and holding losers too long."),
            GlossaryTerm("drawdown", "A peak-to-trough decline, and the moment at which these behaviours become expensive."),
        ],
        callouts=[
            Callout("key_idea", "Your cost basis is not information",
                "What you paid affects your tax bill and nothing else. A position is worth holding or not "
                "based on what it will do from here — a fact entirely independent of whether you happen "
                "to be up or down on it."),
            Callout("why_it_matters", "Decide before, not during",
                "Nobody makes a clear-headed decision during a 30% drawdown. The decision that matters was "
                "made months earlier, when you chose an allocation you could actually sit through."),
        ],
        checkpoints=[
            Checkpoint(
                after_paragraph=2,
                question="You hold two positions: one up 30%, one down 30%. You need cash. Which does your instinct push you toward selling, and is that instinct reliable?",
                options=[
                    "The winner — and yes, banking gains is always right",
                    "The winner — and no; the instinct is the disposition effect, not analysis",
                    "The loser — and yes, cutting losses is always right",
                    "Neither; the decision is arbitrary",
                ],
                correct_index=1,
                explanation=(
                    "Most people sell the winner to make the gain real and keep the loser to avoid making the "
                    "loss real. Which to sell should depend on each position's prospects and the tax "
                    "consequence, not on which one flatters you."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "What mostly explains the gap between fund returns and the returns investors in those funds actually earn?",
                ["Hidden fees", "Investor timing — buying after rises and selling after falls",
                 "Tracking error", "Currency effects"],
                1,
                "The funds delivered their returns; investors were not consistently in them. Money tends to "
                "arrive after good performance and leave after bad, which mechanically buys high and sells low.",
            ),
            QuizQuestion(
                "Why is your original purchase price irrelevant to whether you should hold a position now?",
                ["Because brokers do not track it", "Because the future return depends on the price from here, not on what you paid",
                 "Because it changes with dividends", "It is not irrelevant — it sets your target"],
                1,
                "The market has no memory of your entry. Future returns are driven by current price versus "
                "future value; your basis affects only your tax outcome.",
            ),
            QuizQuestion(
                "A concentrated bet with a small chance of success pays off enormously. What should you conclude?",
                ["The decision was skilful and should be repeated", "The outcome was good but the decision may still have been poor",
                 "Concentration is generally superior", "Nothing can be learned from a single trade"],
                1,
                "Outcome and decision quality are different things. Judging by outcomes teaches you to repeat "
                "low-probability bets, with the size increasing each time confidence does.",
            ),
        ],
    ),

    # ── b014 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b014",
        title="Dollar-Cost Averaging vs Investing It All At Once",
        category="Risk & Return",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=5,
        body=(
            "You have a lump sum — an inheritance, a bonus, savings you finally moved. Do you "
            "invest it all today, or spread it over the next twelve months? This question has a "
            "clear mathematical answer and a completely different practical one, and both are "
            "worth understanding.\n\n"

            "**What the math says.** Markets rise more often than they fall. Money invested "
            "earlier is exposed to that upward drift for longer. So investing the lump sum "
            "immediately beats spreading it out roughly two thirds of the time, and by a "
            "meaningful margin on average. On expected value alone, all-at-once wins.\n\n"

            "**What the math omits.** The one third of the time it loses, it can lose badly — and "
            "you experience that as having invested everything the week before a 25% decline. The "
            "person who does that at the start of their investing life frequently does not stay "
            "invested. A strategy with a slightly lower expected return that you will actually "
            "hold through is superior to an optimal one you will abandon.\n\n"

            "**What dollar-cost averaging actually buys.** Not higher returns — lower regret. By "
            "spreading purchases you guarantee an average entry price rather than a single one, "
            "which removes the possibility of the worst-case entry, and with it much of the "
            "anxiety that causes people to sell. It is insurance, and like most insurance it costs "
            "a little expected return.\n\n"

            "**A distinction that matters.** Investing every paycheque is not dollar-cost "
            "averaging in this sense — that is simply investing money as it arrives, which is "
            "unambiguously correct and has no lump-sum alternative. The comparison only applies "
            "when you already hold the whole amount and are choosing how fast to deploy it.\n\n"

            "**A reasonable middle.** Deploy a meaningful share immediately and the rest on a "
            "fixed schedule over three to six months, decided in advance and followed regardless "
            "of what the market does. The schedule is the important part: 'I'll invest the rest "
            "when things look better' is market timing, and things never look better at the "
            "bottom."
        ),
        key_takeaway=(
            "Investing a lump sum immediately wins about two thirds of the time and on average. "
            "Spreading it buys lower regret, not higher returns — and a strategy you will actually "
            "stay invested in beats an optimal one you abandon."
        ),
        glossary=[
            GlossaryTerm("dollar-cost averaging", "Deploying a fixed amount at regular intervals, producing an average entry price instead of a single one."),
            GlossaryTerm("lump-sum investing", "Investing the entire available amount immediately."),
            GlossaryTerm("expected value", "The probability-weighted average outcome — what a decision is worth on average across many repetitions."),
        ],
        callouts=[
            Callout("key_idea", "Optimal on paper loses to sustainable in practice",
                "The best strategy is the one you will still be following after a bad year. That is not a "
                "concession to weakness; it is a real constraint that belongs in the decision."),
            Callout("common_mistake", "Waiting for a better entry",
                "Deploying the remainder 'when things settle down' is timing with extra steps. Conditions "
                "look worst precisely at the points that turn out to have been good entries."),
        ],
        exercises=[
            Exercise(
                kind="dollar_cost_average",
                title="Same money, two schedules",
                prompt=(
                    "Run both approaches over the same price path, then change the path shape. Note that "
                    "DCA wins when the market falls then recovers, and loses when it simply rises — and "
                    "that you cannot know which you are in beforehand."
                ),
                params={"amount": 12000, "months": 12, "scenario": "dip_then_recover"},
            ),
        ],
        quiz=[
            QuizQuestion(
                "Investing a lump sum immediately rather than spreading it out usually produces a higher return. Why?",
                ["Trading costs are lower", "Markets rise more often than they fall, so earlier money is exposed to that drift for longer",
                 "It avoids taxes", "Brokers give better fills on large orders"],
                1,
                "The upward drift is the whole reason. More time invested means more exposure to it, which "
                "is why all-at-once wins around two thirds of the time.",
            ),
            QuizQuestion(
                "What does dollar-cost averaging actually provide?",
                ["A higher expected return", "Protection against the worst-case entry price, at some cost to expected return",
                 "Immunity from market declines", "Lower taxes"],
                1,
                "It is insurance against a single bad entry. Like insurance it has a premium, paid in "
                "slightly lower average returns.",
            ),
            QuizQuestion(
                "You invest part of every paycheque. Is that the same trade-off as this lesson describes?",
                ["Yes, identical", "No — you are investing money as it arrives; there is no lump sum to deploy differently",
                 "Yes, but only in a taxable account", "No, because paycheques are not lump sums by definition"],
                1,
                "The comparison only exists when you already hold the full amount. Investing income as you "
                "receive it has no alternative to be compared against.",
            ),
        ],
    ),

    # ── b015 ──────────────────────────────────────────────────────────────
    Lesson(
        id="b015",
        title="Reading an Earnings Report Without a Finance Degree",
        category="Market Basics",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=7,
        body=(
            "Four times a year a public company publishes its results. The report is long and "
            "written for professionals, but the parts that matter to you are few and always in "
            "the same places.\n\n"

            "**Revenue — the top line.** Total sales for the quarter. The number itself means "
            "little without context; what matters is the direction and the rate. Growing 3% a "
            "year is a different business from growing 30%, and a company whose revenue is "
            "shrinking has a problem no cost-cutting fixes permanently.\n\n"

            "**Net income — the bottom line.** What is left after every cost. Positive is better "
            "than negative, but this figure is the most manipulable one on the page, because it "
            "includes one-off items: a legal settlement, a writedown, a gain from selling a "
            "building. A quarter can swing from profit to loss on something that will never "
            "recur.\n\n"

            "**Margins — the number that actually tells you about quality.** Gross margin is "
            "revenue minus the direct cost of producing the product, as a percentage. Operating "
            "margin subtracts the cost of running the business too. A software company might hold "
            "an 80% gross margin; a grocer 25%. Neither is 'better' — but a company whose margin "
            "is falling year over year is losing pricing power, and that is a genuine warning "
            "regardless of what net income did.\n\n"

            "**Free cash flow — the hardest number to fake.** Cash generated by operations minus "
            "what was spent on equipment and facilities. Profit is an accounting opinion in a way "
            "cash is not: revenue can be recognised before payment arrives, and costs can be "
            "spread across years. A company reporting rising profit alongside falling free cash "
            "flow is worth looking at closely — that divergence precedes a large share of "
            "accounting problems.\n\n"

            "**Guidance — what the price will actually react to.** Management's forecast for next "
            "quarter and the year. This describes the future, which is what the stock is priced "
            "on. A strong quarter with weak guidance frequently falls.\n\n"

            "**Where to look first.** Read the guidance, then the margin trend, then free cash "
            "flow. Only then the headline earnings-per-share number that the news will lead with. "
            "That ordering is roughly the inverse of how the information is presented to you, and "
            "roughly the order of how much it tells you."
        ),
        key_takeaway=(
            "Read guidance, margin trend and free cash flow before the headline EPS the news leads "
            "with. Profit is an accounting opinion; cash is much harder to present flatteringly, "
            "and rising profit alongside falling cash flow is a warning."
        ),
        glossary=[
            GlossaryTerm("revenue", "Total sales in the period, before any costs. Also called the top line."),
            GlossaryTerm("net income", "Profit after every expense. Also called the bottom line, and the figure most affected by one-off items."),
            GlossaryTerm("gross margin", "Revenue minus the direct cost of producing the product, as a percentage of revenue. A proxy for pricing power."),
            GlossaryTerm("operating margin", "Profit after both production and operating costs, as a percentage of revenue."),
            GlossaryTerm("free cash flow", "Cash from operations minus capital spending. Harder to manipulate than reported profit."),
            GlossaryTerm("EPS", "Earnings per share — net income divided by shares outstanding. Can rise purely from buybacks reducing the share count."),
        ],
        callouts=[
            Callout("why_it_matters", "EPS can rise while the business does not",
                "Earnings per share is profit divided by share count. A company buying back shares raises EPS "
                "with flat profit. That is not necessarily bad, but it is not growth either — and the "
                "headline will not distinguish them."),
            Callout("common_mistake", "Reading net income alone",
                "One-off items live in net income. A quarter can look transformed by a single asset sale or "
                "legal charge. Margins and cash flow are far more informative about whether the underlying "
                "business changed."),
        ],
        practice=[
            NumericQuestion(
                question="A company reports revenue of $500 million and cost of goods sold of $180 million. What is its gross margin, as a percentage?",
                answer=64, tolerance=0.6,
                unit="%",
                hint="Gross profit divided by revenue.",
                explanation=(
                    "Gross profit is $500m - $180m = $320m. $320m / $500m = 64%. Tracking that figure across "
                    "several quarters says more about competitive position than any single quarter's profit."
                ),
            ),
        ],
        quiz=[
            QuizQuestion(
                "Why is free cash flow often more informative than reported net income?",
                ["It is always larger", "It is harder to manipulate — cash either moved or it did not",
                 "It excludes taxes", "Regulators audit it more closely"],
                1,
                "Revenue recognition and cost allocation give real latitude over reported profit. Cash "
                "movement is far more concrete, which is why a divergence between the two is a warning.",
            ),
            QuizQuestion(
                "A company's gross margin has fallen from 45% to 38% over two years while revenue grew. What does that most likely suggest?",
                ["The company is more profitable", "It is losing pricing power or facing rising input costs",
                 "It bought back shares", "Nothing; margins fluctuate randomly"],
                1,
                "Growing revenue at a falling margin often means buying growth through price. It is a "
                "competitive-position signal that headline revenue growth hides.",
            ),
            QuizQuestion(
                "EPS rose 10% while net income was flat. What most likely happened?",
                ["Revenue grew 10%", "The share count fell, probably through buybacks",
                 "Margins expanded", "The company issued new shares"],
                1,
                "EPS is profit per share. With profit unchanged, a higher EPS means fewer shares — typically "
                "buybacks. Real, but not the same as the business earning more.",
            ),
        ],
    ),
]
