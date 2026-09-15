// types/index.ts — shared TypeScript types across the Aureus frontend

// ── Auth ──────────────────────────────────────────────────────────────────────

export type TierName = "sovereign" | "plus" | "elite" | "institutional";

export interface AureusUser {
  id: string;
  email: string;
  name?: string;
  tier: TierName;
  stripeCustomerId?: string;
}

export interface AureusSession {
  user: AureusUser;
  expires: string;
}

// ── Market data ───────────────────────────────────────────────────────────────

export interface PriceBar {
  timestamp: string;   // display label e.g. "Jan 15"
  date: string;        // ISO-8601 for sorting
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  signal?: "BUY" | "HOLD" | "SELL";
  confidence?: number;
}

export interface SupportResistanceLevel {
  price: number;
  level_type: "support" | "resistance";
  strength: number;
}

// ── Portfolio ─────────────────────────────────────────────────────────────────

export interface Holding {
  id: string;
  ticker: string;
  quantity: number;
  average_cost_basis: number;
  current_price: number | null;
  current_weight: number | null;
  beta: number | null;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
}

export interface Portfolio {
  id: string;
  name: string;
  is_paper: boolean;
  base_currency: string;
  holdings: Holding[];
  total_value?: number;
  daily_pnl?: number;
  daily_pnl_pct?: number;
}

// ── Analysis ──────────────────────────────────────────────────────────────────

export type SignalType = "BUY" | "HOLD" | "SELL";
export type SignalStrength = "STRONG" | "MODERATE" | "WEAK";
export type TimeHorizon = "short_term" | "medium_term" | "long_term";

export interface AnalysisResult {
  ticker: string;
  signal: SignalType;
  signal_strength: SignalStrength;
  confidence_index: number;
  fundamental_score: number;
  technical_score: number;
  sentiment_score: number;
  time_horizon: string;
  generated_at: string;
  disclaimer: string;
}

// ── Alerts ────────────────────────────────────────────────────────────────────

export type AlertSeverity = "low" | "medium" | "high" | "critical";

export interface PortfolioAlert {
  id: string;
  ticker?: string;
  headline?: string;
  message?: string;
  severity: AlertSeverity;
  sentiment_score?: number;
  beta_volatility_impact?: number;
  dispatched_at?: string;
  requires_human_review?: boolean;
}

// ── Tier display metadata ─────────────────────────────────────────────────────
// COSMETIC ONLY. The numeric limits that used to live here (analyses per day,
// voice minutes, real-time news) drifted out of sync with the database the
// moment the plans were edited — this map still claimed 10 analyses/day for
// Sovereign after the real limit became 15, and "unlimited" for Elite after it
// became 200. Limits now come from GET /api/v1/account/entitlements, which
// reads subscription_tiers. Do not reintroduce limit values here.

export const TIER_FEATURES: Record<TierName, { label: string; color: string }> = {
  sovereign:     { label: "Sovereign",     color: "text-aureus-muted" },
  plus:          { label: "Plus",          color: "text-aureus-soft" },
  elite:         { label: "Elite",         color: "text-aureus-gold" },
  institutional: { label: "Institutional", color: "text-aureus-text" },
};
