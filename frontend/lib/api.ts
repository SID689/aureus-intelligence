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

// ── Execution ────────────────────────────────────────────────────────────────

export interface OrderRequest {
  strategy_id: string;
  user_id: string;
  portfolio_id: string;
  ticker: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  quantity: number;
  limit_price?: number;
  confidence?: number;
  is_paper?: boolean;
}

export const submitOrder = (order: OrderRequest): Promise<{
  status: string;
  trade_id?: string;
  proposal_id?: string;
  approval_token?: string;
  broker_order_id?: string;
  violations?: string[];
  warnings?: string[];
  order_summary?: object;
}> => apiFetch("/api/v1/execution/submit", { method: "POST", body: JSON.stringify(order) });

export const approveOrder = (
  proposalId: string,
  userId: string,
  approvalToken: string
): Promise<{ status: string; broker_order_id?: string }> =>
  apiFetch(`/api/v1/execution/approve/${proposalId}`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, approval_token: approvalToken }),
  });

export const rejectOrder = (
  proposalId: string,
  userId: string,
  reason?: string
): Promise<{ status: string }> =>
  apiFetch(`/api/v1/execution/reject/${proposalId}`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, reason: reason || "User rejected" }),
  });

export const getProposalStatus = (proposalId: string) =>
  apiFetch<{
    proposal_id: string;
    state: string;
    ticker: string;
    side: string;
    quantity: number;
    stop_loss_price: number;
    take_profit_price: number;
    confidence: number;
    expires_at: string;
  }>(`/api/v1/execution/proposal/${proposalId}`);

export const getAccountStatus = (paper = true) =>
  apiFetch<{
    equity: number;
    cash: number;
    buying_power: number;
    portfolio_value: number;
    is_paper: boolean;
  }>(`/api/v1/execution/account?paper=${paper}`);

// ── Alerts ───────────────────────────────────────────────────────────────────

export const getPendingAlerts = (userId: string) =>
  apiFetch<{ user_id: string; count: number; alerts: object[] }>(
    `/api/v1/alerts/pending/${userId}`
  );
