// components/onboarding/content.ts
//
// The actual educational copy shown during onboarding. Written to be
// genuinely useful to someone learning how professional analysis works —
// not marketing copy, not a wall of jargon. Each section explains WHAT
// the method is, WHY its time horizon is what it is, WHAT it actually
// depends on, and WHERE it breaks down. That last part matters most:
// every method has blind spots, and knowing them is what separates an
// informed user from someone who just trusts a number on a screen.

export interface MethodologySection {
  id: "fundamental" | "technical" | "sentiment";
  title: string;
  tagline: string;
  timeHorizon: string;
  whatItIs: string;
  whyThisHorizon: string;
  dependsOn: { label: string; detail: string }[];
  coreMethod: { name: string; explanation: string };
  risks: { label: string; detail: string }[];
  blindSpot: string;
}

export const METHODOLOGIES: MethodologySection[] = [
  {
    id: "fundamental",
    title: "Fundamental Analysis",
    tagline: "Is the business actually worth what the market says it's worth?",
    timeHorizon: "1 year or longer",
    whatItIs:
      "Fundamental analysis asks a simple question: if you ignored the stock ticker entirely and just looked at the business — its revenue, profits, debts, and cash — what would it be worth? You're valuing the company, not the stock price. The idea is that over long enough periods, a stock's price tends to track the value of the underlying business, even though it can swing wildly around that value in the short run.",
    whyThisHorizon:
      "Business fundamentals change slowly. A company doesn't become dramatically more or less valuable week to week — its competitive position, margins, and growth trajectory shift over quarters and years. But its STOCK PRICE can swing 5% in an afternoon on rumor or sentiment alone. Fundamental analysis is deliberately built to ignore that noise and focus on a horizon long enough for the business reality to actually show up in the price.",
    dependsOn: [
      { label: "Balance sheets", detail: "A snapshot of what the company owns (assets) versus what it owes (liabilities) at a single point in time — this is where debt-to-equity and liquidity ratios come from." },
      { label: "Cash flow statements", detail: "How much real cash actually moved in and out of the business. This matters more than reported earnings, because earnings can be shaped by accounting choices in ways cash flow is harder to fake." },
      { label: "SEC EDGAR filings", detail: "The 10-K (annual) and 10-Q (quarterly) reports every public company is legally required to file. This is the primary source — not a summary written by a journalist, but the actual audited numbers." },
    ],
    coreMethod: {
      name: "Discounted Cash Flow (DCF)",
      explanation:
        "Project how much free cash the business will generate in future years, then mathematically discount those future dollars back to what they're worth today (a dollar next year is worth less than a dollar today, because of inflation and risk). Add it all up, and you get an estimate of what the whole company — and therefore each share — is intrinsically worth. Compare that to the current stock price, and you get a 'margin of safety': how much cushion exists between what you'd pay and what the business is actually worth.",
    },
    risks: [
      { label: "Static data decay", detail: "A balance sheet is a photograph, not a video. The moment a 10-K is filed, it starts going stale — by the time the next one arrives three months later, the business may already look different. You're always analyzing a slightly outdated picture." },
      { label: "Human accounting errors and restatements", detail: "Filed financials are prepared by people, audited by people, and occasionally wrong — sometimes through honest error, occasionally through deliberate fraud (Enron and Wirecard are the textbook examples). Fundamental analysis inherits whatever errors are baked into its source data." },
    ],
    blindSpot:
      "A cheap, fundamentally sound stock can stay cheap for years if nothing forces the market to notice — fundamental analysis tells you what SHOULD happen eventually, not when. It's also completely blind to short-term price action: it won't tell you if a stock is about to drop 8% tomorrow on a sector-wide sell-off.",
  },
  {
    id: "technical",
    title: "Technical Analysis",
    tagline: "What is the price itself telling you, right now?",
    timeHorizon: "Minutes to weeks",
    whatItIs:
      "Technical analysis sets the business aside entirely and studies price and volume behavior directly — on the theory that price already reflects everything the market collectively knows, and that human behavior (fear, greed, herding, capitulation) tends to repeat in recognizable patterns. It's less concerned with whether a company is a good long-term investment and more concerned with a narrower, sharper question: is there a favorable, near-term entry or exit point right now?",
    whyThisHorizon:
      "Technical patterns are about market psychology and short-term supply/demand imbalances, both of which resolve quickly — within days or weeks, not years. A momentum signal or an oversold bounce is, by nature, a short-lived phenomenon. Holding a technical signal for a year would mean riding through dozens of unrelated news cycles that have nothing to do with the original pattern.",
    dependsOn: [
      { label: "High-frequency price action", detail: "Open, high, low, close data at daily or even intraday granularity — the raw material every indicator is built from." },
      { label: "Volume profiles", detail: "How many shares actually traded, not just where the price moved. A price move on heavy volume reflects real conviction; the same move on thin volume is far more likely to reverse." },
    ],
    coreMethod: {
      name: "RSI, MACD, and Support/Resistance",
      explanation:
        "RSI (Relative Strength Index) measures whether recent price gains or losses have been unusually large relative to the recent past — extreme readings suggest a stock may be 'overbought' or 'oversold' and due for a reversal. MACD tracks the relationship between two moving averages to gauge whether upward or downward momentum is accelerating or fading. Support and resistance are price levels where buying or selling pressure has clustered historically — think of them as floors and ceilings the price tends to bounce off of, until it doesn't.",
    },
    risks: [
      { label: "High-frequency market noise", detail: "A large fraction of minute-to-minute and even day-to-day price movement is statistical noise — random fluctuation, not meaningful signal. Patterns that look obvious in hindsight are frequently just noise your eye is pattern-matching onto." },
      { label: "False breakouts", detail: "Price appears to break decisively through a support or resistance level — traders act on it — and then it reverses sharply, trapping everyone who entered on the signal. This is one of the most common and costly technical-analysis failure modes." },
    ],
    blindSpot:
      "Technical analysis has zero awareness of the underlying business. It cannot warn you that a company is about to announce fraud, lose a major lawsuit, or file for bankruptcy — the chart only reflects what has already happened, and a sufficiently large surprise makes every prior pattern irrelevant overnight.",
  },
  {
    id: "sentiment",
    title: "Sentiment Analysis",
    tagline: "What is the market being told, and how is the crowd reacting to it?",
    timeHorizon: "Hours to a few weeks",
    whatItIs:
      "Sentiment analysis measures how a company is being TALKED ABOUT — in news wires, in regulatory filings, and among retail traders — and converts that into a directional score. The premise is straightforward: prices are set by people, people act on information and emotion, and both are observable before they finish showing up in the price. A stock does not fall 8% on an earnings miss because the balance sheet changed overnight; it falls because thousands of people simultaneously revised what they believed. Sentiment analysis tries to measure that revision while it is happening.",
    whyThisHorizon:
      "Because sentiment decays faster than anything else measured here. A news catalyst moves a stock over hours to days; within a few weeks it is fully absorbed into the price and carries no further information. Retail positioning mean-reverts faster still — today's crowded bullish trade is next month's unwind. This is why sentiment carries its heaviest weight over short horizons and almost none over multi-year ones: this quarter's mood tells you nothing about where a business will be in five years.",
    dependsOn: [
      { label: "Financial news wires", detail: "Headlines and article text from Finnhub and Yahoo Finance, weighted by publisher. A Reuters wire story and a content farm's rewrite of it arrive looking identical through an API, so each publisher carries an authority weight — otherwise sheer volume of low-quality coverage would outvote first-hand reporting." },
      { label: "SEC filing language (MD&A)", detail: "The Management's Discussion and Analysis section of 10-K and 10-Q filings. This is the one part of a filing where management writes prose rather than reporting numbers, and it is written under legal liability — which makes a shift in how cautiously they write a genuine signal." },
      { label: "Retail trader chatter", detail: "Messages from StockTwits, where a meaningful fraction of posters explicitly tag their own posts as bullish or bearish. That is a stated position rather than an inferred one, which makes it more reliable than trying to read sentiment out of slang and emoji." },
    ],
    coreMethod: {
      name: "Aspect-based scoring, authority weighting, and sentiment velocity",
      explanation:
        "Three ideas do most of the work. ASPECT-BASED scoring means only the sentences that actually mention the target company are scored — an article headlined 'Nvidia soars while Intel slumps' is strongly positive for one and strongly negative for the other, and scoring it as a single blob would give both a meaningless neutral. AUTHORITY AND RECENCY WEIGHTING means a Reuters story from this morning counts for far more than a blog post from last Tuesday, with influence decaying on a 48-hour half-life. SENTIMENT VELOCITY compares the last 24 hours against the prior period: the LEVEL of sentiment is already reflected in the price, so it is the CHANGE that carries information not yet priced in. The text itself is scored with a finance-specific model, because general-purpose sentiment tools are actively wrong on financial language — they read ordinary accounting vocabulary like 'liability', 'cost' and 'debt' as negative when in a filing those words are simply neutral.",
    },
    risks: [
      { label: "Meme-stock manipulation and coordinated posting", detail: "Social sentiment is the single most gameable input in any analysis system, because posting is free and volume is easy to manufacture. Coordinated campaigns exist specifically to create the appearance of organic enthusiasm. Aureus caps social input at a minority of the sentiment score and compresses the influence of any one account, which makes manipulation expensive and bounded — but not impossible. Treat a sentiment spike driven mostly by social volume with real suspicion." },
      { label: "Noise, and spikes with nothing behind them", detail: "Most financial news is not informative. Routine coverage, recycled analyst notes and sector-wide stories generate constant low-level chatter that carries no signal about any individual company. A short-lived sentiment spike with no fundamental change behind it typically reverses within days, and acting on it means buying exactly when the crowd is most excited." },
      { label: "Reflexivity — sentiment follows price as often as it leads it", detail: "Journalists write about stocks that already moved. A day of positive coverage frequently REFLECTS yesterday's rally rather than predicting tomorrow's. Distinguishing sentiment that leads price from sentiment that merely narrates it is genuinely difficult, and no sentiment score fully solves it." },
    ],
    blindSpot:
      "Sentiment measures how a company is being discussed, not how the business is performing. A company can be beloved and structurally unprofitable, or quietly excellent and entirely ignored — and sentiment analysis will report the popularity in both cases, not the reality. It is also systematically blind to anything nobody has written about yet: a fraud that has not been reported, a competitor's product that has not launched. Sentiment tells you what the market currently believes, which is a genuinely different thing from what is true.",
  },
];

export const SYNTHESIS_NOTE =
  "None of these three methods is simply 'the best' one — they answer different questions and have different blind spots. " +
  "Fundamental analysis tells you what a business is worth but not when the market will agree with you. Technical analysis tells you " +
  "about near-term price behavior but knows nothing about the business itself. Sentiment analysis tells you what the market currently " +
  "believes and how fast that belief is changing, but not whether the belief is correct. Aureus Intelligence's ensemble engine " +
  "deliberately combines all three, and weights them differently depending on your time horizon — sentiment matters most over days " +
  "and least over years, while fundamentals do the opposite. When one leg lacks reliable data for a given stock, it's mathematically " +
  "de-weighted rather than allowed to silently distort the final score toward a false middle ground. " +
  "Statistical and factor research — Fama-French exposures, Monte Carlo simulation, Value at Risk — lives separately in the Quant Lab, " +
  "because those tools answer research questions about risk rather than voting on whether to buy.";

export interface SophisticationQuestion {
  id: string;
  question: string;
  options: { value: string; label: string; points: number }[];
}

export const SOPHISTICATION_QUESTIONS: SophisticationQuestion[] = [
  {
    id: "experience",
    question: "How would you describe your investing experience?",
    options: [
      { value: "new", label: "New to investing", points: 0 },
      { value: "some", label: "Some experience (1–3 years)", points: 1 },
      { value: "experienced", label: "Experienced (3+ years)", points: 2 },
      { value: "professional", label: "Professional / institutional background", points: 3 },
    ],
  },
  {
    id: "instruments",
    question: "Which of these have you traded before?",
    options: [
      { value: "stocks_only", label: "Individual stocks or ETFs only", points: 1 },
      { value: "options", label: "Options or other derivatives", points: 2 },
      { value: "margin_short", label: "Margin trading or short selling", points: 2 },
      { value: "none", label: "None yet — I'm starting here", points: 0 },
    ],
  },
  {
    id: "risk_tolerance",
    question: "If a position dropped 20% in a week, what would you do?",
    options: [
      { value: "sell", label: "Sell to limit further loss", points: 0 },
      { value: "hold", label: "Hold and reassess the thesis", points: 1 },
      { value: "buy_more", label: "Consider buying more at the lower price", points: 2 },
    ],
  },
];
