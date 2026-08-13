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
    quantitative_score: number;
    reasoning: string;
    reasoning_source: string;
    overall_data_completeness: number;
    module_weights_used: Record<string, number>;
    disclaimer: string;
  };
  error?: string;
}

export const runQuickAnalysis = (
  ticker: string,
  horizon: "short_term" | "medium_term" | "long_term" = "medium_term"
): Promise<AnalysisResult> =>
  apiFetch(`/api/v1/analysis/quick/${ticker}?time_horizon=${horizon}`);

export const enqueueAnalysis = (
  ticker: string,
  horizon: "short_term" | "medium_term" | "long_term" = "medium_term"
): Promise<{ job_id: string; poll_url: string }> =>
  apiFetch("/api/v1/analysis/run", {
    method: "POST",
    body: JSON.stringify({ ticker, time_horizon: horizon }),
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

export interface FullAnalysis {
  ticker: string;
  time_horizon: string;
  signal: "BUY" | "HOLD" | "SELL";
  signal_strength: "STRONG" | "MODERATE" | "WEAK";
  confidence_index: number;
  fundamental_score: number;
  technical_score: number;
  quantitative_score: number;
  fundamental: PillarScore & {
    pe_ratio: number | null; pb_ratio?: number | null; gross_margin: number | null;
    roe: number | null; debt_to_equity: number | null; free_cash_flow: number | null;
    dcf_detail: { intrinsic_value_per_share: number; current_price: number; margin_of_safety: number } | null;
    dcf_skip_reason?: string | null;
  };
  technical: PillarScore & { rsi_14: number | null };
  quantitative: PillarScore & {
    beta_vs_spy: number | null; alpha_vs_spy: number | null;
    sharpe_ratio: number | null; rolling_volatility_30d: number | null;
  };
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
  horizon: "short_term" | "medium_term" | "long_term" = "medium_term",
): Promise<{ job_id: string; status: string; result: FullAnalysis | null; error?: string }> =>
  apiFetch(`/api/v1/analysis/quick/${ticker}?time_horizon=${horizon}`);

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

export const getRecentNews = (limit = 25): Promise<{ count: number; articles: NewsArticle[] }> =>
  apiFetch(`/api/v1/news/recent?limit=${limit}`);

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
