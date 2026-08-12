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
