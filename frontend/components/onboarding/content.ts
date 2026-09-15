// components/onboarding/content.ts
//
// The educational copy shown during onboarding.
//
// ── REWRITE NOTE ────────────────────────────────────────────────────
// The previous version ran roughly 350 words per pillar in one
// undifferentiated column. It was accurate and nobody read it. This
// version keeps every substantive point and cuts the connective padding,
// then splits what remains into fields the UI can reveal progressively:
//
//   essence      one line, always visible — the hook
//   keyIdea      the single sentence worth remembering
//   whatItIs     two tight paragraphs, always visible
//   dependsOn /  detail, behind a tab — present for the curious, not in
//   coreMethod   the way of someone who just wants the gist
//   risks /      the failure modes, given their own visual treatment,
//   blindSpot    because "where this lies to you" is the part that
//                actually protects a new user
//
// Nothing was cut for being discouraging. Every pillar still leads the
// reader to its own weaknesses, because a user who trusts a number they
// don't understand is the failure this whole flow exists to prevent.

export interface MethodologySection {
  id: "fundamental" | "technical" | "sentiment";
  title: string;
  /** One line, shown on the pillar selector. */
  essence: string;
  tagline: string;
  timeHorizon: string;
  /** Where this pillar peaks in the ensemble, for the weighting visual. */
  weightPeak: string;
  weightByHorizon: { horizon: string; pct: number }[];
  /** The single sentence worth remembering. */
  keyIdea: string;
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
    title: "Fundamental",
    essence: "What the business is actually worth",
    tagline: "Is the business worth what the market says it's worth?",
    timeHorizon: "1 year or longer",
    weightPeak: "65%",
    weightByHorizon: [
      { horizon: "Days", pct: 10 },
      { horizon: "Months", pct: 35 },
      { horizon: "Years", pct: 65 },
    ],
    keyIdea:
      "A cheap, well-run business can stay cheap for years. Fundamentals tell you what should happen eventually, never when.",
    whatItIs:
      "Ignore the ticker entirely and value the company: its revenue, margins, debts and cash. Over long enough periods a share price tends to track the value of the business underneath it, even while swinging wildly around that value in the short run.",
    whyThisHorizon:
      "Business fundamentals move slowly. A company's competitive position and margins shift over quarters and years, while its stock can move 5% in an afternoon on rumour. This pillar is deliberately built to ignore that noise.",
    dependsOn: [
      { label: "Balance sheets", detail: "What the company owns against what it owes at a point in time, the source of every leverage and liquidity ratio." },
      { label: "Cash flow statements", detail: "How much real cash moved. This matters more than reported earnings, which accounting choices can shape in ways cash is harder to." },
      { label: "SEC filings", detail: "The 10-K and 10-Q every public company must file. Primary audited numbers, not a journalist's summary of them." },
    ],
    coreMethod: {
      name: "Discounted Cash Flow",
      explanation:
        "Project the free cash the business will generate, then discount those future dollars back to what they are worth today: a dollar next year is worth less than a dollar now. Sum it, divide by shares, compare to the market price. The gap is your margin of safety.",
    },
    risks: [
      { label: "Static data decay", detail: "A balance sheet is a photograph, not a video. It starts going stale the moment it is filed, and the next one is three months away." },
      { label: "Accounting error and fraud", detail: "Filed numbers are prepared by people and occasionally wrong, sometimes honestly, occasionally not. Enron and Wirecard both passed audit." },
    ],
    blindSpot:
      "Completely blind to short-term price action. It will not warn you a stock is about to drop 8% tomorrow in a sector-wide selloff, and it cannot tell you when the market will finally agree with you.",
  },
  {
    id: "technical",
    title: "Technical",
    essence: "What the price itself is telling you",
    tagline: "What is the price doing right now, and on what conviction?",
    timeHorizon: "Minutes to weeks",
    weightPeak: "50%",
    weightByHorizon: [
      { horizon: "Days", pct: 50 },
      { horizon: "Months", pct: 35 },
      { horizon: "Years", pct: 20 },
    ],
    keyIdea:
      "Price already reflects everything the market collectively knows, including things no filing will show you for months.",
    whatItIs:
      "Set the business aside and study price and volume directly, on the theory that human behaviour (fear, greed, herding, capitulation) repeats in recognisable patterns. The question narrows from 'is this a good company' to 'is this a favourable entry right now'.",
    whyThisHorizon:
      "Technical patterns are about market psychology and short-term supply and demand, both of which resolve in days or weeks. Holding a momentum signal for a year means riding through dozens of news cycles that have nothing to do with it.",
    dependsOn: [
      { label: "Price action", detail: "Open, high, low and close at daily or intraday granularity, the raw material every indicator is derived from." },
      { label: "Volume profile", detail: "How many shares actually traded. A move on heavy volume reflects conviction; the same move on thin volume is far likelier to reverse." },
    ],
    coreMethod: {
      name: "RSI, MACD and support/resistance",
      explanation:
        "RSI measures whether recent gains or losses have been unusually large, flagging overbought and oversold extremes. MACD tracks whether momentum is accelerating or fading. Support and resistance are levels where buying or selling has clustered historically: floors and ceilings price tends to bounce off, until it doesn't.",
    },
    risks: [
      { label: "Noise mistaken for signal", detail: "A large share of day-to-day movement is statistically random. Patterns that look obvious in hindsight are frequently your eye finding shapes in noise." },
      { label: "False breakouts", detail: "Price breaks a level convincingly, traders act, and it snaps back, trapping everyone who entered. One of the most common and costly failure modes." },
    ],
    blindSpot:
      "Zero awareness of the underlying business. It cannot warn you a company is about to announce fraud, lose a lawsuit, or file for bankruptcy. A large enough surprise makes every prior pattern irrelevant overnight.",
  },
  {
    id: "sentiment",
    title: "Sentiment",
    essence: "What the market currently believes",
    tagline: "What is the market being told, and how is the crowd reacting?",
    timeHorizon: "Hours to a few weeks",
    weightPeak: "40%",
    weightByHorizon: [
      { horizon: "Days", pct: 40 },
      { horizon: "Months", pct: 30 },
      { horizon: "Years", pct: 15 },
    ],
    keyIdea:
      "Sentiment measures belief, not reality. A company can be beloved and unprofitable, or excellent and ignored.",
    whatItIs:
      "Measure how a company is being talked about (in news wires, in regulatory filings, and among retail traders) and convert that into a directional score. Prices are set by people acting on information and emotion, and both are observable before they finish showing up in the price.",
    whyThisHorizon:
      "A stock does not fall 8% on an earnings miss because the balance sheet changed overnight. It falls because thousands of people revised what they believed at once. That revision is measurable while it happens, and fully absorbed within weeks.",
    dependsOn: [
      { label: "Financial news wires", detail: "Headlines and article text, weighted by publisher, a Reuters wire and a content farm's rewrite arrive looking identical through an API and should not count equally." },
      { label: "SEC filing tone", detail: "The MD&A section of 10-K and 10-Q filings, where management writes prose under legal liability. A shift in how cautiously they write is real signal." },
      { label: "Retail chatter", detail: "StockTwits messages, where a meaningful share of posters explicitly tag their own post bullish or bearish, a stated position rather than an inferred one." },
    ],
    coreMethod: {
      name: "Aspect-based scoring and velocity",
      explanation:
        "Only sentences that actually name the target company are scored, so 'Nvidia soars while Intel slumps' produces the right verdict for each rather than a meaningless average. Influence decays on a 48-hour half-life. And velocity, the last 24 hours against the prior period, matters more than the level, because the level is already in the price and the change is not.",
    },
    risks: [
      { label: "Meme-stock manipulation", detail: "Posting is free and volume is easy to manufacture. Aureus caps social input at a minority of the score and compresses any one account's influence, which makes manipulation expensive and bounded, not impossible." },
      { label: "Reflexivity", detail: "Journalists write about stocks that already moved. A day of positive coverage often reflects yesterday's rally rather than predicting tomorrow's." },
    ],
    blindSpot:
      "Systematically blind to anything nobody has written about yet: an unreported fraud generates no negative coverage precisely because it is still unreported.",
  },
];

export const SYNTHESIS_NOTE =
  "None of these three is simply the best one. Fundamental analysis tells you what a business is worth but not when the market will agree. Technical analysis reads near-term price behaviour but knows nothing about the business. Sentiment tells you what the market believes and how fast that belief is changing, but not whether the belief is correct. Aureus combines all three and weights them by your time horizon, and when one lacks reliable data for a stock, it is mathematically de-weighted rather than allowed to drag the score toward a false middle.";

// ── Diagnostic ────────────────────────────────────────────────────────
// Reworked from three bare radio lists. Two changes:
//
//   1. Every option now carries a `detail` line. "Some experience" means
//      different things to different people, and a one-line clarification
//      produces a far more honest self-assessment than a bare label.
//   2. A fourth question about INTENT was added. Experience alone was
//      calibrating the interface — but someone learning deliberately and
//      someone screening a watchlist want opposite amounts of
//      explanation at identical experience levels.

export interface SophisticationQuestion {
  id: string;
  question: string;
  /** Framing shown under the question — why it is being asked. */
  helper: string;
  options: { value: string; label: string; detail: string; points: number }[];
}

export const SOPHISTICATION_QUESTIONS: SophisticationQuestion[] = [
  {
    id: "experience",
    question: "How long have you been investing?",
    helper: "There's no wrong answer, this only sets how much we explain by default.",
    options: [
      { value: "new", label: "I'm just starting", detail: "Little or no experience buying securities", points: 0 },
      { value: "some", label: "One to three years", detail: "Comfortable placing trades, still learning the mechanics", points: 1 },
      { value: "experienced", label: "Three years or more", detail: "You read filings and know your way around a chart", points: 2 },
      { value: "professional", label: "Professionally", detail: "Institutional, advisory or markets background", points: 3 },
    ],
  },
  {
    id: "instruments",
    question: "What have you actually traded?",
    helper: "Instruments you've used say more about familiarity than years alone.",
    options: [
      { value: "none", label: "Nothing yet", detail: "Starting from here", points: 0 },
      { value: "stocks_only", label: "Stocks and ETFs", detail: "Long positions in individual names or funds", points: 1 },
      { value: "options", label: "Options or derivatives", detail: "Calls, puts, spreads or futures", points: 2 },
      { value: "margin_short", label: "Margin or short selling", detail: "Leveraged or directional-short positions", points: 2 },
    ],
  },
  {
    id: "risk_tolerance",
    question: "A position drops 20% in a week. What's your instinct?",
    helper: "This is about temperament, not correctness, all three are defensible.",
    options: [
      { value: "sell", label: "Cut the loss", detail: "Exit and preserve what's left", points: 0 },
      { value: "hold", label: "Re-examine the thesis", detail: "Check whether anything actually changed before acting", points: 1 },
      { value: "buy_more", label: "Look at buying more", detail: "Treat it as the same asset at a better price", points: 2 },
    ],
  },
  {
    id: "intent",
    question: "What do you want Aureus for?",
    helper: "This shapes what we surface first, not what you're allowed to use.",
    options: [
      { value: "learning", label: "Learning the craft", detail: "Build understanding before committing much capital", points: 0 },
      { value: "second_opinion", label: "A second opinion", detail: "Pressure-test ideas you've already formed", points: 1 },
      { value: "screening", label: "Screening and monitoring", detail: "Track a watchlist and surface what changed", points: 2 },
      { value: "research", label: "Deep research", detail: "Factor exposures, backtests and tail risk", points: 3 },
    ],
  },
];

/** Copy for the calibration result, keyed by resolved tier. */
export const TIER_RESULT: Record<string, { title: string; body: string }> = {
  novice: {
    title: "Guided",
    body: "Explanations stay expanded, jargon is defined inline, and the daily lesson starts at the foundations. Every score arrives with its reasoning shown rather than folded away.",
  },
  intermediate: {
    title: "Balanced",
    body: "Reasoning is one tap away rather than always open, and lessons start mid-curriculum. You'll see the sub-signals behind each score without having to ask twice.",
  },
  advanced: {
    title: "Direct",
    body: "Numbers lead and explanation follows only where it earns its place. Lessons start at factor mechanics and market microstructure, and the Quant Lab is where you'll spend your time.",
  },
};
