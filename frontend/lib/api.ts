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

export const runBacktest = (req: {
  ticker: string; start_date: string; end_date: string;
  forward_window_days?: number; step_days?: number;
}) => apiFetch("/api/v1/backtest/run", { method: "POST", body: JSON.stringify(req) });

// ── Execution ────────────────────────────────────────────────────────────────

export interface OrderRequest {
  strategy_id: string; user_id: string; portfolio_id: string;
  ticker: string; side: "buy" | "sell"; order_type: "market" | "limit";
  quantity: number; limit_price?: number; confidence?: number; is_paper?: boolean;
}

export const submitOrder = (order: OrderRequest): Promise<{
  status: string; trade_id?: string; proposal_id?: string; approval_token?: string;
  broker_order_id?: string; violations?: string[]; warnings?: string[]; order_summary?: object;
}> => apiFetch("/api/v1/execution/submit", { method: "POST", body: JSON.stringify(order) });

export const approveOrder = (proposalId: string, userId: string, approvalToken: string) =>
  apiFetch<{ status: string; broker_order_id?: string }>(`/api/v1/execution/approve/${proposalId}`, {
    method: "POST", body: JSON.stringify({ user_id: userId, approval_token: approvalToken }),
  });

export const rejectOrder = (proposalId: string, userId: string, reason?: string) =>
  apiFetch<{ status: string }>(`/api/v1/execution/reject/${proposalId}`, {
    method: "POST", body: JSON.stringify({ user_id: userId, reason: reason || "User rejected" }),
  });

export const getAccountStatus = (paper = true) =>
  apiFetch<{ equity: number; cash: number; buying_power: number; portfolio_value: number; is_paper: boolean }>(
    `/api/v1/execution/account?paper=${paper}`
  );

// ── Alerts ───────────────────────────────────────────────────────────────────

export const getPendingAlerts = (userId: string) =>
  apiFetch<{ user_id: string; count: number; alerts: object[] }>(`/api/v1/alerts/pending/${userId}`);

// ── Auth ─────────────────────────────────────────────────────────────────────

export const signup = (req: { email: string; password: string; display_name?: string }) =>
  apiFetch<{ user_id: string; email: string; tier: string }>("/api/v1/auth/signup", {
    method: "POST", body: JSON.stringify(req),
  });
