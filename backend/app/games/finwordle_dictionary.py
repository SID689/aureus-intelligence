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

from dataclasses import dataclass

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
        "A fund returns 14% while the S&P 500 returns 12%. If the fund carried a beta of 1.3, the market alone explains ~15.6% of expected return — so it actually produced NEGATIVE alpha despite beating the index.",
        "Performance"),
    WordEntry("ASSET",
        "Anything owned that carries economic value and can produce future benefit.",
        "The left side of a balance sheet, and the unit of allocation decisions. Analysts care less about total assets than about how productively they generate cash.",
        "A company reports $50B in assets but only $2B in operating cash flow — a 4% return on assets, which for a capital-intensive business may be normal and for a software business would be alarming.",
        "Accounting"),
    WordEntry("BASIS",
        "The difference between two related prices — commonly spot versus futures, or your cost versus current market value.",
        "In derivatives it's the spot-futures gap that converges at expiry. In taxes, 'cost basis' is what you paid, and it determines the gain you're taxed on.",
        "You buy at $40 (your cost basis) and sell at $65. Your taxable gain is $25/share — not $65, which is why brokers track basis across years and splits.",
        "Market Mechanics"),
    WordEntry("BEARS",
        "Market participants who expect prices to fall, and position accordingly.",
        "Shorthand for the pessimistic side of any debate. A 'bear market' is conventionally a decline of 20% or more from a recent peak.",
        "In a stock with 30% short interest, bears have taken a large, researched position against the business — that's genuine disagreement, not noise.",
        "Sentiment"),
    WordEntry("BONDS",
        "Debt instruments: loans to a government or company that pay interest and return principal at maturity.",
        "The other half of a balanced portfolio. Bondholders rank ahead of shareholders in bankruptcy but give up all the upside if the business thrives.",
        "A 10-year Treasury yielding 4% pays $40 a year per $1,000 of face value. If prevailing rates rise to 5%, that existing bond's price falls — its fixed payment is now uncompetitive.",
        "Fixed Income"),
    WordEntry("BULLS",
        "Market participants who expect prices to rise.",
        "The optimistic side of a debate, and the origin of 'bull market' — a sustained advance, conventionally 20% or more off a low.",
        "Heavy call-option buying alongside rising volume is often read as bulls expressing conviction with leverage rather than just buying shares.",
        "Sentiment"),
    WordEntry("CALLS",
        "Options contracts giving the holder the right, not the obligation, to BUY an asset at a set strike price before expiry.",
        "Used to express upside views with defined risk, or sold against holdings to generate income. The most you can lose buying one is the premium paid.",
        "A $100 call costs $3 with the stock at $98. At expiry the stock is $110, so the call is worth $10 — a $7 profit. Below $100 at expiry, it expires worthless and you lose the $3.",
        "Derivatives"),
    WordEntry("DELTA",
        "How much an option's price is expected to move for a $1 move in the underlying asset.",
        "The first and most-watched of the option greeks. A delta of 0.5 means the option gains roughly $0.50 per $1 rise, and it doubles as a rough probability the option finishes in-the-money.",
        "You hold 10 calls with 0.40 delta on a stock that rises $2. Expected gain ≈ 10 × 100 shares × 0.40 × $2 = $800, before the effect of gamma and time decay.",
        "Derivatives"),
    WordEntry("FLOAT",
        "The number of shares actually available for public trading, excluding closely-held and restricted stock.",
        "Small floats amplify price moves because a given amount of buying pressure meets far fewer available shares. It's a key input to squeeze dynamics.",
        "A company has 100M shares outstanding but insiders hold 80M — the float is only 20M. A fund buying 2M shares is absorbing 10% of everything tradeable.",
        "Market Mechanics"),
    WordEntry("GAMMA",
        "The rate at which an option's delta itself changes as the underlying moves.",
        "Gamma is why option risk is non-linear. Short-gamma positions see losses accelerate as a move extends; long gamma sees gains accelerate.",
        "An at-the-money option days from expiry can swing delta from 0.3 to 0.7 on a small price move — the same instrument behaving like a very different position within hours.",
        "Derivatives"),
    WordEntry("HEDGE",
        "A position taken specifically to offset potential losses in another position.",
        "Hedging trades expected return for reduced variance — it is a cost, deliberately paid. Judging a hedge on its own P&L misses its purpose.",
        "Holding $100k of equities and buying put options costing $2k a year: in a flat market you're down $2k, and in a crash the puts offset a far larger loss.",
        "Risk"),
    WordEntry("INDEX",
        "A rules-based basket of securities used to represent a market or segment of one.",
        "The benchmark active managers are measured against and the thing most passive funds track. Weighting method matters enormously to what you actually own.",
        "The S&P 500 is market-cap weighted, so its largest handful of companies can represent a far larger share of your risk than 'one of 500 holdings' suggests.",
        "Portfolio"),
    WordEntry("LIMIT",
        "An order type specifying the worst price you will accept.",
        "Trades price certainty for execution uncertainty — the opposite tradeoff to a market order. Essential in illiquid names where spreads are wide.",
        "You set a buy limit at $50 while the market trades at $49.50. You fill near $49.50, because a limit is a ceiling on what you'll pay, not a target price.",
        "Order Execution"),
    WordEntry("MOATS",
        "Durable competitive advantages that protect a business's profits from competitors.",
        "Popularised by Warren Buffett. Sources include network effects, switching costs, scale economics, patents, and brand — a moat is what keeps high returns from being competed away.",
        "A payments network gets more valuable to merchants as more consumers use it and vice versa — a network-effect moat that a well-funded new entrant still struggles to breach.",
        "Fundamentals"),
    WordEntry("ORDER",
        "An instruction sent to a broker or exchange to buy or sell.",
        "The order TYPE — market, limit, stop — determines how it executes, which is often more consequential for a retail investor than the choice of security.",
        "The same decision to buy 500 shares of a thinly-traded stock can cost meaningfully more as a market order than as a patient limit order, purely from spread and impact.",
        "Order Execution"),
    WordEntry("PRICE",
        "The amount at which a transaction most recently occurred.",
        "Not a valuation and not a guarantee of your fill — the price you get is the ask if buying and the bid if selling. Price is a record of agreement, not of worth.",
        "A quote screen reads $150, but the book is $149.90 bid / $150.10 ask. Buying immediately costs $150.10, and selling straight back returns $149.90.",
        "Market Mechanics"),
    WordEntry("QUOTE",
        "The current bid and ask prices available for a security, with their sizes.",
        "The two-sided quote is what actually exists in the market. A single headline number hides the spread you'll pay to cross it.",
        "A quote of '49.95 x 50.05, 200 x 300' means 200 shares are bid at $49.95 and 300 are offered at $50.05 — useful when sizing an order against available depth.",
        "Market Mechanics"),
    WordEntry("RATIO",
        "A relationship between two figures, used to make financial statements comparable across companies of different sizes.",
        "The core tool of fundamental analysis. Ratios are only meaningful against a peer group or the company's own history — never in isolation.",
        "A P/E of 35 is expensive for a utility and unremarkable for a fast-growing software company. The number alone carries almost no information without its comparison set.",
        "Fundamentals"),
    WordEntry("SHARE",
        "One unit of ownership in a company.",
        "Ownership is what distinguishes equity from debt: shareholders hold the residual claim, with unlimited upside and last position in a bankruptcy.",
        "Owning 100 shares of a company with 1 billion outstanding makes you a one-ten-millionth owner — with a proportional claim on its future profits.",
        "Equity"),
    WordEntry("SHORT",
        "Selling a borrowed security in the expectation of buying it back cheaper.",
        "The payoff is inverted and asymmetric: gains are capped at 100% (the price can only fall to zero) while losses are theoretically unlimited.",
        "Short at $50 and cover at $30, and you make $20. But if it runs to $150, you've lost $100 per share — three times what you could have made if it went to zero.",
        "Trading"),
    WordEntry("SPLIT",
        "Dividing existing shares into more shares, proportionally reducing the price of each.",
        "A split changes nothing about the company's value — it's a cosmetic change to share count and price. It matters mainly for optics and options contract adjustment.",
        "A 4-for-1 split turns 100 shares at $400 into 400 shares at $100. Your position is worth exactly $40,000 before and after.",
        "Corporate Actions"),
    WordEntry("STOCK",
        "An ownership stake in a corporation, traded in units called shares.",
        "The highest long-run return potential of the mainstream asset classes, paired with the deepest drawdowns and last claim in insolvency.",
        "Equities have historically outperformed bonds over long horizons — while also delivering periods where they fell more than 50% and took years to recover.",
        "Equity"),
    WordEntry("THETA",
        "The rate at which an option loses value purely from the passage of time.",
        "Time decay is relentless and accelerates near expiry. Option buyers fight theta; option sellers collect it.",
        "An option with $2.00 of time value and 10 days left loses roughly $0.20 a day if nothing else changes — and that decay speeds up in the final week.",
        "Derivatives"),
    WordEntry("TREND",
        "The prevailing direction of price over a chosen timeframe.",
        "Technical analysis defines an uptrend as successively higher highs and higher lows. Trend-following strategies rely on momentum persisting; mean-reversion strategies bet on it breaking.",
        "A stock making higher highs and higher lows across three months is in an uptrend — until it fails to exceed the prior high and then breaks the prior low.",
        "Technical"),
    WordEntry("VALUE",
        "An investment style favouring securities that appear cheap relative to fundamentals.",
        "One of the best-documented academic factors, typically measured by book-to-market or earnings yield — and famously capable of underperforming for a decade at a time.",
        "Value underperformed growth for much of 2007–2020 before sharply reversing. A long drought doesn't prove a factor is broken; factor cyclicality is expected.",
        "Quantitative"),
    WordEntry("YIELD",
        "The income an investment produces, expressed as a percentage of its price.",
        "Because price is the denominator, yield rises when price falls. An unusually high yield is often a distress signal rather than generosity.",
        "A $2 annual dividend on a $50 stock yields 4%. If the price halves to $25 with the dividend unchanged, the yield reads 8% — right before the payout may be cut.",
        "Income"),
    WordEntry("SWAPS",
        "Derivative contracts in which two parties exchange one stream of cash flows for another.",
        "Mostly institutional. Interest-rate swaps trade fixed payments for floating ones; credit default swaps transfer default risk for a fee.",
        "A borrower paying a floating rate can swap into fixed, locking their cost of debt in exchange for giving up any benefit if rates later fall.",
        "Derivatives"),
    WordEntry("AUDIT",
        "An independent examination of financial statements to verify they fairly represent reality.",
        "Public companies must be audited annually. The audit OPINION is what matters — a 'going concern' qualification is a serious red flag buried in plain sight.",
        "An auditor issuing a going-concern warning is stating substantial doubt the company can operate for another twelve months — disclosed in the filing, often missed by headline readers.",
        "Accounting"),
    WordEntry("PIVOT",
        "A price level at which direction changes, or a strategic change of business direction.",
        "In technical analysis, pivot points are calculated support and resistance levels used as reference marks for the session.",
        "A stock that repeatedly stalls near $75 and turns lower has established $75 as resistance — a pivot traders watch for either rejection or breakout.",
        "Technical"),
    WordEntry("STAKE",
        "An ownership interest in a company or venture.",
        "Position size matters as much as position choice: a well-reasoned view held in size too large for the portfolio is a risk-management failure regardless of whether it's right.",
        "Disclosing a 5%+ stake in a US public company triggers a mandatory SEC filing — which is how activist positions typically become public.",
        "Equity"),
    WordEntry("SPIKE",
        "A sudden, sharp move in price or volume over a very short period.",
        "Volume spikes usually accompany news and signal broad participation. A price spike on thin volume is far less meaningful than the same move on heavy volume.",
        "A stock jumping 8% on five times average volume reflects genuine repricing by many participants; the same move on a fifth of average volume may be a liquidity artifact.",
        "Technical"),
    WordEntry("MACRO",
        "The economy-wide forces — growth, inflation, rates, employment — that affect all assets.",
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
        "Net income growing 10% while share count grows 8% delivers roughly 2% growth per share — and per-share is what an owner actually holds.",
        "Equity"),
    WordEntry("CYCLE",
        "The recurring expansion and contraction pattern in an economy or industry.",
        "Cyclical businesses see earnings swing with the economy, which makes a single year's P/E deeply misleading — they look cheapest at peak earnings.",
        "An automaker at the top of a cycle may show a P/E of 5 on record earnings, precisely when those earnings are least sustainable. A low P/E is not automatically cheap.",
        "Macro"),
]

# Accepted as guesses but never selected as the answer. These let a player
# probe letters with words they'd naturally reach for, without widening the
# solution pool to terms whose definitions wouldn't earn their place in the
# post-game teaching moment.
EXTRA_VALID_GUESSES: frozenset[str] = frozenset({
    "BANKS", "BONUS", "CHURN", "COSTS", "DEBTS", "EARNS", "EXITS", "FUNDS",
    "GAINS", "GROSS", "LEVEL", "LOANS", "NOTES", "PEAKS", "PROXY", "RALLY",
    "RISKS", "ROLLS", "SALES", "SCALE", "SPEND", "TAXES", "TICKS", "TOKEN",
    "TRUST", "UNITS", "VAULT", "WAGES", "WHALE", "WORTH",
})

ANSWERS_BY_WORD: dict[str, WordEntry] = {e.word: e for e in ANSWERS}

# Every answer is also a valid guess.
VALID_GUESSES: frozenset[str] = frozenset(ANSWERS_BY_WORD) | frozenset(
    w for w in EXTRA_VALID_GUESSES if len(w) == WORD_LENGTH and w.isalpha()
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
