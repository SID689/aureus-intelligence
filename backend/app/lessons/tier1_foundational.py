"""
app/lessons/tier1_foundational.py
-----------------------------------
TIER 1 — "Foundational+"

One level past the basics. Assumes the reader has placed trades and knows
the common terms; every lesson here goes one layer deeper on the MECHANISM
behind something they already half-know, or shows where the standard
explanation quietly breaks down.

These lessons predate the Module 0 beginner tier and were originally
numbered tier 0. They are now tier 1 — see models.py for the renumbering
history and db/migrations/004 for the matching user data migration.
Quiz questions live in quizzes.py, keyed by lesson id.
"""

from app.lessons.models import Callout, GlossaryTerm, Lesson, TIER_FOUNDATIONAL

TIER_1_FOUNDATIONAL: list[Lesson] = [

    Lesson("l001", "Why P/E Ratios Lie to You Across Sectors", "Valuation", TIER_FOUNDATIONAL,
        "A price-to-earnings ratio only means something relative to a peer group with similar "
        "capital structure and growth dynamics. A software company trading at 35x earnings and a "
        "regional bank trading at 9x aren't telling you the bank is 'cheaper': they're telling you "
        "the market expects very different growth trajectories and has very different views on the "
        "durability of each business's earnings.\n\n"
        "The deeper issue: P/E uses trailing or forward earnings, and earnings are an accounting "
        "construct that management has real discretion over: depreciation schedules, revenue "
        "recognition timing, one-time charges. Two companies with identical cash economics can report "
        "meaningfully different earnings depending on accounting choices. That's part of why "
        "professional analysts lean on free cash flow alongside earnings: cash is harder to shape "
        "than reported profit.",
        "A P/E ratio is only informative when compared within a sector, and even then it should be triangulated against cash flow, not read alone."),
    Lesson("l002", "What Beta Actually Measures (and Doesn't)", "Risk", TIER_FOUNDATIONAL,
        "Beta measures how a stock's returns have historically moved relative to a benchmark: a beta "
        "of 1.5 means the stock has tended to move 50% more than the market in either direction. "
        "It's a measure of historical co-movement, not a measure of quality, safety, or future risk.\n\n"
        "The common mistake: treating low beta as synonymous with 'safe.' A low-beta stock can still "
        "carry enormous company-specific risk (fraud, a failed product, a lawsuit) that has nothing to "
        "do with market correlation. Beta captures systematic risk: the risk you can't diversify away "
        "by holding many stocks, but says nothing about idiosyncratic risk specific to that one company.",
        "Beta tells you how correlated a stock is to the market, not how risky the underlying business is."),
    Lesson("l003", "The Difference Between Volume and Liquidity", "Market Mechanics", TIER_FOUNDATIONAL,
        "Daily trading volume and liquidity sound similar but answer different questions. Volume tells "
        "you how many shares changed hands. Liquidity tells you how much you could trade RIGHT NOW "
        "without moving the price against yourself, which depends on order book depth, not just "
        "yesterday's volume total.\n\n"
        "A stock can show healthy average volume while having thin liquidity at any given moment if "
        "that volume is concentrated in a few large block trades rather than continuous two-sided "
        "flow. This matters most when position sizing: a $50,000 order in a stock with $2M average "
        "daily volume might move the price meaningfully more than the same order in a stock with "
        "identical average volume but tighter bid-ask spreads and deeper resting orders.",
        "High average volume doesn't guarantee you can exit a large position without moving the price: check the bid-ask spread and order book depth too."),
    Lesson("l004", "Why Diversification Stops Helping After ~20-30 Stocks", "Portfolio Theory", TIER_FOUNDATIONAL,
        "The classic diversification benefit, reducing risk without sacrificing expected return, "
        "comes almost entirely from eliminating company-specific risk. Each additional holding you add "
        "reduces idiosyncratic risk, but with steeply diminishing returns. Academic estimates generally "
        "put the bulk of the benefit captured by around 20-30 well-chosen, uncorrelated positions.\n\n"
        "Beyond that point, you're mostly just approximating an index fund with extra transaction costs "
        "and monitoring overhead, while the risk that remains, market-wide systematic risk, can't be "
        "diversified away by adding more individual stocks at all. That risk only comes down through "
        "asset allocation (bonds, cash, uncorrelated asset classes), not through owning more stocks.",
        "Adding your 50th holding barely reduces risk versus your 25th: company-specific risk diversifies away fast, market risk never does."),
    Lesson("l005", "Reading a Cash Flow Statement in Three Lines", "Valuation", TIER_FOUNDATIONAL,
        "The cash flow statement has three sections, and the relationship between them tells a story "
        "the income statement can hide. Operating cash flow (cash generated by the core business), "
        "investing cash flow (cash spent on or received from long-term assets), and financing cash "
        "flow (cash raised from or returned to lenders and shareholders).\n\n"
        "A healthy, mature company typically shows positive operating cash flow, negative investing "
        "cash flow (reinvesting in the business), and negative financing cash flow (paying down debt "
        "or returning capital via buybacks/dividends). A company burning cash that shows POSITIVE "
        "financing cash flow every year is funding operations by continuously raising new capital: "
        "worth understanding whether that's growth-stage normal or a warning sign.",
        "Watch the trend across all three cash flow sections together, not any single number in isolation."),
    Lesson("l006", "Why Momentum Works (and Why It Randomly Stops Working)", "Quantitative", TIER_FOUNDATIONAL,
        "Price momentum: the tendency for recent winners to keep outperforming over 3-12 month "
        "windows: is one of the most robust, well-documented factors in academic finance. The leading "
        "behavioral explanation is underreaction: investors are slow to fully price in new information, "
        "so good news gets incorporated gradually rather than instantly.\n\n"
        "The catch is 'momentum crashes': sharp, sudden reversals that tend to cluster around market "
        "turning points, especially after periods of high volatility. The very thing that makes "
        "momentum profitable (crowding into recent winners) is what makes it dangerous when sentiment "
        "flips fast, because everyone is positioned the same way at once.",
        "Momentum is a real, persistent effect, but it comes with fat-tailed crash risk concentrated around volatility spikes, not a smooth payoff."),
    Lesson("l007", "Stated Risk Tolerance vs. Revealed Risk Tolerance", "Behavioral", TIER_FOUNDATIONAL,
        "Ask most investors how they'd react to a 30% portfolio decline and you'll get a calm, "
        "rational answer: 'I'd hold, maybe buy more.' Actual behavior during real drawdowns tells a "
        "different story: retail outflows accelerate sharply during genuine crashes, well beyond what "
        "stated risk tolerance surveys would predict.\n\n"
        "This gap exists because stated risk tolerance is answered in a calm state, imagining a "
        "hypothetical. Revealed risk tolerance shows up under the actual physiological stress of "
        "watching real money disappear in real time. The practical takeaway: position sizing decisions "
        "made when calm should assume your actual behavior under stress will be somewhat worse than "
        "your stated intentions.",
        "Size positions for how you'll actually behave during a real drawdown, not how you predict you'll behave when you're calm."),
    Lesson("l008", "What the Yield Curve Inversion Actually Signals", "Macro", TIER_FOUNDATIONAL,
        "A yield curve inversion, short-term Treasury yields exceeding long-term yields, has "
        "preceded most U.S. recessions in the past 60 years, which is why it gets so much attention. "
        "The mechanism: an inverted curve typically reflects markets pricing in future rate cuts, which "
        "usually only happen because the central bank expects economic weakness ahead.\n\n"
        "The important nuance: the lag between inversion and recession has historically ranged from "
        "roughly 6 to 24 months, and the curve has also produced false signals. It's a probabilistic "
        "indicator investors watch as one input among many, not a precise, mechanical trading trigger.",
        "Yield curve inversions have real predictive history but poor timing precision: treat it as one macro input, not a trading signal on its own."),
    Lesson("l009", "Options Basics: What Implied Volatility Actually Prices In", "Derivatives", TIER_FOUNDATIONAL,
        "An option's price has two components: intrinsic value (how far in-the-money it already is) "
        "and time value, driven heavily by implied volatility: the market's forward-looking estimate "
        "of how much the underlying will move before expiration, back-solved from the option's price.\n\n"
        "Implied volatility isn't a prediction of direction, only magnitude. A stock can have very high "
        "implied volatility heading into an earnings report with no directional view at all, just high "
        "uncertainty about the SIZE of the move. This is why option premiums spike before binary events "
        "and typically collapse right after, regardless of which direction the stock moved: 'volatility crush.'",
        "High implied volatility means the market expects a big move, not that it expects a move in any particular direction."),
    Lesson("l010", "Why 'Buy the Dip' Isn't a Strategy by Itself", "Behavioral", TIER_FOUNDATIONAL,
        "'Buy the dip' has worked remarkably well across most of the post-2009 bull market, which is "
        "exactly why it's dangerous as an unconditional rule: it was reinforced by a specific, "
        "unusually persistent regime. The strategy has a very different track record during genuine "
        "structural bear markets (2000-2002, 2007-2009), where dips kept dipping for years.\n\n"
        "The distinction that actually matters: is this a sentiment-driven pullback in an intact "
        "fundamental picture, or the market correctly repricing genuine deterioration? Those look "
        "identical in the first few days of a decline and only become distinguishable over time.",
        "'Buy the dip' worked because of a specific market regime, not because it's a timeless law: the same pattern has failed for years at a time in different regimes."),
    Lesson("l011", "Free Cash Flow Yield vs. Dividend Yield", "Valuation", TIER_FOUNDATIONAL,
        "Dividend yield only captures the portion of cash a company chooses to distribute directly. "
        "Free cash flow yield (FCF divided by market cap) captures the TOTAL cash the business is "
        "generating relative to its price, regardless of whether management pays it out, reinvests it, "
        "or uses it for buybacks.\n\n"
        "A company with a 1% dividend yield but a 7% free cash flow yield is generating substantial "
        "cash: it's just choosing to redeploy most of it. Whether that's the right choice depends on "
        "whether management has good reinvestment opportunities; if not, that cash is effectively "
        "earning shareholders nothing until it's returned or productively deployed.",
        "A low dividend yield doesn't mean a company isn't generating cash: check free cash flow yield before drawing conclusions."),
    Lesson("l012", "What Short Interest Actually Tells You", "Market Mechanics", TIER_FOUNDATIONAL,
        "Short interest, the percentage of a stock's float sold short, gets popular attention mostly "
        "around short-squeeze narratives, but its more reliable use is as a proxy for how contested the "
        "bear case is. Very high short interest (25%+ of float) means sophisticated participants have "
        "taken a structural bet against the business.\n\n"
        "The squeeze mechanic is real but rare and hard to time: it requires a specific combination of "
        "high short interest, low float, and a genuine catalyst, not just 'the stock is going up.' Most "
        "high-short-interest stocks never squeeze; the short sellers are often simply right.",
        "High short interest signals genuine disagreement about the bear case: it's a real signal worth investigating, not automatically a squeeze setup."),
    Lesson("l013", "Sequence-of-Returns Risk, Explained Simply", "Risk", TIER_FOUNDATIONAL,
        "Two portfolios can have identical average annual returns over 20 years and produce wildly "
        "different outcomes purely based on the ORDER those returns happened in: this matters most for "
        "anyone regularly withdrawing from (or adding to) a portfolio, not just holding a lump sum.\n\n"
        "If large losses happen early while you're withdrawing, you're forced to sell more shares at "
        "depressed prices to generate the same dollar amount, permanently impairing recovery even if "
        "subsequent average returns match an alternate scenario exactly.",
        "The ORDER returns arrive in matters as much as the average return itself, especially if you're withdrawing money along the way."),
    Lesson("l014", "Why Analyst Price Targets Cluster Around the Current Price", "Behavioral", TIER_FOUNDATIONAL,
        "Sell-side price targets show a well-documented bias: they tend to anchor toward the current "
        "price rather than representing an independent fair-value estimate. Part of this is "
        "career-risk-driven: a wildly out-of-consensus target that's wrong is more damaging to an "
        "analyst's reputation than a modest, consensus-hugging one that's also wrong.\n\n"
        "This doesn't make targets worthless, but the DIRECTION and REASONING behind a revision usually "
        "carries more information than the number itself.",
        "Price target changes carry more signal than price target levels: watch the direction and reasoning, not the specific number."),
    Lesson("l015", "What 'Priced In' Actually Means (and When It's Wrong)", "Market Mechanics", TIER_FOUNDATIONAL,
        "'It's already priced in' is one of the most overused phrases in markets, and it's only "
        "meaningfully true when the market has had the SAME information you have, for long enough to "
        "digest it, AND the expected outcome matches what actually happens.\n\n"
        "Markets are frequently surprised by things that seem obvious in hindsight because the "
        "distribution of likely outcomes was genuinely wide beforehand: a 70%-probability outcome "
        "still surprises the market 30% of the time, and that's not irrationality, that's just probability.",
        "'Priced in' means the market's probability-weighted expectation matches an outcome: it doesn't mean surprises can't happen."),
Lesson("l016", "Sentiment Is a Measure of Belief, Not of Business Quality", "Sentiment", TIER_FOUNDATIONAL,
        "Sentiment analysis measures how a company is being TALKED ABOUT: in news, in filings, and "
        "among traders, and turns that into a directional score. It sits alongside fundamental and "
        "technical analysis as one of the three pillars, and it answers a question neither of the "
        "others can: what does the market currently believe, and how fast is that belief changing?\n\n"
        "The reason this matters is timing. A stock does not fall 8% on an earnings miss because the "
        "balance sheet changed overnight: it falls because thousands of people revised their beliefs "
        "at once. Fundamental analysis can tell you a business is worth more than its price; it "
        "cannot tell you what will make the market notice. Sentiment is often the thing that does.\n\n"
        "The critical limitation is right there in the definition. Sentiment measures belief, not "
        "reality. A company can be beloved and structurally unprofitable, or quietly excellent and "
        "completely ignored, and sentiment reports the popularity in both cases. It is also blind to "
        "anything nobody has written about yet: an unreported fraud generates no negative coverage "
        "precisely because it is still unreported.",
        "Sentiment tells you what the market believes right now, which is a genuinely different thing from what is true.",
        glossary=[
            GlossaryTerm("Sentiment velocity",
                "The change in sentiment over the last 24 hours versus the prior period. The LEVEL of "
                "sentiment is largely already reflected in the price; the CHANGE is the part that isn't."),
            GlossaryTerm("Aspect-based sentiment",
                "Scoring only the parts of an article that refer to a specific company. An article titled "
                "'Nvidia soars while Intel slumps' is strongly positive for one and negative for the other; "
                "scoring it as a single block gives both a meaningless neutral."),
        ],
        callouts=[
            Callout("key_idea", "The change matters more than the level",
                "If a company has been covered positively for months, that optimism is in the price. What "
                "isn't in the price is a shift, which is why sentiment velocity is tracked separately "
                "from the sentiment score itself."),
            Callout("common_mistake", "Treating a social sentiment spike as confirmation",
                "Retail chatter volume is the easiest signal in markets to manufacture. A sentiment spike "
                "driven mostly by post volume, with no news and no filing behind it, is the single most "
                "common false positive in this pillar, and buying it means buying exactly when the crowd "
                "is most excited."),
            Callout("why_it_matters", "Why sentiment is weighted by horizon",
                "Sentiment decays fast. Aureus weights it at 40% over a short horizon, 30% over medium, "
                "and just 15% over long, because this quarter's mood tells you nothing about where a "
                "business will be in five years, while a DCF tells you very little about next week."),
        ]),
    Lesson("l017", "Why General Sentiment Tools Fail on Financial Text", "Sentiment", TIER_FOUNDATIONAL,
        "Most off-the-shelf sentiment tools are trained on product reviews and social media. Point one "
        "at a 10-K and it does not merely lose accuracy: it fails in a specific, systematic direction.\n\n"
        "The reason is vocabulary. The language of accounting is full of words that carry strong "
        "negative emotion in ordinary English and none whatsoever in a filing: liability, cost, expense, "
        "debt, charge, obligation, depreciation, impairment, risk. Every company has liabilities. Every "
        "company reports expenses. A general-purpose model reads a routine balance-sheet description and "
        "concludes the company is in trouble.\n\n"
        "This is measurable. Run a neutral sentence like 'total costs and liabilities rose as "
        "depreciation and debt expense increased' through a general social-media sentiment model and it "
        "scores meaningfully negative: the correct answer is zero. Run 'the company did not beat "
        "estimates' through the same model and it scores exactly neutral, because it has no idea that "
        "'beat estimates' is a phrase or that 'did not' inverts it.\n\n"
        "That second failure points at the fix. In financial text, short PHRASES carry far more signal "
        "than individual words. 'Beat' alone is ambiguous. 'Beat estimates' is close to the most "
        "informative two-word sequence in the entire domain. Finance-specific models: whether a "
        "domain lexicon or a model like FinBERT trained on financial text: are built around exactly "
        "that difference.",
        "General sentiment tools misread financial text in a predictable direction, because ordinary accounting vocabulary sounds alarming in everyday English.",
        glossary=[
            GlossaryTerm("FinBERT",
                "A version of the BERT language model fine-tuned on financial text, so it learns that "
                "'liability' is neutral in a filing and that 'cut guidance' is decisively negative."),
            GlossaryTerm("Negation handling",
                "Detecting that 'did not beat estimates' means the opposite of 'beat estimates'. Naive "
                "word-counting misses this entirely and scores the phrase positive."),
        ],
        callouts=[
            Callout("example", "The same sentence, two models",
                "'Total costs and liabilities rose as depreciation and debt expense increased.' A general "
                "social-media model scores this around -0.35 (negative). A finance-specific model scores "
                "it 0.00: correctly, because the sentence describes an accounting fact and takes no "
                "directional position at all."),
            Callout("key_idea", "Phrases beat words",
                "'Cut guidance', 'going concern', 'FDA approval', 'material weakness': each of these is "
                "worth more than any single word in the sentence containing it. This is why financial "
                "sentiment scoring matches phrases first and individual words second."),
        ]),
]
