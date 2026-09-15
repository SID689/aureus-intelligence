"""
app/lessons/tier0_beginner.py
-------------------------------
MODULE 0 — "New to Investing"

The only tier that assumes ZERO prior knowledge. Every other tier in this
curriculum starts from "you've placed trades before"; this one starts from
"you have never bought a stock and aren't sure what one is."

Editorial rules for this tier, which differ from the rest:
  1. No unexplained jargon. Every term of art gets defined inline the first
     time it appears (see the `glossary` on each lesson).
  2. Concrete numbers over abstractions. A beginner learns "the spread cost
     you $10" far faster than "the spread represents transaction friction."
  3. Never imply a recommendation. This is the tier most likely to be read
     by someone who will act on it literally, so the compliance bar is
     higher here, not lower — explain mechanics, never suggest what to buy.
  4. Name the common beginner mistake explicitly. Most of the damage new
     investors do is from a small set of predictable errors.
"""

from app.lessons.models import Callout, GlossaryTerm, Lesson, QuizQuestion, TIER_BEGINNER

TIER_0_BEGINNER: list[Lesson] = [

    # ── Lesson 1 ──────────────────────────────────────────────────────────
    Lesson(
        id="b001",
        title="How the Stock Market Actually Works",
        category="Market Basics",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "A share of stock is a unit of ownership in a company. If a company has issued one "
            "billion shares and you own one hundred of them, you own one ten-millionth of that "
            "business, including a claim on its future profits. That's it. Everything else about "
            "the stock market is machinery for transferring those ownership units between people.\n\n"

            "**Where the trading happens.** An exchange (the NYSE, Nasdaq) is a regulated venue that "
            "matches buyers with sellers. It doesn't set prices and it doesn't own the shares: it "
            "runs the matching process and publishes the results. When you press 'buy' in a broker "
            "app, your order is routed to an exchange or to a market maker, matched against someone "
            "willing to sell, and the trade is recorded. The whole round trip usually takes "
            "milliseconds.\n\n"

            "**Who is on the other side.** Every trade has exactly two sides. For you to buy 100 "
            "shares, someone must sell 100 shares. This sounds obvious but it has an important "
            "consequence people miss: the price is not a fact about the company, it's the point "
            "where the most recent buyer and seller agreed. When you read 'the stock is at $150,' "
            "that means the last trade happened at $150, not that $150 is what the company is worth.\n\n"

            "**Market makers.** If every trade needed a matching human on the other side at the exact "
            "same moment, most stocks would be nearly impossible to trade. Market makers solve this. "
            "A market maker is a firm that continuously offers to both buy and sell a stock, holding "
            "inventory to bridge the gap in timing between real buyers and real sellers. They are not "
            "doing this as a service: they earn the bid-ask spread.\n\n"

            "**The bid-ask spread.** At any moment a stock has two prices, not one:\n"
            "  - The **bid**: the highest price anyone is currently willing to PAY.\n"
            "  - The **ask** (or offer): the lowest price anyone is currently willing to SELL at.\n\n"
            "The ask is always higher than the bid. The gap between them is the spread, and it is a "
            "real cost you pay on every round trip. If the bid is $99.95 and the ask is $100.05, you "
            "buy at $100.05 and, if you turned around and sold instantly, you'd sell at $99.95. "
            "You would be down $0.10 per share before the price moved at all.\n\n"

            "Heavily traded large companies typically have spreads of a penny or two on a $100 stock. "
            "Thinly traded small companies can have spreads of several percent. That difference is one "
            "of the most underrated costs in investing, because it never appears on a statement as a "
            "fee: it's baked into the price you got."
        ),
        key_takeaway=(
            "A stock price is just where the last buyer and seller agreed, and there are always two "
            "prices, the bid and the ask. The gap between them is a real cost you pay on every trade, "
            "even though it never shows up as a fee."
        ),
        glossary=[
            GlossaryTerm("share", "One unit of ownership in a company. Owning shares makes you a part-owner with a claim on future profits."),
            GlossaryTerm("exchange", "A regulated venue (NYSE, Nasdaq) that matches buyers and sellers and publishes the resulting prices."),
            GlossaryTerm("market maker", "A firm that continuously quotes both a buy and a sell price for a stock, providing liquidity and earning the spread."),
            GlossaryTerm("bid", "The highest price a buyer is currently willing to pay for a stock."),
            GlossaryTerm("ask", "The lowest price a seller is currently willing to accept. Always higher than the bid."),
            GlossaryTerm("spread", "The gap between the bid and the ask. An invisible but real transaction cost."),
            GlossaryTerm("liquidity", "How easily you can buy or sell without moving the price. High liquidity means tight spreads and lots of willing counterparties."),
        ],
        callouts=[
            Callout("example", "The spread, in dollars",
                "You buy 100 shares of a stock quoted $99.95 bid / $100.05 ask. You pay the ask: "
                "$10,005. If you immediately changed your mind and sold, you'd receive the bid: $9,995. "
                "That $10 round-trip cost is the spread. On a liquid mega-cap it might be $1; on an "
                "illiquid small-cap with a $0.50 spread it would be $50."),
            Callout("common_mistake", "Assuming the quoted price is the price you'll get",
                "The single number you see in a stock app is usually the last traded price. The price "
                "YOU get is the ask if you're buying and the bid if you're selling. On liquid stocks "
                "the difference is trivial. On illiquid ones it is not."),
        ],
        quiz=[
            QuizQuestion(
                "The bid is $49.90 and the ask is $50.10. You place an order to buy immediately. What price do you most likely pay?",
                ["$49.90", "$50.00", "$50.10", "Whichever is closest to the last trade"],
                2,
                "Buyers pay the ask (the lowest price a seller will accept), which is $50.10. Sellers receive the bid. "
                "The $0.20 gap is the spread: a cost you absorb on entry and again on exit.",
            ),
            QuizQuestion(
                "What does a market maker primarily earn from providing liquidity?",
                ["A commission charged to the exchange", "The bid-ask spread", "A fee paid by the company whose stock they quote", "Dividends on inventory they hold"],
                1,
                "Market makers quote both sides and profit from the spread between them. They're not performing a "
                "public service: the spread is their compensation for holding inventory and bearing the risk that "
                "prices move against them.",
            ),
            QuizQuestion(
                "A stock's price shows $150. What does that most accurately tell you?",
                ["The company is worth $150 per share", "The most recent buyer and seller agreed on $150", "$150 is the price you can buy at right now", "An analyst valued the company at $150"],
                1,
                "A quoted price is a record of the last transaction, not a valuation and not a guarantee of your fill. "
                "To buy right now you'd pay the ask, which is slightly higher.",
            ),
        ],
    ),

    # ── Lesson 2 ──────────────────────────────────────────────────────────
    Lesson(
        id="b002",
        title="The Core Asset Classes: Stocks, Bonds, ETFs, and Commodities",
        category="Asset Classes",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=7,
        body=(
            "Different asset classes behave differently because they represent structurally different "
            "claims. Understanding what you actually own explains most of why an investment behaves the "
            "way it does.\n\n"

            "**Stocks (equities): you own a piece of the business.**\n"
            "As a shareholder you have a residual claim: you get what's left after employees, suppliers, "
            "and lenders are paid. That's why stocks have the highest long-run return potential AND the "
            "most downside: if the business does spectacularly, there's no cap on your upside; if it "
            "goes bankrupt, shareholders are last in line and typically recover nothing. Some companies "
            "pay out part of their profit as a **dividend**; many reinvest it all instead.\n\n"

            "**Bonds (fixed income): you are the lender.**\n"
            "A bond is a loan. You give an issuer (a government or a company) money; they contractually "
            "owe you periodic interest and your principal back at maturity. You do NOT participate in "
            "the upside: if the company triples in value, your bond still just pays what it promised. "
            "In exchange, you're ahead of shareholders if things go badly. Bonds are generally less "
            "volatile than stocks, but they are not risk-free: the issuer can default, and bond prices "
            "fall when prevailing interest rates rise.\n\n"

            "**ETFs: a wrapper, not an asset class.**\n"
            "An exchange-traded fund is a single ticker that holds a basket of underlying assets. Buying "
            "one share of a broad stock-market ETF gives you fractional exposure to hundreds or thousands "
            "of companies at once. This is the most accessible route to **diversification**: the single "
            "highest-value concept for a new investor. Important: an ETF is a container. An S&P 500 ETF "
            "and a leveraged natural-gas ETF are both 'ETFs' and have nothing else in common. Always look "
            "at what's inside.\n\n"

            "**Commodities: physical goods.**\n"
            "Oil, gold, wheat, copper. Commodities produce no cash flow: a bar of gold will never pay "
            "you a dividend or interest. That makes them fundamentally harder to value than a business "
            "or a loan: the return depends entirely on someone paying more later. Most retail exposure "
            "comes through ETFs holding futures contracts, which introduces costs beyond the commodity's "
            "own price movement.\n\n"

            "**Why the mix matters more than the picks.** A large body of research finds that the split "
            "between asset classes explains far more of a portfolio's return variability over time than "
            "individual security selection does. Which stocks you own matters less than how much you hold "
            "in stocks versus bonds versus cash."
        ),
        key_takeaway=(
            "Stocks make you an owner with unlimited upside and last claim in bankruptcy; bonds make you "
            "a lender with capped upside and a earlier claim. ETFs are containers that can hold either. "
            "How you split across these matters more than which specific names you pick."
        ),
        glossary=[
            GlossaryTerm("equity", "Another word for stock: an ownership stake in a company."),
            GlossaryTerm("dividend", "A cash payment some companies distribute to shareholders out of profits."),
            GlossaryTerm("bond", "A loan to a government or company that pays interest and returns principal at maturity."),
            GlossaryTerm("principal", "The original amount lent, repaid to the bondholder at maturity."),
            GlossaryTerm("maturity", "The date a bond's principal is scheduled to be repaid."),
            GlossaryTerm("default", "When a borrower fails to make promised interest or principal payments."),
            GlossaryTerm("ETF", "Exchange-traded fund: one ticker that holds a basket of underlying assets, tradeable like a stock."),
            GlossaryTerm("diversification", "Spreading money across many holdings so no single failure can badly damage the whole portfolio."),
            GlossaryTerm("asset allocation", "How a portfolio is split across asset classes (stocks/bonds/cash). Historically the dominant driver of return variability."),
        ],
        callouts=[
            Callout("key_idea", "Owner vs. lender is the whole distinction",
                "Nearly every difference between stocks and bonds follows from one fact: shareholders own "
                "the residual (unlimited upside, last in line), bondholders own a contract (fixed upside, "
                "earlier in line). If you remember only that, you can reason out the rest."),
            Callout("common_mistake", "Treating 'ETF' as a synonym for 'safe' or 'diversified'",
                "An ETF is just a legal wrapper. A total-market index ETF holding 3,000 companies and a "
                "single-sector leveraged ETF are both ETFs. The wrapper tells you nothing about the risk "
                "inside it: the holdings do."),
        ],
        quiz=[
            QuizQuestion(
                "A company you invested in goes bankrupt. Who is paid first from whatever assets remain?",
                ["Shareholders, because they own the company", "Bondholders, because they are lenders with a contractual claim", "Both are paid equally and simultaneously", "Whoever invested earliest"],
                1,
                "Bondholders are creditors and sit ahead of shareholders in the capital structure. Shareholders hold "
                "the residual claim: they receive only what's left after all creditors are satisfied, which in a "
                "bankruptcy is frequently nothing.",
            ),
            QuizQuestion(
                "Which best describes an ETF?",
                ["A type of government bond", "A container that holds a basket of underlying assets, traded like a stock", "A guaranteed-return savings product", "A commodity contract"],
                1,
                "An ETF is a wrapper, not an asset class. Its risk depends entirely on what it holds: a broad index "
                "ETF and a leveraged single-commodity ETF share a structure and nothing else.",
            ),
            QuizQuestion(
                "Why are commodities like gold structurally harder to value than a stock or a bond?",
                ["They are illegal to hold directly", "They produce no cash flow, so return depends entirely on resale price", "Their prices never change", "They always lose money over time"],
                1,
                "Stocks have earnings and bonds have contractual interest: both generate cash you can discount to a "
                "value. A commodity generates none, so its valuation rests entirely on what someone will pay later.",
            ),
        ],
    ),

    # ── Lesson 3 ──────────────────────────────────────────────────────────
    Lesson(
        id="b003",
        title="Compounding, Risk, and Why Time Horizon Changes Everything",
        category="Risk & Return",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=7,
        body=(
            "**Compounding is growth on growth.** If you invest $10,000 and it grows 8% in a year, you "
            "have $10,800. The next year's 8% is calculated on $10,800, not on your original $10,000: "
            "so you earn $864 instead of $800. That extra $64 is trivial. Repeated for thirty years, it "
            "is the entire game.\n\n"

            "At a constant 8%, $10,000 becomes roughly $21,600 after 10 years, roughly $46,600 after 20 "
            "years, and roughly $100,600 after 30 years. Note the shape: the third decade adds far more "
            "dollars than the first two combined, despite being the same length and the same rate. "
            "Compounding is not linear, and almost all of its power is back-loaded. This is why time in "
            "the market is the variable a new investor has the most control over.\n\n"

            "**Risk and return are linked, and not optionally.** Higher expected returns exist as "
            "compensation for bearing something unpleasant, usually volatility, the risk of permanent "
            "loss, or the inability to access your money. If someone offers high returns with no risk, "
            "the risk hasn't been removed; it's been hidden or misrepresented. This is the single most "
            "reliable heuristic in finance.\n\n"

            "**Two different things called 'risk.'** These get conflated constantly:\n"
            "  - **Volatility**: how much the value bounces around. Uncomfortable, but temporary if you "
            "don't sell.\n"
            "  - **Permanent loss of capital**: the money is genuinely gone (a bankruptcy, a fraud). No "
            "recovery, regardless of patience.\n\n"
            "A diversified index fund has significant volatility and very low risk of total permanent "
            "loss. A single speculative company can have both. Confusing the two leads people to panic-sell "
            "temporary volatility while ignoring genuine permanent-loss risk.\n\n"

            "**Diversification is the one nearly-free improvement.** Spreading across many uncorrelated "
            "holdings reduces the damage any single failure can do, without a matching reduction in "
            "expected return. It cannot protect you from a market-wide decline, when everything falls "
            "together, diversification across stocks doesn't help, but it reliably protects you from "
            "being wiped out by one company's specific disaster.\n\n"

            "**Time horizon determines appropriate risk.** Money you need in 18 months and money you "
            "won't touch for 30 years should not be invested the same way, because a volatile asset "
            "needs time to recover from a drawdown. The shorter the horizon, the less tolerance you have "
            "for an asset that can be down 30% at the exact moment you need it."
        ),
        key_takeaway=(
            "Compounding's power is heavily back-loaded, so time invested is the variable you control "
            "most. Distinguish volatility (temporary, survivable) from permanent loss (unrecoverable): "
            "and match how much risk you take to when you'll actually need the money."
        ),
        glossary=[
            GlossaryTerm("compounding", "Earning returns on your previous returns, not just your original principal. Its effect accelerates over time."),
            GlossaryTerm("volatility", "How much an investment's value fluctuates. High volatility means large swings in both directions."),
            GlossaryTerm("drawdown", "A decline from a previous peak value, usually quoted as a percentage."),
            GlossaryTerm("permanent loss of capital", "Money that is genuinely unrecoverable, as distinct from a temporary paper decline."),
            GlossaryTerm("time horizon", "How long until you need to spend the money. Shorter horizons justify less volatile assets."),
            GlossaryTerm("correlation", "How closely two investments move together. Diversification works best across low-correlation holdings."),
        ],
        callouts=[
            Callout("example", "Why starting earlier beats contributing more",
                "Person A invests $5,000/year for 10 years starting at 25, then stops entirely. Person B "
                "invests $5,000/year for 30 years starting at 35. At 8%, Person A contributed $50,000 and "
                "Person B contributed $150,000, yet by 65 their balances end up broadly comparable. "
                "Person A's money simply had more time to compound."),
            Callout("why_it_matters", "The 'no risk, high return' filter",
                "Because return is compensation for risk, any pitch offering high returns with no risk is "
                "either misdescribing the risk or is a fraud. This one heuristic screens out a large share "
                "of what harms new investors."),
        ],
        quiz=[
            QuizQuestion(
                "Why does compounding add far more dollars in year 30 than in year 3, at the same rate?",
                ["Interest rates rise over time", "Each year's return is calculated on a progressively larger balance", "Taxes decrease over time", "Markets are more predictable long-term"],
                1,
                "The rate is constant, but the base it applies to grows every year. That's why compounding curves "
                "upward instead of rising in a straight line, and why its benefit is concentrated in later years.",
            ),
            QuizQuestion(
                "A diversified index fund drops 25% during a market-wide selloff. Which risk is this primarily an example of?",
                ["Permanent loss of capital", "Volatility", "Default risk", "Liquidity risk"],
                1,
                "A broad market decline is volatility: painful, but historically recoverable if you don't sell. "
                "Permanent loss means the capital is genuinely gone, as in a bankruptcy, where waiting doesn't help.",
            ),
            QuizQuestion(
                "What can diversification across many stocks NOT protect you from?",
                ["A single company's accounting fraud", "One industry collapsing", "A broad market-wide decline", "A single stock going to zero"],
                2,
                "Diversification removes company-specific and sector-specific risk, but market-wide (systematic) risk "
                "hits everything at once. Reducing that requires different asset classes, not more stocks.",
            ),
            QuizQuestion(
                "You need a house down payment in 18 months. What does that short time horizon most directly imply?",
                ["You should take more risk to reach the goal faster", "You have less capacity to absorb a large drawdown, since there's little time to recover", "Time horizon is irrelevant to asset choice", "You should buy only individual stocks"],
                1,
                "A volatile asset needs time to recover from a decline. With 18 months, a 30% drawdown at the wrong "
                "moment can't be waited out: the short horizon itself constrains how much volatility is appropriate.",
            ),
        ],
    ),

    # ── Lesson 4 ──────────────────────────────────────────────────────────
    Lesson(
        id="b004",
        title="Order Types: Market, Limit, Stop-Loss, and Slippage",
        category="Order Execution",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=6,
        body=(
            "An order type tells your broker HOW to execute, not just what to buy. Choosing wrong is one "
            "of the most common and most avoidable ways new investors lose money unnecessarily.\n\n"

            "**Market order: prioritizes speed, not price.**\n"
            "'Buy 100 shares at whatever the market is offering right now.' It will almost certainly fill "
            "immediately. What it does NOT do is guarantee a price. In a calm, liquid stock the fill will "
            "be within a cent or two of the quote. In a fast-moving or thinly traded stock, it can fill "
            "meaningfully worse than the price you saw when you clicked.\n\n"

            "**Limit order: prioritizes price, not speed.**\n"
            "'Buy 100 shares, but pay no more than $50.00.' You control the worst price you'll accept. "
            "The tradeoff: it may not fill at all. If the stock never trades at or below your limit, you "
            "simply don't get the shares. A limit order is a cap, not a target: if the market is at "
            "$49.50 and you set a $50.00 buy limit, you'll fill around $49.50, not $50.00.\n\n"

            "**Stop-loss: a trigger, not a guarantee.**\n"
            "'If the price falls to $45, sell.' A stop-loss sits dormant until the trigger price is "
            "touched, at which point it typically converts into a market order. This is the part people "
            "misunderstand: the stop sets when you start selling, not the price you get. If bad news "
            "gaps a stock from $46 straight to $38 with no trading in between, your $45 stop triggers "
            "and fills near $38.\n\n"

            "**Slippage: the gap between expected and actual.**\n"
            "Slippage is the difference between the price you expected and the price you actually got. "
            "It comes from the spread, from the market moving between your click and the fill, and from "
            "your order being large enough to exhaust available shares at the best price. It's usually "
            "negligible on liquid large-caps and can be severe on illiquid names, at the market open, or "
            "during news events.\n\n"

            "**The practical default.** For liquid, widely-traded stocks, a market order's slippage is "
            "typically trivial. For anything thinly traded, anything volatile, or any order large relative "
            "to normal volume, a limit order protects you from a genuinely bad fill for the cost of "
            "possibly not filling at all."
        ),
        key_takeaway=(
            "Market orders guarantee execution but not price; limit orders guarantee price but not "
            "execution. A stop-loss controls WHEN you start selling, never the price you get: in a "
            "gap-down it can fill far below your stop."
        ),
        glossary=[
            GlossaryTerm("market order", "An order to execute immediately at the best available price. Guarantees a fill, not a price."),
            GlossaryTerm("limit order", "An order with a worst-acceptable price. Guarantees the price, not that it fills."),
            GlossaryTerm("stop-loss", "A resting order that triggers a sale once a set price is reached. Controls timing, not fill price."),
            GlossaryTerm("slippage", "The difference between the price you expected and the price you actually received."),
            GlossaryTerm("fill", "The completed execution of your order."),
            GlossaryTerm("gap", "When a price jumps between two levels with no trading in between, usually overnight or on news."),
            GlossaryTerm("order book", "The live list of resting buy and sell orders at each price level."),
        ],
        callouts=[
            Callout("common_mistake", "Believing a stop-loss caps your loss at the stop price",
                "A stop-loss at $45 does not mean you lose no more than the move to $45. If overnight news "
                "reopens the stock at $38, your stop triggers into a market order and fills near $38. "
                "Stop-losses manage discipline and typical-case risk, not gap risk."),
            Callout("example", "When a market order costs real money",
                "A thinly traded stock shows a $10.00 bid / $10.60 ask. You market-buy 500 shares. You pay "
                "the ask and possibly worse as you consume the limited shares available there: perhaps an "
                "average of $10.75. A limit order at $10.20 might have filled patiently over an hour, saving "
                "roughly $275 on the same position."),
        ],
        quiz=[
            QuizQuestion(
                "What does a market order guarantee?",
                ["The price you'll pay", "That your order will execute, at whatever price is available", "Both price and execution", "That you'll get the bid price"],
                1,
                "Market orders trade price certainty for execution certainty. You'll almost always get filled: the "
                "open question is at what price, especially in fast or illiquid markets.",
            ),
            QuizQuestion(
                "You set a stop-loss at $45. Overnight, bad news causes the stock to open at $37 with no trades in between. What most likely happens?",
                ["You sell at exactly $45", "Your order is cancelled automatically", "The stop triggers and you sell near $37", "You sell at yesterday's close"],
                2,
                "A stop-loss triggers a market order once the level is touched or passed. In a gap, there were no "
                "trades at $45 to fill against, so execution happens near the new price: well below the stop. This "
                "gap risk is exactly why a stop-loss is not a guaranteed floor.",
            ),
            QuizQuestion(
                "The market is at $49.50 and you place a buy limit order at $50.00. What happens?",
                ["You pay exactly $50.00", "You fill around $49.50, since the limit is a maximum, not a target", "The order is rejected as invalid", "You must wait for the price to reach $50.00"],
                1,
                "A buy limit is a ceiling on what you'll pay, not the price you're aiming for. With the market lower "
                "than your limit, it fills at the better available price.",
            ),
            QuizQuestion(
                "In which situation is a limit order most valuable over a market order?",
                ["Buying a mega-cap stock with a one-cent spread mid-session", "Buying a thinly traded stock with a wide spread", "When you need guaranteed immediate execution", "When the market is closed"],
                1,
                "The wider the spread and the thinner the liquidity, the more a market order can cost you. That's "
                "precisely where a limit order's price protection is worth the risk of not filling.",
            ),
        ],
    ),

    # ── Lesson 5 ──────────────────────────────────────────────────────────
    Lesson(
        id="b005",
        title="Reading a Stock Quote: Market Cap, P/E, Volume, and Yield",
        category="Market Basics",
        tier=TIER_BEGINNER,
        estimated_read_time_minutes=7,
        body=(
            "A stock quote page is dense with numbers that mean very little without context. Here's what "
            "the core ones actually tell you, and what they don't.\n\n"

            "**Market capitalization = share price × shares outstanding.**\n"
            "This is the market's total price tag for the whole company, and it is the correct measure of "
            "company size, NOT the share price. A $10 stock is not 'cheaper' than a $500 stock in any "
            "meaningful sense; a company with 10 billion shares at $10 ($100B) is far larger than one with "
            "1 million shares at $500 ($500M). Share price alone is close to meaningless without the share "
            "count.\n\n"

            "Rough conventional bands: large-cap above ~$10B, mid-cap ~$2–10B, small-cap ~$300M–2B. Smaller "
            "companies tend to be more volatile and less liquid.\n\n"

            "**Volume = shares traded during the period.**\n"
            "It's an activity measure. High volume means many shares changed hands, which usually means "
            "tighter spreads and easier entry and exit. A sudden volume spike typically signals news or a "
            "change in sentiment: a price move on heavy volume reflects broader participation than the "
            "same move on very light volume.\n\n"

            "**P/E ratio = share price ÷ earnings per share.**\n"
            "It answers: how many dollars are you paying per dollar of annual profit? A P/E of 20 means "
            "$20 of price for every $1 of yearly earnings. Higher P/E generally means the market expects "
            "faster future growth.\n\n"
            "Three cautions a beginner should internalize immediately: (1) P/E is only comparable WITHIN "
            "an industry: software and utilities have structurally different normal ranges; (2) a company "
            "with no profits has no meaningful P/E at all; (3) a low P/E is not automatically a bargain: "
            "it frequently means the market expects earnings to decline. 'Cheap' and 'low P/E' are not "
            "synonyms.\n\n"

            "**Dividend yield = annual dividend per share ÷ share price.**\n"
            "The cash return you'd receive at the current price, as a percentage. A $2 annual dividend on "
            "a $50 stock is a 4% yield. Because price is the denominator, a yield can rise simply because "
            "the price collapsed: an unusually high yield relative to peers is often a signal of distress "
            "rather than generosity, and dividends can be cut at any time. They are not contractual "
            "obligations the way bond interest is.\n\n"

            "**52-week range.** The highest and lowest price over the past year. Useful for context on "
            "where the current price sits historically, but note that proximity to a 52-week low says "
            "nothing on its own about whether a stock is undervalued."
        ),
        key_takeaway=(
            "Market cap, not share price, tells you a company's size. P/E is only meaningful compared "
            "within an industry, and a low P/E often signals expected decline rather than a bargain. An "
            "unusually high dividend yield frequently means the price fell, not that the payout is generous."
        ),
        glossary=[
            GlossaryTerm("market capitalization", "Share price × shares outstanding. The market's total valuation of the company and the correct measure of its size."),
            GlossaryTerm("shares outstanding", "The total number of shares a company has issued."),
            GlossaryTerm("volume", "The number of shares traded over a period. A measure of activity and a rough proxy for liquidity."),
            GlossaryTerm("earnings per share", "A company's profit divided by its shares outstanding. Often abbreviated EPS."),
            GlossaryTerm("P/E ratio", "Price divided by earnings per share: dollars paid per dollar of annual profit."),
            GlossaryTerm("dividend yield", "Annual dividend divided by share price, expressed as a percentage."),
            GlossaryTerm("52-week range", "The highest and lowest prices over the trailing year."),
            GlossaryTerm("large-cap", "Conventionally a company with a market capitalization above roughly $10 billion."),
        ],
        callouts=[
            Callout("common_mistake", "Thinking a $10 stock is 'cheaper' than a $500 stock",
                "Share price is arbitrary: it depends entirely on how many shares exist, which a company can "
                "change at will via a split. A 2-for-1 split halves the share price and doubles the share "
                "count, changing the price tag on the business by exactly nothing. Compare market caps."),
            Callout("why_it_matters", "Why a high dividend yield can be a warning",
                "Yield is dividend ÷ price. If a company's price halves on bad news and the dividend hasn't "
                "been cut YET, the yield doubles, making a distressed company screen as an attractive "
                "income opportunity right before the payout gets reduced. Always ask why the yield is high."),
        ],
        quiz=[
            QuizQuestion(
                "Company A trades at $8/share with 5 billion shares. Company B trades at $400/share with 20 million shares. Which is larger?",
                ["Company B, because its share price is much higher", "Company A: $40B market cap vs Company B's $8B", "They are the same size", "You cannot tell without knowing earnings"],
                1,
                "Market cap = price × shares. A: $8 × 5B = $40B. B: $400 × 20M = $8B. Company A is five times larger "
                "despite the far lower share price, which is exactly why share price alone tells you nothing about size.",
            ),
            QuizQuestion(
                "A stock's P/E ratio is 6, well below its industry's typical 18. What is the most reasonable interpretation?",
                ["It is definitively undervalued and a good buy", "The market may expect its earnings to decline: it warrants investigation, not an automatic conclusion", "Its P/E is calculated incorrectly", "It pays a large dividend"],
                1,
                "A low P/E reflects low market expectations for future earnings. Sometimes that pessimism is "
                "overdone (a genuine bargain) and sometimes it's correct (a declining business). The ratio alone "
                "can't distinguish between the two: that's what further analysis is for.",
            ),
            QuizQuestion(
                "A stock's dividend yield jumps from 3% to 9% in two months with no change to the dividend. What most likely happened?",
                ["The company tripled its dividend", "The share price fell by roughly two-thirds", "Interest rates rose", "The company issued more shares"],
                1,
                "Yield = dividend ÷ price. With the dividend unchanged, a yield tripling means the price fell by about "
                "two-thirds. A spiking yield is very often a distress signal, and the dividend may be cut next.",
            ),
            QuizQuestion(
                "What does unusually high trading volume on a given day most directly indicate?",
                ["The stock price definitely rose", "An unusual level of participation and interest, often around news", "The company issued a dividend", "The spread has widened"],
                1,
                "Volume is a measure of activity, not direction. Heavy volume signals that many participants are "
                "acting, which is why a price move on heavy volume is generally considered more meaningful than "
                "the same move on very light volume.",
            ),
        ],
    ),
]
