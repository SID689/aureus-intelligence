"use client";
import { cn } from "@/lib/utils";
import type { Holding, SignalType, AlertSeverity } from "@/types";

// ── MetricCard ─────────────────────────────────────────────────────────────

interface MetricCardProps {
  label:       string;
  value:       string;
  sub?:        string;
  trend?:      "up" | "down" | "neutral";
  className?:  string;
}

export function MetricCard({ label, value, sub, trend, className }: MetricCardProps) {
  return (
    <div className={cn(
      "rounded-xl border border-aureus-border p-4 space-y-1",
      className
    )} style={{ background: "var(--surface)" }}>
      <div className="text-xs text-aureus-muted uppercase tracking-wide">{label}</div>
      <div className={cn(
        "text-2xl font-bold",
        trend === "up"   ? "text-aureus-green" :
        trend === "down" ? "text-aureus-red"   : "text-white"
      )}>
        {value}
      </div>
      {sub && (
        <div className={cn(
          "text-xs",
          trend === "up"   ? "text-aureus-green" :
          trend === "down" ? "text-aureus-red"   : "text-aureus-muted"
        )}>
          {sub}
        </div>
      )}
    </div>
  );
}

// ── SignalBadge ────────────────────────────────────────────────────────────

interface SignalBadgeProps {
  signal:    SignalType;
  strength?: string;
  confidence?: number;
}

const SIGNAL_STYLES: Record<SignalType, string> = {
  BUY:  "bg-green-950/50 text-aureus-green border-aureus-green/40",
  HOLD: "bg-amber-950/30 text-aureus-gold border-aureus-gold/40",
  SELL: "bg-red-950/40 text-aureus-red border-aureus-red/40",
};

export function SignalBadge({ signal, strength, confidence }: SignalBadgeProps) {
  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 rounded px-2.5 py-1 border text-xs font-bold uppercase",
      SIGNAL_STYLES[signal]
    )}>
      <span>{signal}</span>
      {strength  && <span className="opacity-60">· {strength}</span>}
      {confidence !== undefined && (
        <span className="opacity-60">· {confidence.toFixed(0)}%</span>
      )}
    </div>
  );
}

// ── SeverityBadge ─────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  low:      "text-aureus-muted  border-aureus-muted/40  bg-gray-900/20",
  medium:   "text-aureus-gold   border-aureus-gold/40   bg-amber-950/20",
  high:     "text-orange-400    border-orange-400/40    bg-orange-950/20",
  critical: "text-aureus-red    border-aureus-red/40    bg-red-950/20",
};

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span className={cn(
      "text-xs font-bold uppercase border rounded px-1.5 py-0.5",
      SEVERITY_STYLES[severity]
    )}>
      {severity}
    </span>
  );
}

// ── PositionTable ──────────────────────────────────────────────────────────

interface PositionTableProps {
  holdings: Holding[];
}

export function PositionTable({ holdings }: PositionTableProps) {
  if (holdings.length === 0) {
    return (
      <div className="text-center py-10 text-aureus-muted text-sm">
        No holdings. Connect a brokerage account to see your positions.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-aureus-border text-aureus-muted text-xs uppercase">
            <th className="text-left py-2 px-3">Ticker</th>
            <th className="text-right py-2 px-3">Qty</th>
            <th className="text-right py-2 px-3">Avg Cost</th>
            <th className="text-right py-2 px-3">Current</th>
            <th className="text-right py-2 px-3">P&L</th>
            <th className="text-right py-2 px-3">Weight</th>
            <th className="text-right py-2 px-3">Beta</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const pnl    = h.current_price != null
              ? (h.current_price - h.average_cost_basis) * h.quantity
              : null;
            const pnlPct = h.current_price != null
              ? ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100
              : null;
            const isPos  = (pnl ?? 0) >= 0;

            return (
              <tr key={h.ticker}
                  className="border-b border-aureus-border/50 hover:bg-white/2 transition-colors">
                <td className="py-3 px-3 font-bold text-white">{h.ticker}</td>
                <td className="py-3 px-3 text-right text-aureus-muted">{h.quantity.toLocaleString()}</td>
                <td className="py-3 px-3 text-right text-aureus-muted">${h.average_cost_basis.toFixed(2)}</td>
                <td className="py-3 px-3 text-right text-white">
                  {h.current_price != null ? `$${h.current_price.toFixed(2)}` : "—"}
                </td>
                <td className={cn("py-3 px-3 text-right font-medium", isPos ? "text-aureus-green" : "text-aureus-red")}>
                  {pnl != null ? (
                    <>
                      {isPos ? "+" : ""}{pnl.toFixed(0)}
                      <span className="text-xs ml-1">
                        ({isPos ? "+" : ""}{pnlPct?.toFixed(1)}%)
                      </span>
                    </>
                  ) : "—"}
                </td>
                <td className="py-3 px-3 text-right text-aureus-muted">
                  {h.current_weight != null ? `${h.current_weight.toFixed(1)}%` : "—"}
                </td>
                <td className="py-3 px-3 text-right text-aureus-muted">
                  {h.beta != null ? h.beta.toFixed(2) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
