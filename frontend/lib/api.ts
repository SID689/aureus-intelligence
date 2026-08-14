// lib/api.ts — typed client for every backend endpoint the frontend calls.
// BASE is intentionally empty: next.config.ts rewrites /api/v1/* to the
// backend container (http://backend:8000) server-side, so both server
// components and the browser can call relative paths without caring
// whether they're inside Docker or not.
const BASE = "";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Analysis ────────────────────────────────────────────────────────────────

export interface AnalysisResult {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  result?: {
    ticker: string;
    signal: "BUY" | "HOLD" | "SELL";
    signal_strength: "STRONG" | "MODERATE" | "WEAK";
    confidence_index: number;
    fundamental_score: number;
    technical_score: number;
    sentiment_score: number;
    reasoning: string;
    reasoning_source: string;
    overall_data_completeness: number;
    module_weights_used: Record<string, number>;
    disclaimer: string;
  };
  error?: string;
}

// Analysis is metered against the caller's plan, so userId is required.
// The server resolves the LIMITS from the database — passing a user id
// identifies you, it does not grant you anything.
export const runQuickAnalysis = (
  ticker: string,
  userId: string,
  horizon: "short_term" | "medium_term" | "long_term" = "medium_term"
): Promise<AnalysisResult> =>
  apiFetch(`/api/v1/analysis/quick/${ticker}?time_horizon=${horizon}&user_id=${encodeURIComponent(userId)}`);

export const enqueueAnalysis = (
  ticker: string,
  userId: string,
  horizon: "short_term" | "medium_term" | "long_term" = "medium_term"
): Promise<{ job_id: string; poll_url: string }> =>
  apiFetch("/api/v1/analysis/run", {
    method: "POST",
    body: JSON.stringify({ ticker, time_horizon: horizon, user_id: userId }),
  });

export const pollAnalysis = (jobId: string): Promise<AnalysisResult> =>
  apiFetch(`/api/v1/analysis/result/${jobId}`);

// ── Analysis: theses & pillar detail ────────────────────────────────────────

export interface ThesisPoint {
  category: string; headline: string; detail: string;
  metric_label: string; metric_value: string;
}
export interface ThesisCase {
  stance: "bull" | "bear";
  summary: string;
  points: ThesisPoint[];
  what_would_change_this: string[];
  source: string;
}
export interface SignalBreakdownItem { label: string; score: number; detail: string }

export interface PillarScore {
  score: number;
  data_completeness: number;
  effective_weights: Record<string, number>;
  signal_breakdown: SignalBreakdownItem[];
  analysis_notes: string[];
  [k: string]: unknown;
}

export interface SectorComparison {
  sector: string;
  peer_count: number;
  medians: Record<string, number>;
  comparisons: Record<string, {
    value: number; median: number; premium_pct: number; favourable: boolean;
  }>;
  relative_score: number | null;
  stale: boolean;
}

/** One high-impact article driving the sentiment reading. */
export interface SentimentCatalyst {
  headline: string;
  source: string;
  url: string;
  published_at: string;
  polarity: number;              // -1..+1
  direction: "positive" | "negative";
  authority: number;             // publisher-quality multiplier
  evidence: string[];            // the phrases that moved the score
}

/** A brief-requested source that has no free tier, surfaced so the UI can
 *  explain a missing stream instead of silently showing a gap. */
export interface UnavailableSource {
  name: string;
  channel: string;
  reason: string;
  to_enable: string;
}

export interface SentimentPillar extends PillarScore {
  // Plan-dependent depth. The pillar SCORE is always present; these say
  // how much of the research behind it this plan includes.
  catalysts_total?: number;
  catalysts_locked?: number;
  sec_tone_locked?: boolean;
  news_score: number;
  social_score: number;
  sec_tone_score: number;
  news_computed: boolean;
  social_computed: boolean;
  sec_tone_computed: boolean;
  overall_label: "Bullish" | "Neutral" | "Bearish";
  sec_tone_label: string;        // Positive | Neutral | Cautious | Computing
  velocity_label: string;
  news_document_count: number;
  social_message_count: number;
  news_polarity: number;
  social_polarity: number;
  polarity_velocity: number;
  volume_velocity: number | null;
  sentiment_confidence: number;  // 0-1
  model_used: string;            // "finbert" | "lexicon"
  catalysts: SentimentCatalyst[];
  source_mix: Record<string, number>;
  unavailable_sources: UnavailableSource[];
  sec_tone_detail: Record<string, unknown>;
}

export interface FullAnalysis {
  sector?: string | null;
  sector_comparison?: SectorComparison;
  ticker: string;
  time_horizon: string;
  signal: "BUY" | "HOLD" | "SELL";
  signal_strength: "STRONG" | "MODERATE" | "WEAK";
  confidence_index: number;
  fundamental_score: number;
  technical_score: number;
  sentiment_score: number;
  fundamental: PillarScore & {
    pe_ratio: number | null; pb_ratio?: number | null; gross_margin: number | null;
    roe: number | null; debt_to_equity: number | null; free_cash_flow: number | null;
    // Declared explicitly rather than left to PillarScore's `[k: string]: unknown`
    // index signature — reaching them through that returns `unknown`, which the
    // metrics grid then cannot pass to a number formatter.
    operating_margin?: number | null;
    revenue_growth_yoy?: number | null;
    current_ratio?: number | null;
    ev_to_ebitda?: number | null;
    price_to_sales?: number | null;
    fcf_yield?: number | null;
    roic?: number | null;
    interest_coverage?: number | null;
    market_cap?: number | null;
    dcf_detail: { intrinsic_value_per_share: number; current_price: number; margin_of_safety: number } | null;
    dcf_skip_reason?: string | null;
  };
  technical: PillarScore & { rsi_14: number | null };
  sentiment: SentimentPillar;
  market_data_provider: string;
  fundamental_data_provider: string;
  reasoning: string;
  reasoning_source: string;
  overall_data_completeness: number;
  module_weights_used: Record<string, number>;
  bull_case: ThesisCase;
  bear_case: ThesisCase;
  generated_at: string;
}

export const getFullAnalysis = (
  ticker: string,
  userId: string,
  horizon: "short_term" | "medium_term" | "long_term" = "medium_term",
): Promise<{ job_id: string; status: string; result: FullAnalysis | null; error?: string }> =>
  apiFetch(`/api/v1/analysis/quick/${ticker}?time_horizon=${horizon}&user_id=${encodeURIComponent(userId)}`);

// ── Market data (real bars — fixes the mock-data chart bug) ──────────────────

export interface PriceBar {
  timestamp: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  signal?: "BUY" | "HOLD" | "SELL";
  confidence?: number;
}

export const getBars = (
  ticker: string,
  days = 90,
  frequency: "1d" | "1h" | "5m" = "1d"
): Promise<{ ticker: string; provider: string; frequency: string; bars: PriceBar[] }> =>
  apiFetch(`/api/v1/market/bars/${ticker}?days=${days}&frequency=${frequency}`);

export const getLatestPrice = (ticker: string): Promise<{ ticker: string; price: number }> =>
  apiFetch(`/api/v1/market/price/${ticker}`);

// ── Portfolio ────────────────────────────────────────────────────────────────

export interface Holding {
  id: string;
  ticker: string;
  quantity: number;
  average_cost_basis: number;
  current_price: number | null;
  current_weight: number | null;
  beta: number | null;
  last_priced_at: string | null;
}

export const ensureDefaultPortfolio = (userId: string): Promise<{ portfolio_id: string; created: boolean }> =>
  apiFetch("/api/v1/portfolio/ensure-default", { method: "POST", body: JSON.stringify({ user_id: userId }) });

export const listHoldings = (portfolioId: string): Promise<{
  portfolio_id: string; holdings: Holding[]; total_value: number;
  total_cost: number; total_pnl: number; total_pnl_pct: number;
}> => apiFetch(`/api/v1/portfolio/holdings?portfolio_id=${portfolioId}`);

export const addHolding = (req: {
  portfolio_id: string; user_id: string; ticker: string;
  quantity: number; average_cost_basis: number;
}): Promise<{ holding_id: string; ticker: string; action: string }> =>
  apiFetch("/api/v1/portfolio/holdings", { method: "POST", body: JSON.stringify(req) });

export const deleteHolding = (holdingId: string, userId: string): Promise<{ deleted: boolean }> =>
  apiFetch(`/api/v1/portfolio/holdings/${holdingId}?user_id=${userId}`, { method: "DELETE" });

export const updateHolding = (
  holdingId: string,
  userId: string,
  updates: { quantity?: number; average_cost_basis?: number }
): Promise<{ holding_id: string; updated: boolean }> =>
  apiFetch(`/api/v1/portfolio/holdings/${holdingId}`, {
    method: "PUT",
    body: JSON.stringify({ user_id: userId, ...updates }),
  });

// ── Lessons ──────────────────────────────────────────────────────────────────

export interface TodaysLesson {
  lesson: { id: string; title: string; category: string; body: string; key_takeaway: string };
  tier: number;
  tier_label: string;
  already_dismissed_today: boolean;
  lessons_completed_count: number;
  lessons_to_next_tier: number | null;
}

export const getTodaysLesson = (userId: string): Promise<TodaysLesson> =>
  apiFetch(`/api/v1/lessons/today?user_id=${userId}`);

export const dismissTodaysLesson = (userId: string, lessonId: string) =>
  apiFetch<{ dismissed: boolean; lessons_completed_count: number; current_tier: number }>(
    "/api/v1/lessons/dismiss",
    { method: "POST", body: JSON.stringify({ user_id: userId, lesson_id: lessonId }) }
  );

export const getLearningLevel = (userId: string) =>
  apiFetch<{
    base_level: number; base_level_label: string;
    effective_tier: number; effective_tier_label: string;
    lessons_completed_count: number;
  }>(`/api/v1/lessons/level?user_id=${userId}`);

export const setLearningLevel = (userId: string, baseLevel: number) =>
  apiFetch<{ base_level: number; base_level_label: string }>("/api/v1/lessons/level", {
    method: "PUT",
    body: JSON.stringify({ user_id: userId, base_level: baseLevel }),
  });

// ── News ─────────────────────────────────────────────────────────────────────

export interface NewsArticle {
  id: string; article_id: string; headline: string; source: string; source_url: string;
  ticker: string; sentiment_score: number; summary: string;
  published_at: string | null; processed_at: string | null;
}

// userId is optional: this feed also backs unauthenticated views, and the
// server treats an absent user as the free tier (delayed).
export const getRecentNews = (
  limit = 25,
  userId?: string,
): Promise<{ count: number; delayed_by_seconds: number; articles: NewsArticle[] }> =>
  apiFetch(`/api/v1/news/recent?limit=${limit}${userId ? `&user_id=${encodeURIComponent(userId)}` : ""}`);

export const refreshNews = (): Promise<{ stages: Record<string, unknown>; elapsed_seconds: number; note: string }> =>
  apiFetch("/api/v1/news/refresh", { method: "POST" });

export const getNewsPipelineStatus = () =>
  apiFetch<{ stream_depths: Record<string, number>; anthropic_configured: boolean }>("/api/v1/news/status");

// ── Education / course browser ───────────────────────────────────────────────
// Self-paced counterpart to the dashboard's daily-lesson card above. Both read
// the same backend curriculum registry, so content never diverges.

export type LessonStatus = "not_started" | "in_progress" | "completed";

export interface LessonSummary {
  id: string; title: string; category: string;
  tier: number; difficulty_level: string; tier_label: string;
  estimated_read_time_minutes: number;
  xp_points: number; max_xp: number;
  quiz_question_count: number; key_takeaway: string;
  status: LessonStatus; xp_earned: number;
  quiz_best_score: number | null; quiz_total: number | null;
  quiz_passed: boolean; completed_at: string | null;
}

export interface EducationModule {
  tier: number; difficulty_level: string; label: string; description: string;
  lesson_count: number; total_xp_available: number; estimated_minutes: number;
  lessons_completed: number; xp_earned: number; percent_complete: number;
  lessons: LessonSummary[];
}

export interface EducationCatalog {
  modules: EducationModule[];
  totals: {
    lessons_total: number; lessons_completed: number;
    xp_earned: number; xp_available: number; percent_complete: number;
  };
}

export interface QuizOption { index: number; question: string; options: string[] }
export interface GlossaryEntry { term: string; definition: string }
export interface LessonCallout { kind: "key_idea" | "why_it_matters" | "common_mistake" | "example"; title: string; body: string }

export interface LessonDetail {
  lesson: {
    id: string; title: string; category: string; tier: number;
    difficulty_level: string; tier_label: string;
    estimated_read_time_minutes: number; xp_points: number; max_xp: number;
    quiz_question_count: number; key_takeaway: string; body: string;
    glossary: GlossaryEntry[]; callouts: LessonCallout[]; quiz: QuizOption[];
  };
  progress: {
    status: LessonStatus; xp_earned: number; quiz_attempts: number;
    quiz_best_score: number | null; quiz_total: number | null; quiz_passed: boolean;
  };
  quiz_pass_mark: number;
  quiz_bonus_xp: number;
}

export interface QuizResult {
  lesson_id: string; score: number; total: number; pass_mark: number;
  passed: boolean; attempts: number; best_score: number;
  xp_earned_total_for_lesson: number;
  results: { index: number; your_answer: number; correct_index: number; correct: boolean; explanation: string }[];
}

export interface Badge {
  id: string; name: string; description: string; icon: string;
  earned: boolean; progress_current: number; progress_target: number;
}

export interface EducationProgress {
  xp_earned: number; xp_available: number;
  lessons_completed: number; lessons_total: number;
  quizzes_taken: number; quizzes_passed: number; perfect_quizzes: number;
  quiz_accuracy_pct: number | null;
  correct_answers: number; total_answers: number;
  by_tier: { tier: number; label: string; description: string; completed: number; total: number }[];
  badges: Badge[];
  legacy_daily_lessons_completed: number;
}

export const getEducationCatalog = (userId: string): Promise<EducationCatalog> =>
  apiFetch(`/api/v1/education/catalog?user_id=${userId}`);

export const getEducationLesson = (lessonId: string, userId: string): Promise<LessonDetail> =>
  apiFetch(`/api/v1/education/lesson/${lessonId}?user_id=${userId}`);

export const startEducationLesson = (lessonId: string, userId: string) =>
  apiFetch<{ lesson_id: string; status: string }>(`/api/v1/education/lesson/${lessonId}/start`, {
    method: "POST", body: JSON.stringify({ user_id: userId }),
  });

export const completeEducationLesson = (lessonId: string, userId: string) =>
  apiFetch<{ lesson_id: string; status: string; xp_earned_total_for_lesson: number }>(
    `/api/v1/education/lesson/${lessonId}/complete`,
    { method: "POST", body: JSON.stringify({ user_id: userId }) },
  );

export const submitEducationQuiz = (lessonId: string, userId: string, answers: number[]): Promise<QuizResult> =>
  apiFetch(`/api/v1/education/lesson/${lessonId}/quiz`, {
    method: "POST", body: JSON.stringify({ user_id: userId, answers }),
  });

export const getEducationProgress = (userId: string): Promise<EducationProgress> =>
  apiFetch(`/api/v1/education/progress?user_id=${userId}`);

// ── Games ────────────────────────────────────────────────────────────────────
// The server withholds every answer until a round ends: FinWordle returns
// tile colours (never the word) and the pattern game returns the setup
// (never the ticker or outcome). Grading is server-side only.

export type TileState = "correct" | "present" | "absent";
export type FinWordleMode = "daily" | "practice";
export type GameSessionStatus = "in_progress" | "won" | "lost";

export interface WordEducation {
  word: string; definition: string; trading_context: string;
  example: string; category: string;
}

export interface FinWordleSession {
  session_id: string;
  mode: FinWordleMode;
  puzzle_date: string | null;
  puzzle_number: number | null;
  word_length: number;
  max_guesses: number;
  guesses: string[];
  tiles: TileState[][];
  keyboard: Record<string, TileState>;
  status: GameSessionStatus;
  guesses_used: number;
  score_awarded: number;
  // Present only once status !== "in_progress".
  answer?: string;
  emoji_grid?: string;
  education?: WordEducation | null;
}

export type PatternDirection = "bullish_breakout" | "bearish_breakdown" | "range_consolidation";

export interface OhlcBar {
  date: string; open: number; high: number; low: number; close: number; volume: number;
}

export type PatternQuestionType = "direction" | "pattern_id" | "pattern_implication";

export interface PatternChoice { value: string; label: string }

export interface PatternInfo {
  key: string; name: string; bias: string; shape: string;
  implication: string; confirmation: string; caveat: string;
  detected_detail?: string | null; confidence?: number | null;
}

export interface PatternResult {
  correct: boolean;
  your_answer: string | null;
  correct_answer: string;
  ticker: string;
  outcome_bars: OhlcBar[];
  correct_direction: string;
  correct_direction_label: string;
  forward_return_pct: number;
  threshold_pct: number;
  rationale: string;
  score_awarded: number;
  pattern: PatternInfo | null;
}

export interface PatternScenario {
  scenario_id: string;
  puzzle_date: string;
  question_type: PatternQuestionType;
  question: string;
  choices: PatternChoice[];
  setup_bars: OhlcBar[];
  setup_notes: string[];
  outcome_horizon_sessions: number;
  answered: boolean;
  // Only present for pattern_implication, where the question already names it.
  named_pattern?: { key: string; name: string; shape: string };
  // Present once answered — lets the reveal survive a page refresh.
  result?: PatternResult;
}

export interface LeaderboardEntry {
  rank: number; user_id: string; display_name: string;
  games_played: number; games_won: number; win_rate_pct: number;
  current_streak: number; max_streak: number; total_score: number;
}

export interface GameStats {
  by_game: Record<string, {
    games_played: number; games_won: number; win_rate_pct: number | null;
    current_streak: number; max_streak: number; total_score: number;
    last_daily_played: string | null;
  }>;
  total_score: number;
  daily_puzzle_number: number;
  daily_status_today: GameSessionStatus | "not_started";
}

export const startFinWordle = (userId: string, mode: FinWordleMode): Promise<FinWordleSession> =>
  apiFetch("/api/v1/games/finwordle/session", {
    method: "POST", body: JSON.stringify({ user_id: userId, mode }),
  });

export const submitFinWordleGuess = (
  userId: string, sessionId: string, guess: string,
): Promise<FinWordleSession> =>
  apiFetch("/api/v1/games/finwordle/guess", {
    method: "POST", body: JSON.stringify({ user_id: userId, session_id: sessionId, guess }),
  });

export const newPatternScenario = (userId: string): Promise<PatternScenario> =>
  apiFetch("/api/v1/games/pattern/scenario", {
    method: "POST", body: JSON.stringify({ user_id: userId }),
  });

export const submitPatternGuess = (
  userId: string, scenarioId: string, answer: string,
): Promise<PatternResult> =>
  apiFetch("/api/v1/games/pattern/guess", {
    method: "POST", body: JSON.stringify({ user_id: userId, scenario_id: scenarioId, answer }),
  });

export const getPatternLibrary = () =>
  apiFetch<{ patterns: PatternInfo[] }>("/api/v1/games/patterns/library");

export const getLeaderboard = (gameType = "finwordle", limit = 20) =>
  apiFetch<{ game_type: string; entries: LeaderboardEntry[] }>(
    `/api/v1/games/leaderboard?game_type=${gameType}&limit=${limit}`,
  );

export const getGameStats = (userId: string): Promise<GameStats> =>
  apiFetch(`/api/v1/games/stats?user_id=${userId}`);

// ── Backtesting ──────────────────────────────────────────────────────────────
// POST /api/v1/backtest/strategy — the main user-facing strategy backtester.
// (The original ensemble signal-accuracy backtest still exists server-side
// at /api/v1/backtest/signal-accuracy/run but isn't wired into the UI.)

export interface RSIRuleRequest {
  type: "rsi";
  period?: number;
  buy_below?: number;
  sell_above?: number;
}

export interface MACrossoverRuleRequest {
  type: "ma_crossover";
  fast_period?: number;
  slow_period?: number;
  ma_type?: "sma" | "ema";
}

export interface StrategyBacktestRequest {
  user_id: string;
  tickers: string[];
  start_date: string;   // YYYY-MM-DD
  end_date: string;
  frequency?: "1d" | "1h" | "5m";
  initial_capital?: number;
  max_position_pct?: number;
  commission_pct?: number;
  slippage_pct?: number;
  rule: RSIRuleRequest | MACrossoverRuleRequest;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  allow_short?: boolean;
}

export interface BacktestTrade {
  ticker: string;
  direction: "long" | "short";
  entry_date: string; entry_price: number;
  exit_date: string; exit_price: number;
  quantity: number; duration_days: number;
  pnl_dollars: number; pnl_pct: number;
  exit_reason: "signal" | "stop_loss" | "take_profit" | "end_of_backtest";
}

export interface EquityCurvePoint {
  date: string;
  strategy_equity: number;
  benchmark_equity: number | null;
}

export interface StrategyBacktestSummary {
  total_trades: number; winning_trades: number; losing_trades: number;
  win_rate_pct: number | null; profit_factor: number | null; expectancy_dollars: number | null;
  avg_win_dollars: number | null; avg_loss_dollars: number | null;
  longest_win_streak: number; longest_loss_streak: number; avg_trade_duration_days: number | null;
  total_return_pct: number; cagr_pct: number;
  max_drawdown_pct: number; max_drawdown_peak_date: string | null; max_drawdown_trough_date: string | null;
  sharpe_ratio: number | null; sortino_ratio: number | null;
  final_equity: number;
}

export interface StrategyBacktestResult {
  config: Record<string, unknown>;
  summary: StrategyBacktestSummary;
  equity_curve: EquityCurvePoint[];
  trades: BacktestTrade[];
}

export const runStrategyBacktest = (req: StrategyBacktestRequest): Promise<StrategyBacktestResult> =>
  apiFetch("/api/v1/backtest/strategy", { method: "POST", body: JSON.stringify(req) });

// ── Alerts ───────────────────────────────────────────────────────────────────

export const getPendingAlerts = (userId: string) =>
  apiFetch<{ user_id: string; count: number; alerts: object[] }>(`/api/v1/alerts/pending/${userId}`);

// ── Auth ─────────────────────────────────────────────────────────────────────

export const signup = (req: { email: string; password: string; display_name?: string }) =>
  apiFetch<{ user_id: string; email: string; tier: string }>("/api/v1/auth/signup", {
    method: "POST", body: JSON.stringify(req),
  });

// ── Quant Lab (Elite / Institutional) ────────────────────────────────────────
// Every endpoint here is tier-gated server-side (see backend app/core/tiers.py)
// and returns HTTP 402 with the caller's current and required tier when the
// plan is too low — which is what the upgrade prompt renders from.

export interface FactorLoading {
  factor: string;        // Mkt-RF | SMB | HML | RMW | CMA
  label: string;
  meaning: string;
  loading: number;
  t_stat: number;
  significant: boolean;  // |t| >= 1.96
}

export interface FactorModel {
  model: string;
  observations: number;
  start: string;
  end: string;
  alpha_daily: number;
  alpha_annualised: number;
  alpha_t_stat: number;
  alpha_significant: boolean;
  r_squared: number;
  loadings: FactorLoading[];
}

export interface VarResult {
  var_pct: number | null;
  cvar_pct: number | null;
  confidence: number;
  horizon_days: number;
  observations: number;
  worst_observed_pct?: number;
}

export interface MonteCarloResult {
  horizon_days: number;
  paths: number;
  method: string;
  mean_return: number;
  median_return: number;
  percentiles: Record<string, number>;
  var_pct: number;
  cvar_pct: number;
  probability_of_loss: number;
  histogram: { lower: number; upper: number; mid: number; count: number }[];
}

export interface BetaStability {
  window_days: number;
  full_sample_beta: number | null;
  rolling_mean: number;
  rolling_std: number;
  rolling_min: number;
  rolling_max: number;
  instability: number | null;
  series: { date: string; beta: number }[];
}

export interface ZScoreSignal {
  window_days: number;
  z_score: number;
  rolling_mean: number;
  rolling_std: number;
  current_price: number;
  percentile_in_window: number;
  interpretation: string;
  series: { date: string; z: number }[];
}

export interface QuantLabReport {
  ticker: string;
  benchmark: string;
  start_date: string;
  end_date: string;
  observations: number;
  current_price: number;
  notes: string[];
  tier: string;
  disclaimer: string;
  factor_model_5: FactorModel | null;
  factor_model_3: FactorModel | null;
  rolling_factor_betas: Record<string, string | number>[];
  performance: {
    sharpe_ratio: number | null; sortino_ratio: number | null;
    annualised_return: number | null; annualised_volatility: number | null;
  } | null;
  var_1d: VarResult | null;
  var_10d: VarResult | null;
  monte_carlo: MonteCarloResult | null;
  max_drawdown: {
    max_drawdown_pct: number | null; peak_date?: string; trough_date?: string;
    recovered?: boolean; recovery_date?: string | null;
  } | null;
  beta_stability: BetaStability | null;
  zscore: ZScoreSignal | null;
  half_life: { half_life_days: number | null; reverting: boolean; note: string } | null;
  volatility_term_structure: {
    windows: Record<string, number>; short_vs_long_ratio?: number;
    regime?: string; note?: string;
  } | null;
  pairs: {
    ticker: string; return_correlation: number;
    observations: number; spread_z_score: number | null;
  }[];
}

export interface QuantAccess {
  user_id: string;
  tier: string;
  has_access: boolean;
  required_tier: string;
}

export const getQuantAccess = (userId: string): Promise<QuantAccess> =>
  apiFetch(`/api/v1/quant/access?user_id=${encodeURIComponent(userId)}`);

export const getQuantLab = (
  ticker: string,
  userId: string,
  opts?: { benchmark?: string; monteCarloHorizon?: number; peers?: string[] },
): Promise<QuantLabReport> => {
  const q = new URLSearchParams({ user_id: userId });
  if (opts?.benchmark) q.set("benchmark", opts.benchmark);
  if (opts?.monteCarloHorizon) q.set("monte_carlo_horizon", String(opts.monteCarloHorizon));
  if (opts?.peers?.length) q.set("peers", opts.peers.join(","));
  return apiFetch(`/api/v1/quant/lab/${ticker}?${q.toString()}`);
};

// ── Account: plan limits and usage ───────────────────────────────────────────

export interface UsageBlock {
  used: number;
  limit: number | null;      // null = unlimited
  unlimited: boolean;
  remaining: number | null;
  exceeded: boolean;
  unit: string;
  resets: string;
}

export interface PlanQuality {
  llm_model_default: string | null;   // null = deterministic, no LLM
  llm_model_deep: string | null;
  market_data_providers: string[];
  sentiment_sources: string[];
  queue_priority: number;
}

export interface CreditBalance {
  allowance: number;
  consumed: number;
  purchased: number;
  remaining: number;
  usd_value_remaining: number;
}

export interface PlanLimits {
  monthly_credits: number;
  cache_ttl_seconds: number;
  max_concurrent_jobs: number;
  api_keys_allowed: number;
  analysis_requests_per_day: number | null;
  backtests_per_day: number | null;
  backtest_tickers: number | null;
  backtest_years: number | null;
  portfolio_holdings: number | null;
  portfolios: number | null;
  voice_minutes_per_month: number | null;
  news_feed_delay_seconds: number;
  sentiment_catalysts: number | null;
  quant_history_years: number | null;
  quant_monte_carlo_paths: number | null;
}

export interface Plan {
  tier: string;
  display_name: string;
  price_cents: number;
  limits: PlanLimits;
  quality: PlanQuality;
  features: Record<string, boolean>;
}

export interface AccountEntitlements extends Plan {
  user_id: string;
  usage: { analysis: UsageBlock; backtest: UsageBlock; voice: UsageBlock };
}

export const getEntitlements = (userId: string): Promise<AccountEntitlements> =>
  apiFetch(`/api/v1/account/entitlements?user_id=${encodeURIComponent(userId)}`);

/** All active plans, served from the DB so pricing can't drift from enforcement. */
export const getPlans = (): Promise<{ plans: Plan[] }> => apiFetch("/api/v1/account/plans");

export const getCredits = (userId: string): Promise<{
  user_id: string;
  balance: CreditBalance;
  transactions: {
    kind: string; credits: number; vendor: string | null;
    operation: string | null; at: string | null;
  }[];
  unit: string;
}> => apiFetch(`/api/v1/account/credits?user_id=${encodeURIComponent(userId)}`);

export interface PlatformApiKey {
  id: string; key_prefix: string; name: string; environment: string;
  scopes: string[]; last_used_at: string | null; request_count: number;
  revoked: boolean; created_at: string | null;
}

export const getApiKeys = (userId: string): Promise<{
  keys: PlatformApiKey[]; allowed: number; tier: string;
}> => apiFetch(`/api/v1/account/api-keys?user_id=${encodeURIComponent(userId)}`);

/** The plaintext key is returned ONCE and never retrievable again. */
export const createApiKey = (userId: string, name: string): Promise<{
  id: string; api_key: string; key_prefix: string; warning: string;
}> => apiFetch("/api/v1/account/api-keys", {
  method: "POST", body: JSON.stringify({ user_id: userId, name }),
});

export const revokeApiKey = (keyId: string, userId: string) =>
  apiFetch<{ revoked: boolean }>(
    `/api/v1/account/api-keys/${keyId}?user_id=${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
