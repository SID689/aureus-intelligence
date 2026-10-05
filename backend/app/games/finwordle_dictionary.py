"""
app/games/finwordle_dictionary.py
-----------------------------------
The FinWordle answer bank: 5-letter finance and trading terms, each with
the educational payload shown after a round ends.

CONTENT IN CODE, NOT IN A TABLE
Consistent with the lessons curriculum (see app/lessons/models.py), the
dictionary lives in Python rather than a `finwordle_dictionary` table.
It's static editorial content with no admin UI, it needs to be loaded as
an in-memory set on every guess validation anyway, and keeping it in code
means the definitions can't drift from a separate seed script. Per-user
game state — streaks, scores, sessions — is what lives in Postgres.

EDITORIAL RULES
  1. Every answer must be a real English word that is ALSO a genuine term
     of art in finance. Abbreviations and truncations are excluded: a
     player who doesn't know the jargon should still be able to reach the
     answer by ordinary word reasoning.
  2. `definition` is what the word means. `trading_context` is where you
     actually meet it on a desk or a screen. `example` is a concrete,
     numeric illustration — not a restatement of the definition.
  3. No word may imply a recommendation. These are definitions, not calls.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("aureus.games.finwordle")

WORD_LENGTH = 5
MAX_GUESSES = 6


@dataclass(frozen=True)
class WordEntry:
    word: str
    definition: str
    trading_context: str
    example: str
    category: str

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "definition": self.definition,
            "trading_context": self.trading_context,
            "example": self.example,
            "category": self.category,
        }


ANSWERS: list[WordEntry] = [
    WordEntry("ALPHA",
        "The portion of a return that exceeds what the benchmark and the risk taken would predict.",
        "The single number active managers are judged on. If a fund returns 12% while its benchmark returns 11%, the extra 1% is only alpha if it isn't explained by simply taking more market risk.",
        "A fund returns 14% while the S&P 500 returns 12%. If the fund carried a beta of 1.3, the market alone explains ~15.6% of expected return, so it actually produced NEGATIVE alpha despite beating the index.",
        "Performance"),
    WordEntry("ASSET",
        "Anything owned that carries economic value and can produce future benefit.",
        "The left side of a balance sheet, and the unit of allocation decisions. Analysts care less about total assets than about how productively they generate cash.",
        "A company reports $50B in assets but only $2B in operating cash flow: a 4% return on assets, which for a capital-intensive business may be normal and for a software business would be alarming.",
        "Accounting"),
    WordEntry("BASIS",
        "The difference between two related prices: commonly spot versus futures, or your cost versus current market value.",
        "In derivatives it's the spot-futures gap that converges at expiry. In taxes, 'cost basis' is what you paid, and it determines the gain you're taxed on.",
        "You buy at $40 (your cost basis) and sell at $65. Your taxable gain is $25/share, not $65, which is why brokers track basis across years and splits.",
        "Market Mechanics"),
    WordEntry("BEARS",
        "Market participants who expect prices to fall, and position accordingly.",
        "Shorthand for the pessimistic side of any debate. A 'bear market' is conventionally a decline of 20% or more from a recent peak.",
        "In a stock with 30% short interest, bears have taken a large, researched position against the business: that's genuine disagreement, not noise.",
        "Sentiment"),
    WordEntry("BONDS",
        "Debt instruments: loans to a government or company that pay interest and return principal at maturity.",
        "The other half of a balanced portfolio. Bondholders rank ahead of shareholders in bankruptcy but give up all the upside if the business thrives.",
        "A 10-year Treasury yielding 4% pays $40 a year per $1,000 of face value. If prevailing rates rise to 5%, that existing bond's price falls: its fixed payment is now uncompetitive.",
        "Fixed Income"),
    WordEntry("BULLS",
        "Market participants who expect prices to rise.",
        "The optimistic side of a debate, and the origin of 'bull market': a sustained advance, conventionally 20% or more off a low.",
        "Heavy call-option buying alongside rising volume is often read as bulls expressing conviction with leverage rather than just buying shares.",
        "Sentiment"),
    WordEntry("CALLS",
        "Options contracts giving the holder the right, not the obligation, to BUY an asset at a set strike price before expiry.",
        "Used to express upside views with defined risk, or sold against holdings to generate income. The most you can lose buying one is the premium paid.",
        "A $100 call costs $3 with the stock at $98. At expiry the stock is $110, so the call is worth $10: a $7 profit. Below $100 at expiry, it expires worthless and you lose the $3.",
        "Derivatives"),
    WordEntry("DELTA",
        "How much an option's price is expected to move for a $1 move in the underlying asset.",
        "The first and most-watched of the option greeks. A delta of 0.5 means the option gains roughly $0.50 per $1 rise, and it doubles as a rough probability the option finishes in-the-money.",
        "You hold 10 calls with 0.40 delta on a stock that rises $2. Expected gain ≈ 10 × 100 shares × 0.40 × $2 = $800, before the effect of gamma and time decay.",
        "Derivatives"),
    WordEntry("FLOAT",
        "The number of shares actually available for public trading, excluding closely-held and restricted stock.",
        "Small floats amplify price moves because a given amount of buying pressure meets far fewer available shares. It's a key input to squeeze dynamics.",
        "A company has 100M shares outstanding but insiders hold 80M: the float is only 20M. A fund buying 2M shares is absorbing 10% of everything tradeable.",
        "Market Mechanics"),
    WordEntry("GAMMA",
        "The rate at which an option's delta itself changes as the underlying moves.",
        "Gamma is why option risk is non-linear. Short-gamma positions see losses accelerate as a move extends; long gamma sees gains accelerate.",
        "An at-the-money option days from expiry can swing delta from 0.3 to 0.7 on a small price move: the same instrument behaving like a very different position within hours.",
        "Derivatives"),
    WordEntry("HEDGE",
        "A position taken specifically to offset potential losses in another position.",
        "Hedging trades expected return for reduced variance: it is a cost, deliberately paid. Judging a hedge on its own P&L misses its purpose.",
        "Holding $100k of equities and buying put options costing $2k a year: in a flat market you're down $2k, and in a crash the puts offset a far larger loss.",
        "Risk"),
    WordEntry("INDEX",
        "A rules-based basket of securities used to represent a market or segment of one.",
        "The benchmark active managers are measured against and the thing most passive funds track. Weighting method matters enormously to what you actually own.",
        "The S&P 500 is market-cap weighted, so its largest handful of companies can represent a far larger share of your risk than 'one of 500 holdings' suggests.",
        "Portfolio"),
    WordEntry("LIMIT",
        "An order type specifying the worst price you will accept.",
        "Trades price certainty for execution uncertainty: the opposite tradeoff to a market order. Essential in illiquid names where spreads are wide.",
        "You set a buy limit at $50 while the market trades at $49.50. You fill near $49.50, because a limit is a ceiling on what you'll pay, not a target price.",
        "Order Execution"),
    WordEntry("MOATS",
        "Durable competitive advantages that protect a business's profits from competitors.",
        "Popularised by Warren Buffett. Sources include network effects, switching costs, scale economics, patents, and brand: a moat is what keeps high returns from being competed away.",
        "A payments network gets more valuable to merchants as more consumers use it and vice versa: a network-effect moat that a well-funded new entrant still struggles to breach.",
        "Fundamentals"),
    WordEntry("ORDER",
        "An instruction sent to a broker or exchange to buy or sell.",
        "The order TYPE (market, limit, stop) determines how it executes, which is often more consequential for a retail investor than the choice of security.",
        "The same decision to buy 500 shares of a thinly-traded stock can cost meaningfully more as a market order than as a patient limit order, purely from spread and impact.",
        "Order Execution"),
    WordEntry("PRICE",
        "The amount at which a transaction most recently occurred.",
        "Not a valuation and not a guarantee of your fill: the price you get is the ask if buying and the bid if selling. Price is a record of agreement, not of worth.",
        "A quote screen reads $150, but the book is $149.90 bid / $150.10 ask. Buying immediately costs $150.10, and selling straight back returns $149.90.",
        "Market Mechanics"),
    WordEntry("QUOTE",
        "The current bid and ask prices available for a security, with their sizes.",
        "The two-sided quote is what actually exists in the market. A single headline number hides the spread you'll pay to cross it.",
        "A quote of '49.95 x 50.05, 200 x 300' means 200 shares are bid at $49.95 and 300 are offered at $50.05: useful when sizing an order against available depth.",
        "Market Mechanics"),
    WordEntry("RATIO",
        "A relationship between two figures, used to make financial statements comparable across companies of different sizes.",
        "The core tool of fundamental analysis. Ratios are only meaningful against a peer group or the company's own history, never in isolation.",
        "A P/E of 35 is expensive for a utility and unremarkable for a fast-growing software company. The number alone carries almost no information without its comparison set.",
        "Fundamentals"),
    WordEntry("SHARE",
        "One unit of ownership in a company.",
        "Ownership is what distinguishes equity from debt: shareholders hold the residual claim, with unlimited upside and last position in a bankruptcy.",
        "Owning 100 shares of a company with 1 billion outstanding makes you a one-ten-millionth owner, with a proportional claim on its future profits.",
        "Equity"),
    WordEntry("SHORT",
        "Selling a borrowed security in the expectation of buying it back cheaper.",
        "The payoff is inverted and asymmetric: gains are capped at 100% (the price can only fall to zero) while losses are theoretically unlimited.",
        "Short at $50 and cover at $30, and you make $20. But if it runs to $150, you've lost $100 per share: three times what you could have made if it went to zero.",
        "Trading"),
    WordEntry("SPLIT",
        "Dividing existing shares into more shares, proportionally reducing the price of each.",
        "A split changes nothing about the company's value: it's a cosmetic change to share count and price. It matters mainly for optics and options contract adjustment.",
        "A 4-for-1 split turns 100 shares at $400 into 400 shares at $100. Your position is worth exactly $40,000 before and after.",
        "Corporate Actions"),
    WordEntry("STOCK",
        "An ownership stake in a corporation, traded in units called shares.",
        "The highest long-run return potential of the mainstream asset classes, paired with the deepest drawdowns and last claim in insolvency.",
        "Equities have historically outperformed bonds over long horizons, while also delivering periods where they fell more than 50% and took years to recover.",
        "Equity"),
    WordEntry("THETA",
        "The rate at which an option loses value purely from the passage of time.",
        "Time decay is relentless and accelerates near expiry. Option buyers fight theta; option sellers collect it.",
        "An option with $2.00 of time value and 10 days left loses roughly $0.20 a day if nothing else changes, and that decay speeds up in the final week.",
        "Derivatives"),
    WordEntry("TREND",
        "The prevailing direction of price over a chosen timeframe.",
        "Technical analysis defines an uptrend as successively higher highs and higher lows. Trend-following strategies rely on momentum persisting; mean-reversion strategies bet on it breaking.",
        "A stock making higher highs and higher lows across three months is in an uptrend, until it fails to exceed the prior high and then breaks the prior low.",
        "Technical"),
    WordEntry("VALUE",
        "An investment style favouring securities that appear cheap relative to fundamentals.",
        "One of the best-documented academic factors, typically measured by book-to-market or earnings yield, and famously capable of underperforming for a decade at a time.",
        "Value underperformed growth for much of 2007–2020 before sharply reversing. A long drought doesn't prove a factor is broken; factor cyclicality is expected.",
        "Quantitative"),
    WordEntry("YIELD",
        "The income an investment produces, expressed as a percentage of its price.",
        "Because price is the denominator, yield rises when price falls. An unusually high yield is often a distress signal rather than generosity.",
        "A $2 annual dividend on a $50 stock yields 4%. If the price halves to $25 with the dividend unchanged, the yield reads 8%: right before the payout may be cut.",
        "Income"),
    WordEntry("SWAPS",
        "Derivative contracts in which two parties exchange one stream of cash flows for another.",
        "Mostly institutional. Interest-rate swaps trade fixed payments for floating ones; credit default swaps transfer default risk for a fee.",
        "A borrower paying a floating rate can swap into fixed, locking their cost of debt in exchange for giving up any benefit if rates later fall.",
        "Derivatives"),
    WordEntry("AUDIT",
        "An independent examination of financial statements to verify they fairly represent reality.",
        "Public companies must be audited annually. The audit OPINION is what matters: a 'going concern' qualification is a serious red flag buried in plain sight.",
        "An auditor issuing a going-concern warning is stating substantial doubt the company can operate for another twelve months: disclosed in the filing, often missed by headline readers.",
        "Accounting"),
    WordEntry("PIVOT",
        "A price level at which direction changes, or a strategic change of business direction.",
        "In technical analysis, pivot points are calculated support and resistance levels used as reference marks for the session.",
        "A stock that repeatedly stalls near $75 and turns lower has established $75 as resistance: a pivot traders watch for either rejection or breakout.",
        "Technical"),
    WordEntry("STAKE",
        "An ownership interest in a company or venture.",
        "Position size matters as much as position choice: a well-reasoned view held in size too large for the portfolio is a risk-management failure regardless of whether it's right.",
        "Disclosing a 5%+ stake in a US public company triggers a mandatory SEC filing, which is how activist positions typically become public.",
        "Equity"),
    WordEntry("SPIKE",
        "A sudden, sharp move in price or volume over a very short period.",
        "Volume spikes usually accompany news and signal broad participation. A price spike on thin volume is far less meaningful than the same move on heavy volume.",
        "A stock jumping 8% on five times average volume reflects genuine repricing by many participants; the same move on a fifth of average volume may be a liquidity artifact.",
        "Technical"),
    WordEntry("MACRO",
        "The economy-wide forces (growth, inflation, rates, employment) that affect all assets.",
        "Macro conditions set the discount rate every asset is valued against, which is why a rate decision can move a stock whose business is entirely unchanged.",
        "Rising rates hit unprofitable long-duration growth companies hardest, because their value depends on cash flows far in the future being discounted across more periods.",
        "Macro"),
    WordEntry("DRAWS",
        "Amounts taken from an available credit facility, or withdrawals from a portfolio.",
        "Regular withdrawals expose a portfolio to sequence-of-returns risk: early losses force selling more shares at depressed prices, permanently impairing recovery.",
        "Two portfolios with identical 20-year average returns can end in very different places if one suffered its worst years early while withdrawals were being taken.",
        "Portfolio"),
    WordEntry("MERGE",
        "To combine two companies into one entity.",
        "Announcements create merger-arbitrage spreads: the target usually trades below the offer price, and the gap reflects the market's odds the deal closes.",
        "An acquirer offers $80 a share and the target trades at $76. That $4 gap is compensation for the risk the deal breaks on regulatory or financing grounds.",
        "Corporate Actions"),
    WordEntry("GRANT",
        "Equity awarded as compensation, typically to employees, that vests over time.",
        "Stock-based compensation dilutes existing shareholders. Tracking net income growth without tracking share count growth systematically overstates what accrues to you.",
        "Net income growing 10% while share count grows 8% delivers roughly 2% growth per share, and per-share is what an owner actually holds.",
        "Equity"),
    WordEntry("CYCLE",
        "The recurring expansion and contraction pattern in an economy or industry.",
        "Cyclical businesses see earnings swing with the economy, which makes a single year's P/E deeply misleading: they look cheapest at peak earnings.",
        "An automaker at the top of a cycle may show a P/E of 5 on record earnings, precisely when those earnings are least sustainable. A low P/E is not automatically cheap.",
        "Macro"),
    WordEntry("BLOCK",
        "A single trade large enough that putting it through the open market would move the price against you.",
        "Institutions negotiate blocks away from the public book precisely so the size is not advertised. A block print on the tape is often the first public sign that a large holder has changed their mind.",
        "A fund selling 2 million shares of a stock that trades 500,000 a day would be four days of volume. Crossed as a block at a 2% discount, the discount costs $1.2M on a $60 stock and the market impact of working it openly would likely cost more.",
        "Market Mechanics"),
    WordEntry("BOARD",
        "The group of directors elected by shareholders to oversee management on their behalf.",
        "The board hires and fires the chief executive and sets their pay, so its independence is the main structural check an outside shareholder has. A board stacked with insiders is a governance risk long before it is a headline.",
        "A board of 9 directors where 6 are current or former executives of the firm has an independent majority on paper only. On a 3-person compensation committee drawn from that board, management is effectively setting its own pay.",
        "Governance"),
    WordEntry("BREAK",
        "A move through a price level that had previously held, in either direction.",
        "Breaks matter because the levels were not arbitrary: they are where earlier buyers and sellers actually transacted. A break on heavy volume says the balance there has changed; one on light volume often does not hold.",
        "A stock that stalled at $50 on four separate attempts over six months finally closes at $52 on three times average volume. The level that capped it has gone, and prior sellers at $50 are now the ones under pressure.",
        "Technical"),
    WordEntry("BUYER",
        "The side of a transaction taking ownership, and therefore the side that sets the bid.",
        "Every print needs both sides, so talk of more buyers than sellers is loose language: what actually changes is the price at which the two agree. Where the balance shows up is in who crosses the spread to get filled.",
        "If 80% of a day's volume prints at the ask rather than the bid, buyers were the impatient side, paying up for immediacy even though the number of shares bought and sold was identical.",
        "Market Mechanics"),
    WordEntry("CARRY",
        "The net cost or gain from holding a position over time, before any price movement.",
        "Carry is what a position earns or bleeds while nothing happens. It is why a trade can be directionally right and still lose, and why some positions pay you simply to wait.",
        "Borrowing at 2% to hold a bond yielding 5% is positive carry of 3% a year. The same trade when short rates rise to 6% becomes negative carry of 1%, and now time works against the holder.",
        "Fixed Income"),
    WordEntry("CHART",
        "A plot of price and volume over time, the standard way market history is read.",
        "A chart is a record of what was actually paid, not a forecast. Its value is in showing where supply and demand have previously met, and how much conviction stood behind each turn.",
        "Twenty years of monthly data compresses 5,000 trading days into one image. The same series as a table of numbers would be unreadable, which is why the chart is the default even for people who distrust technical analysis.",
        "Technical"),
    WordEntry("CHURN",
        "Excessive trading that generates commissions without serving the account holder.",
        "Churn is the clearest conflict in a commission-based model: the broker is paid by activity and the client is paid by returns. It is also a useful metric in reverse, where customer churn measures the share of revenue a business must win back each year just to stand still.",
        "A $100,000 account turning over six times a year at 1% round-trip costs $6,000, or 6% of capital, before any investment decision has been judged right or wrong.",
        "Market Mechanics"),
    WordEntry("CLAIM",
        "A legal right to be paid from a company's assets or cash flows.",
        "Capital structure is a queue of claims. Debt is paid before equity in a liquidation, which is the whole reason equity is more volatile: it receives what is left after every senior claim is satisfied.",
        "A firm with $800M of assets and $700M of debt leaves $100M for equity. A 15% fall in asset value wipes out $120M and leaves equity worthless, an 8x amplification of the underlying move.",
        "Accounting"),
    WordEntry("CLOSE",
        "The final price of a trading session, and the reference most calculations use.",
        "The close carries disproportionate weight: index funds trade it, derivatives settle on it, and performance is marked to it. That concentration of interest is why volume spikes into the final minutes.",
        "On a typical day roughly 10% of total volume prints in the closing auction. A stock averaging 5 million shares will see around 500,000 change hands in a single matching event at one price.",
        "Market Mechanics"),
    WordEntry("COVER",
        "Buying back a security that was previously sold short, closing the position.",
        "Covering is forced buying, which is why heavily shorted stocks can rise violently on no fundamental news. The short seller must buy to exit, and they are buying into the strength that is hurting them.",
        "A stock with 25% of its float sold short needs the equivalent of 25% of all tradable shares to be bought back. At 2 million shares of daily volume and a 40 million float, that is five full days of volume of pure demand.",
        "Trading"),
    WordEntry("CROSS",
        "A point where two tracked series meet, most often two moving averages.",
        "A cross is a summary of a change in trend that already happened, not a prediction of one. Its usefulness is as a consistent rule rather than as a signal with any edge of its own.",
        "A 50-day average crossing above a 200-day average cannot occur until the shorter window has already outperformed for weeks. By the time it prints, much of the move it describes is behind you.",
        "Technical"),
    WordEntry("CROWD",
        "The collective of participants already holding the same position.",
        "A crowded trade is risky not because the thesis is wrong but because everyone who agrees has already bought. There is nobody left to push it higher, and any forced seller meets a thin bid.",
        "If the largest 20 funds all hold the same stock at 5% of their books, the position is 100% of one fund's capital spread across twenty. A redemption cycle makes all twenty sellers at once into a market with one buyer.",
        "Sentiment"),
    WordEntry("CURVE",
        "The line plotting yield against maturity for bonds of the same credit quality.",
        "The shape of the curve is the market's view of future rates and growth compressed into one picture. Its slope has historically carried more information about the economy than its level.",
        "If 2-year notes yield 4.5% and 10-year notes yield 4.0%, the curve is inverted by 50 basis points: lenders accept less to lend for longer, which only makes sense if they expect rates to fall.",
        "Fixed Income"),
    WordEntry("DEALS",
        "Negotiated transactions in which one company acquires or combines with another.",
        "Deal activity is cyclical and tends to peak with confidence and cheap financing, which is also when acquirers overpay. The announcement is the start of a process, not the end.",
        "An acquirer paying a 30% premium for a target with $100M of earnings pays $2.6B instead of $2.0B at 20x. The deal only creates value if the combination produces more than $600M of extra present value.",
        "Corporate Actions"),
    WordEntry("DEBIT",
        "An entry on the left side of a ledger, increasing assets or decreasing liabilities.",
        "Double-entry bookkeeping is why financial statements tie together: every debit has an equal credit, so the balance sheet must balance. Statements that do not reconcile are the first sign of a problem.",
        "Buying $5M of equipment with cash debits equipment by $5M and credits cash by $5M. Total assets are unchanged, which is why capital expenditure does not appear on the income statement in the year it is spent.",
        "Accounting"),
    WordEntry("DRIFT",
        "The slow, persistent component of a price series, separate from its noise.",
        "Separating drift from noise is the central problem in reading any short price history. Over short windows noise dominates so completely that the drift is unmeasurable, which is why a week of performance says almost nothing.",
        "A stock with 2% daily volatility and 10% annual drift earns about 0.04% a day. The daily noise is fifty times the daily signal, so a month of data cannot distinguish skill from chance.",
        "Quantitative"),
    WordEntry("ENTRY",
        "A single record in the accounting system, and the unit the books are built from.",
        "Every number in a financial statement is an aggregation of entries. Understanding which entries feed a line is what separates reading a statement from reciting it.",
        "Revenue of $4.2B may be millions of individual entries. If the policy for when each is recorded changes, the total moves without a single additional sale being made.",
        "Accounting"),
    WordEntry("EXITS",
        "The transactions through which an investor converts a holding back into cash.",
        "An investment is not a return until it is exited. Private market valuations are estimates until someone buys at that price, which is why exit activity matters more than marks.",
        "A fund holding a position marked at 3x cost for four years has produced no cash. Exiting at 2.5x after fees may still beat the public market, while the 3x mark never existed as money.",
        "Private Markets"),
    WordEntry("FLASH",
        "A sudden, violent price dislocation that reverses almost as quickly.",
        "Flash events expose how thin visible liquidity really is. Quotes on screen are not commitments, and when automated participants step back simultaneously the book can empty in seconds.",
        "On 6 May 2010 the Dow fell about 9% and recovered most of it within 20 minutes. Individual shares printed at a cent, not because their value changed but because no bid remained.",
        "Market Mechanics"),
    WordEntry("FLOOR",
        "A level below which a price is not expected, or not permitted, to fall.",
        "Floors can be structural, like a bond's redemption value, or behavioural, like a level where buyers have repeatedly stepped in. The two behave very differently under stress: one is a contract, the other is a habit.",
        "A convertible bond redeeming at $1,000 has a hard floor near its straight-bond value regardless of the equity. A support level at $40 on a chart has no such guarantee and fails whenever the buyers who made it stop appearing.",
        "Market Mechanics"),
    WordEntry("FLOWS",
        "The movement of money into and out of funds, sectors or asset classes.",
        "Flows explain a great deal of short-term price movement that fundamentals cannot. A sector can rise for weeks because money is being allocated to it, with no change in any underlying business.",
        "A sector fund taking in $2B when the sector's free float is $200B means forced buying of 1% of all available shares, concentrated into whatever the index weights dictate rather than into whichever company improved.",
        "Portfolio"),
    WordEntry("FRAUD",
        "Deliberate misrepresentation of financial reality in order to deceive.",
        "Fraud is rare but not negligible, and it clusters where incentives and opacity meet. The recurring pattern is reported earnings that cash flow never confirms over several years.",
        "A company reporting $500M of cumulative net income over five years while cumulative operating cash flow is $50M has a $450M gap. The gap may be legitimate growth in receivables, and it may not, but it is the question to ask.",
        "Governance"),
    WordEntry("GROSS",
        "Revenue less only the direct cost of producing what was sold.",
        "Gross margin is the cleanest measure of pricing power, because it is the line least affected by how a company chooses to spend on growth. It is also the hardest line to improve by cost-cutting.",
        "A software business at 80% gross margin keeps $0.80 of every incremental dollar before any other cost. A grocer at 25% keeps $0.25, which is why the two cannot be valued on the same multiple of sales.",
        "Fundamentals"),
    WordEntry("ISSUE",
        "A new offering of securities sold by a company to raise capital.",
        "Issuing equity raises cash and dilutes existing owners at the same time. Whether that is good for you depends entirely on whether the cash earns more than the stake you gave up was worth.",
        "A company with 100 million shares issuing 10 million at $50 raises $500M and dilutes you by 9%. The trade is worthwhile only if that $500M generates more value than 9% of the business it bought.",
        "Corporate Actions"),
    WordEntry("LEASE",
        "A contract granting use of an asset for a period in exchange for payments.",
        "Leases were kept off balance sheets for decades, which flattered leverage for any business renting its premises. Accounting rules now bring most of them on, and comparisons across that change are not like for like.",
        "A retailer with $3B of lease commitments previously showed them in a footnote. On balance sheet they add $3B of liability, and a debt-to-equity ratio of 0.5 becomes 1.4 without the business changing at all.",
        "Accounting"),
    WordEntry("MODEL",
        "A simplified representation of a business or market used to produce an estimate.",
        "Every valuation is a model, including the ones that look like a single multiple. The useful question is never whether the model is right but which of its assumptions the answer actually depends on.",
        "A discounted cash flow with a 3% terminal growth rate and a 9% discount rate puts over 70% of its value beyond year ten. Moving terminal growth to 4% raises the valuation by roughly a quarter, on an assumption nobody can verify.",
        "Valuation"),
    WordEntry("NOISE",
        "Price movement that carries no information about value.",
        "Most short-term movement is noise, and the human instinct to explain every move produces stories for randomness. Distinguishing the two is the discipline that separates analysis from narration.",
        "A stock with 25% annual volatility moves about 1.6% on a typical day with no news at all. A 1.5% fall reported as a reaction to something is, far more often than not, an ordinary day being given a cause.",
        "Quantitative"),
    WordEntry("OUNCE",
        "The unit in which precious metals are priced and traded.",
        "Commodity quotes are meaningless without their unit. Gold in troy ounces, oil in barrels and copper in pounds are not interchangeable, and a troy ounce is about 10% heavier than the ordinary one.",
        "Gold at $2,400 per troy ounce is roughly $77 per gram. A futures contract covers 100 ounces, so a single contract controls $240,000 of metal and a 1% move is $2,400 of profit or loss.",
        "Commodities"),
    WordEntry("PANIC",
        "A phase in which selling is driven by fear rather than by any reassessment of value.",
        "Panic is identifiable by correlation: in a genuine one, assets that should be unrelated fall together because holders are selling whatever can be sold rather than whatever should be.",
        "In March 2020 gold fell alongside equities for several sessions. A hedge failing at exactly the moment it is needed is the signature of forced liquidation rather than of changed views about gold.",
        "Sentiment"),
    WordEntry("PAPER",
        "Short-term unsecured debt issued by corporations to fund immediate needs.",
        "Commercial paper is where a solvent company meets a liquidity problem. The market is reliable until it is not, and it closes to a borrower precisely when that borrower most needs it open.",
        "A firm rolling $500M of 30-day paper repeats that transaction twelve times a year. If the market shuts for a week, a profitable business with long-term assets faces a cash shortfall that has nothing to do with its earnings.",
        "Fixed Income"),
    WordEntry("PEERS",
        "The set of comparable companies a valuation is measured against.",
        "Relative valuation is only as good as the peer set, and peer selection is where most of the judgement hides. Change the comparables and the same company looks cheap or expensive at will.",
        "A company at 18x earnings is expensive against a peer set averaging 12x and cheap against one averaging 25x. Nothing about the business changed between the two conclusions.",
        "Valuation"),
    WordEntry("POINT",
        "A single unit of an index, or one hundredth of a percent when it is a basis point.",
        "The word carries two meanings that differ by orders of magnitude, and conflating them is a common and expensive error. Index points and basis points are not the same unit.",
        "A 50 basis point rate move is 0.50%. A 50 point move in an index at 5,000 is 1%. Reading one as the other misstates the magnitude by a factor of two in this case and far more in others.",
        "Market Mechanics"),
    WordEntry("POOLS",
        "Venues where orders are matched without displaying quotes to the public market.",
        "Dark pools exist so that large orders can find each other without advertising intent. The cost is that a growing share of volume is invisible while it happens, and the public price is formed on less information.",
        "If 15% of a stock's volume trades in non-displayed venues, the visible book represents 85% of real activity. A quote that looks thin may be sitting on top of substantial hidden interest, or on nothing.",
        "Market Mechanics"),
    WordEntry("PRIME",
        "The reference rate banks charge their most creditworthy borrowers.",
        "Prime is a benchmark that other lending is priced against rather than a rate most borrowers receive. It moves with central bank policy, so consumer and corporate borrowing costs reprice without any new negotiation.",
        "A loan priced at prime plus 2% costs 9.5% when prime is 7.5%. If policy rates rise by one point, the borrower pays 10.5% on exactly the same debt, and the increase arrives automatically.",
        "Fixed Income"),
    WordEntry("PRINT",
        "A published data release, or a single executed trade appearing on the tape.",
        "Both senses describe the moment something becomes fact rather than expectation. An inflation print and a block print are each the point at which the market stops guessing and starts repricing.",
        "If consensus expects 3.2% inflation and the print is 3.5%, the surprise is 30 basis points. Rate expectations can move more on that gap than on the absolute level, because only the gap was unpriced.",
        "Macro"),
    WordEntry("PROXY",
        "The authority to cast a shareholder's vote, and the document soliciting it.",
        "The proxy statement is the most informative annual filing most investors never read: executive pay, related-party transactions and board composition are all disclosed there rather than in the annual report.",
        "A shareholder with 2% of a company has 2% of the vote whether or not they attend. Not voting is not neutral: it lowers the total cast and raises the weight of everyone who did.",
        "Governance"),
    WordEntry("QUANT",
        "An approach that selects positions by measurable rules rather than by judgement.",
        "The appeal is consistency: a rule applies identically on the day it is uncomfortable. The weakness is that the rule was fitted to history, and history contained regimes that may not repeat.",
        "A strategy tested over 2009 to 2021 was fitted almost entirely to falling interest rates. Its results say little about how the same rules behave when rates rise, because that case barely appears in the sample.",
        "Quantitative"),
    WordEntry("RALLY",
        "A sustained advance in price over days or weeks.",
        "What matters about a rally is its breadth. An index can rise steadily while most of its members fall, if the few largest are carrying it, and that is a materially weaker advance than the headline suggests.",
        "An index up 8% where only 40% of members beat it is being driven by a handful of large weights. The same 8% with 70% participating is a broad move and historically a more durable one.",
        "Sentiment"),
    WordEntry("RANGE",
        "The band between the high and low over a period, within which price has been contained.",
        "Ranges describe periods when buyers and sellers are in rough balance. They are useful mainly as a measure of normal movement, which is what makes an unusual move recognisable.",
        "A stock with an average daily range of 2% that moves 6% has moved three times its normal amount. That is the signal worth investigating, independent of direction.",
        "Technical"),
    WordEntry("ROLLS",
        "Closing an expiring derivative position and reopening it in a later contract.",
        "Rolling is how a position is maintained past expiry, and it is rarely free. The cost depends on the shape of the futures curve, and over a year it can dominate the return of the underlying.",
        "A fund rolling monthly into contracts 0.5% more expensive each time pays about 6% a year in roll cost. The commodity itself can rise 4% and the fund still loses money.",
        "Derivatives"),
    WordEntry("SCALE",
        "The advantage a business gains as its fixed costs spread over more units.",
        "Scale is only an advantage where costs are genuinely fixed. In businesses where cost rises with each customer, being larger brings purchasing power but not the margin expansion the word implies.",
        "A firm with $100M of fixed costs earns 50% margins at $200M of revenue and 75% at $400M. A business whose costs are 60% variable sees margins improve by only a few points over the same doubling.",
        "Fundamentals"),
    WordEntry("SHELF",
        "A registration allowing a company to sell securities over time without refiling.",
        "A shelf is permission, not an event. Its existence tells you dilution is available on short notice, which matters most for companies that are burning cash and will eventually need it.",
        "A company with $200M of cash, a $50M annual burn and a $300M shelf has four years of funding and the standing ability to raise more at any price. The shelf itself caps how far a squeeze can run.",
        "Corporate Actions"),
    WordEntry("SHOCK",
        "An unanticipated event that forces a rapid repricing across many assets at once.",
        "Shocks are where correlation assumptions fail. Portfolios diversified under normal conditions discover that their holdings share a factor nobody was modelling, usually liquidity.",
        "A portfolio of assets correlated at 0.3 in calm markets can behave as if correlated at 0.9 in a shock. Diversification measured on quiet data overstates the protection available on the day it is needed.",
        "Macro"),
    WordEntry("SLACK",
        "Unused productive capacity in an economy, in labour or in plant.",
        "Slack is the main reason growth can run without inflation. Where it exists, demand is met by putting idle capacity back to work rather than by raising prices.",
        "An economy with unemployment at 7% and a long-run rate near 4% has roughly three points of labour slack. Stimulus there tends to raise output; the same stimulus at 3.5% unemployment tends to raise wages instead.",
        "Macro"),
    WordEntry("SLUMP",
        "A prolonged period of weak activity or falling prices.",
        "Slumps differ from corrections in duration rather than depth, and duration is what damages investors. A fall recovered in months is survivable; the same fall lasting years changes behaviour permanently.",
        "A 40% decline recovered in 18 months and the same decline taking 10 years require identical nerve on day one and entirely different circumstances to hold through. The second is where most selling actually happens.",
        "Macro"),
    WordEntry("TAPER",
        "A gradual reduction in the pace of central bank asset purchases.",
        "Tapering is slowing the rate of buying, not selling. The distinction is routinely lost, and markets have historically reacted to the announcement far more than to the reduced purchases themselves.",
        "Cutting purchases from $120B a month to $105B still adds $105B of demand for bonds. The balance sheet keeps growing, just more slowly, which is not tightening by any ordinary meaning of the word.",
        "Macro"),
    WordEntry("TENOR",
        "The time remaining until a financial instrument matures.",
        "Tenor drives how much a price moves for a given change in rates. Two bonds from the same issuer with identical coupons behave completely differently if one matures in two years and the other in thirty.",
        "A 2-year bond falls about 2% when yields rise one point. A 30-year bond with the same coupon falls closer to 18%, from an identical move in the same rate.",
        "Fixed Income"),
    WordEntry("TIERS",
        "The layers of capital a bank holds, ranked by their ability to absorb losses.",
        "Bank regulation is built on these layers because not all capital is equally useful in a crisis. Common equity absorbs losses immediately; other instruments only do so under specific conditions.",
        "A bank with $50B of risk-weighted assets and $6B of common equity has a 12% ratio against a regulatory minimum nearer 7%. The buffer is $2.5B of losses before any restriction on dividends applies.",
        "Banking"),
    WordEntry("TOTAL",
        "A return measure that includes income as well as price change.",
        "Price-only returns understate what a shareholder actually received, and the gap compounds. Any long-run comparison between a dividend payer and a non-payer on price alone is simply wrong.",
        "An index rising from 1,000 to 3,000 over 30 years is a 200% price return. With dividends reinvested at 2% a year the total return is nearer 440%, and the difference is not a rounding error.",
        "Performance"),
    WordEntry("TRADE",
        "A single completed transaction between a buyer and a seller.",
        "The trade is the atom of every other market statistic. Volume, price and volatility are all aggregations of individual trades, and a quote that is never traded against is not a price.",
        "A stock quoted $49.90 bid and $50.10 offered has no price of $50 until someone transacts. If the last trade was three hours ago, the quoted midpoint is an opinion rather than a market.",
        "Market Mechanics"),
    WordEntry("TRUST",
        "A legal structure holding assets on behalf of beneficiaries.",
        "In listed markets the common form is the real estate investment trust, which avoids corporate tax on condition that it distributes most of its income. That condition is why its yield is high and its retained growth is low.",
        "A structure distributing 90% of income retains 10% to reinvest. Growth must therefore come from issuing new units or taking on debt, which is why these vehicles are unusually sensitive to the cost of capital.",
        "Equity"),
    WordEntry("WAVES",
        "The alternating advances and retreats that make up a longer price move.",
        "Describing a trend as a series of waves is useful as a vocabulary for structure, and unreliable as a forecasting method. The counting is only unambiguous once the move is over.",
        "A 30% advance made of 5 up legs and 4 pullbacks can be labelled cleanly after the fact. In real time the same bars support at least 3 incompatible counts, which is the practical limit of the approach.",
        "Technical"),
    WordEntry("WEDGE",
        "A chart formation where the range narrows between two converging boundaries.",
        "A narrowing range means participants are disagreeing less about price, which cannot continue indefinitely. The formation says a resolution is coming without saying which way.",
        "A stock oscillating in a 10% band that narrows to 3% over two months has compressed its daily range by two thirds. The eventual exit from that band tends to move more than the band itself.",
        "Technical"),
    WordEntry("WIDEN",
        "An increase in the gap between two yields, usually credit against government debt.",
        "Widening spreads are the bond market's measure of fear. They move before equity markets more often than after, which is why credit is watched as a leading indicator.",
        "A corporate bond yielding 1.5% above treasuries widening to 4% means lenders now demand far more to hold the same debt. On a 7-year bond that repricing is roughly a 16% fall in value.",
        "Fixed Income"),
    WordEntry("WORTH",
        "What remains of assets once every liability has been subtracted.",
        "Book value is an accounting answer, not a market one, and the two diverge most for businesses whose main assets are not on the balance sheet at all.",
        "A company with $10B of assets and $6B of liabilities has $4B of book equity. If it trades at $40B, the market is valuing $36B of brand, research and position that the accounts never recorded.",
        "Accounting"),
    WordEntry("ZEROS",
        "Bonds paying no interest, sold below face value and redeemed at par.",
        "With no coupons, the entire return arrives at maturity, which makes these instruments unusually sensitive to rate changes. They are the purest expression of duration available.",
        "A 20-year zero bought at $350 redeems at $1,000, about 5.4% a year. A one-point rise in yields cuts its price by roughly 18%, against 11% for a coupon bond of the same maturity.",
        "Fixed Income"),
    WordEntry("BONUS",
        "Variable pay awarded on performance, typically annually.",
        "Bonus structures shape behaviour more reliably than stated strategy. Where the measure is annual and the risk is multi-year, the incentive is to take risk that pays this year and shows up later.",
        "A trader paid 10% of profits with no claw-back receives $2M on a $20M gain and nothing on a $20M loss. The payoff resembles a call option, and options are worth more the more volatile the underlying.",
        "Compensation"),
    WordEntry("LOANS",
        "Credit extended by a bank, and the main asset on most bank balance sheets.",
        "A bank's loan book is where its risk lives. Profit is recognised as interest accrues, while losses arrive later and in clusters, so the reported earnings of a lender always lead its real experience.",
        "A bank with $100B of loans earning a 3% spread makes $3B a year. A 4% loss rate in a recession costs $4B, erasing more than a year of profit from a book that looked sound while it was being written.",
        "Banking"),
    WordEntry("NOTES",
        "Debt securities of intermediate maturity, and the disclosures attached to accounts.",
        "The second sense is where the detail lives. Pension obligations, lease commitments, contingent liabilities and accounting policy changes are disclosed in the notes rather than on the face of any statement.",
        "A company showing $2B of debt on its balance sheet may disclose a further $3B of commitments in the notes. Leverage calculated from the balance sheet alone understates the obligation by 60%.",
        "Fixed Income"),
    WordEntry("TAXES",
        "Payments to government that sit between pre-tax profit and what owners keep.",
        "The gap between the statutory rate and what a company actually pays is one of the more revealing lines in the accounts. A persistently low effective rate is either a durable structural advantage or something that will eventually reverse.",
        "A firm reporting a 12% effective rate against a 21% statutory rate keeps an extra $90M on $1B of pre-tax profit. Whether that is worth capitalising depends entirely on whether the reason for it persists.",
        "Accounting"),
]

# ── The guess list ───────────────────────────────────────────────────
# Answers are curated; GUESSES ARE NOT, and the two serve opposite ends.
#
# The answer bank is hand-written because every entry has to earn the
# teaching moment shown when a round ends. The guess list has no such
# duty: its only job is to not reject a word a player legitimately typed.
# Those were the same list until now, 66 words between them, which meant
# the standard openers everyone reaches for first came back as "not a
# word". Being told your English is wrong by a finance game is a bad
# first thirty seconds.
#
# five_letter_words.txt is therefore broad on purpose: accepting an
# obscure real word costs nothing, rejecting a common one costs the
# player their opening move. It carries every five-letter headword from
# Webster's Second International (1934), whose copyright has lapsed and
# which ships as /usr/share/dict/web2 on BSD and macOS, plus the regular
# inflections a dictionary of headwords does not list separately: NOTES,
# TEARS, CITIES and so on, which are ordinary words to everyone except a
# lexicographer.
_WORDLIST_PATH = Path(__file__).with_name("five_letter_words.txt")


def _load_wordlist() -> frozenset[str]:
    """
    Read the guess list once at import.

    A missing or unreadable file degrades to the curated sets rather than
    raising. A game that accepts fewer words is playable; a service that
    will not start is not, and this is static data rather than something
    a deployment configures.
    """
    try:
        with open(_WORDLIST_PATH, encoding="utf-8") as fh:
            return frozenset(
                w for w in (line.strip().upper() for line in fh)
                if len(w) == WORD_LENGTH and w.isalpha()
            )
    except OSError as exc:  # noqa: BLE001
        logger.error("FinWordle word list unavailable, falling back to the curated set",
                     extra={"path": str(_WORDLIST_PATH), "error": str(exc)})
        return frozenset()


# Desk vocabulary that is not an English headword, so no general
# dictionary will ever contain it. Guesses only: by editorial rule 1
# these cannot be answers, because a player who does not already know the
# jargon could not reach them by ordinary word reasoning.
EXTRA_VALID_GUESSES: frozenset[str] = frozenset({
    "CAPEX", "EBITA", "FOREX", "LIBOR", "REPOS", "TBILL", "VWAPS",
})

ANSWERS_BY_WORD: dict[str, WordEntry] = {e.word: e for e in ANSWERS}

# Every answer is also a valid guess, and the broad list sits under both,
# so a player is never told that a real word is not one.
VALID_GUESSES: frozenset[str] = (
    frozenset(ANSWERS_BY_WORD)
    | frozenset(w for w in EXTRA_VALID_GUESSES if len(w) == WORD_LENGTH and w.isalpha())
    | _load_wordlist()
)


def is_valid_guess(word: str) -> bool:
    return word.upper() in VALID_GUESSES


def get_entry(word: str) -> WordEntry | None:
    return ANSWERS_BY_WORD.get(word.upper())


# Fail fast at import rather than serving a malformed puzzle.
_bad = [e.word for e in ANSWERS if len(e.word) != WORD_LENGTH or not e.word.isalpha() or e.word != e.word.upper()]
if _bad:
    raise RuntimeError(f"FinWordle answers must be {WORD_LENGTH} uppercase letters: {_bad}")
if len(ANSWERS_BY_WORD) != len(ANSWERS):
    raise RuntimeError("Duplicate word in FinWordle answer bank")
# An answer absent from the guess list could never be typed, which would
# make that day's puzzle unsolvable for everyone. Cheap to assert, and
# otherwise invisible until it happens to come up as the daily word.
_unguessable = sorted(set(ANSWERS_BY_WORD) - VALID_GUESSES)
if _unguessable:
    raise RuntimeError(f"FinWordle answers missing from the guess list: {_unguessable}")
