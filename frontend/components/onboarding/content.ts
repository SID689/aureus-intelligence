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
  id: "fundamental" | "technical" | "quantitative";
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
    id: "quantitative",
    title: "Quantitative Analysis",
    tagline: "What systematic, repeatable edge can be proven across data, not asserted from judgment?",
    timeHorizon: "Milliseconds (arbitrage) to months (systematic strategies)",
    whatItIs:
      "Quantitative analysis applies statistics and machine learning to find edges that are systematic and repeatable across many securities or time periods — rather than judgment calls made one stock at a time. The unifying idea isn't a specific time horizon (it spans an enormous range, from millisecond arbitrage between exchanges to monthly-rebalanced factor strategies) — it's the METHOD: rules are defined in advance, tested against historical data, and applied consistently rather than adjusted case by case based on a gut feeling.",
    whyThisHorizon:
      "Because quant strategies are defined by their method, not a fixed horizon, they show up everywhere from microsecond price-discrepancy arbitrage (pure speed, no forecasting) to statistical factor models that rebalance once a month based on volatility, momentum, or value signals measured across the whole market. What all of them share is systematic, rules-based execution — the opposite of picking one stock because it 'feels right.'",
    dependsOn: [
      { label: "Normalized alternative datasets", detail: "Data beyond just price — trading volume patterns, volatility surfaces, sometimes genuinely 'alternative' data like transaction records or web-scraped signals — cleaned and standardized so it can be compared consistently across thousands of securities." },
      { label: "Statistical / ML features", detail: "Derived signals rather than raw numbers: rolling volatility, momentum measured over specific windows, correlation to a benchmark (beta), and model-estimated forward return based on historical relationships between these features and what happened next." },
    ],
    coreMethod: {
      name: "Rolling volatility, beta/alpha, and regression-based signals",
      explanation:
        "Rolling volatility measures how much a stock's price has been swinging recently, annualized for comparability. Beta measures how sensitive a stock is to overall market moves; alpha measures the return left over after accounting for that market sensitivity — the part of performance that isn't just 'the market went up.' A statistical model (e.g., ridge regression) can be trained on historical relationships between these features and subsequent returns to generate a forward-looking signal, always regularized to avoid over-fitting to noise in a limited sample.",
    },
    risks: [
      { label: "Look-ahead bias", detail: "The single most common way a backtest lies to its creator: accidentally letting a model 'see' information during testing that wouldn't have actually been available at that historical moment — for example, using a company's CURRENT financials to simulate a decision from two years ago. A model that looks brilliant in a backtest with look-ahead bias baked in will fail in live trading, because the future information it relied on isn't actually available yet." },
      { label: "Historical overfitting", detail: "Given enough adjustable parameters, it's always possible to fit a model perfectly to historical noise — capturing coincidental patterns that have zero genuine predictive power going forward. An overfit model looks spectacular on the exact data it was built on and then falls apart the moment it sees new data." },
    ],
    blindSpot:
      "Quantitative models are trained on the past — they have no mechanism for anticipating a genuinely novel event that has no historical precedent in the training data (a new type of regulation, an unprecedented geopolitical shock, a first-of-its-kind technology disruption). They're powerful at finding repeatable patterns and completely unequipped for one-off surprises.",
  },
];

export const SYNTHESIS_NOTE =
  "None of these three methods is simply 'the best' one — they answer different questions and have different blind spots. " +
  "Fundamental analysis tells you what a business is worth but not when the market will agree with you. Technical analysis tells you " +
  "about near-term price behavior but knows nothing about the business itself. Quantitative analysis finds systematic, provable edges " +
  "but can't anticipate events with no historical precedent. Aureus Intelligence's ensemble engine deliberately combines all three — " +
  "and when one leg lacks reliable data for a given stock, it's mathematically de-weighted rather than allowed to silently distort the " +
  "final score toward a false middle ground.";

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
