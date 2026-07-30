"use client";
import { cn } from "@/lib/utils";
import type { Holding, SignalType, AlertSeverity } from "@/types";

// ── MetricCard ─────────────────────────────────────────────────────────────
// Every number on a trading terminal is set in tabular monospace so digits
// align in a column as they update — this isn't decoration, it's how real
// trading software has worked for decades (Bloomberg, Reuters terminals).

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function MetricCard({ label, value, sub, trend, className }: MetricCardProps) {
  return (
    <div className={cn("rounded-lg border border-aureus-rule p-4 space-y-1.5 guilloche-corner", className)}
         style={{ background: "var(--panel)" }}>
      <div className="text-[10px] text-aureus-muted uppercase tracking-widest">{label}</div>
      <div className={cn(
        "font-mono-num text-2xl font-medium",
        trend === "up"   ? "text-aureus-verdigris" :
        trend === "down" ? "text-aureus-oxblood"    : "text-aureus-text"
      )}>
        {value}
      </div>
      {sub && (
        <div className={cn(
          "text-xs font-mono",
          trend === "up"   ? "text-aureus-verdigris" :
          trend === "down" ? "text-aureus-oxblood"    : "text-aureus-muted"
        )}>
          {sub}
        </div>
      )}
    </div>
  );
}

// ── SignalBadge ────────────────────────────────────────────────────────────

interface SignalBadgeProps {
  signal: SignalType;
  strength?: string;
  confidence?: number;
}

const SIGNAL_STYLES: Record<SignalType, string> = {
  BUY:  "bg-aureus-verdigris/10 text-aureus-verdigris border-aureus-verdigris/30",
  HOLD: "bg-aureus-gold/10 text-aureus-gold border-aureus-gold/30",
  SELL: "bg-aureus-oxblood/10 text-aureus-oxblood border-aureus-oxblood/30",
};

export function SignalBadge({ signal, strength, confidence }: SignalBadgeProps) {
  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 rounded px-2.5 py-1 border text-xs font-mono font-semibold uppercase tracking-wide",
      SIGNAL_STYLES[signal]
    )}>
      <span>{signal}</span>
      {strength && <span className="opacity-60">· {strength}</span>}
      {confidence !== undefined && <span className="opacity-60">· {confidence.toFixed(0)}%</span>}
    </div>
  );
}

// ── SeverityBadge ───────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  low:      "text-aureus-muted     border-aureus-rule           bg-aureus-panellift",
  medium:   "text-aureus-gold      border-aureus-gold/30        bg-aureus-gold/5",
  high:     "text-orange-300       border-orange-400/30         bg-orange-950/20",
  critical: "text-aureus-oxblood   border-aureus-oxblood/30     bg-aureus-oxblood/10",
};

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span className={cn("text-[10px] font-mono font-semibold uppercase border rounded px-1.5 py-0.5", SEVERITY_STYLES[severity])}>
      {severity}
    </span>
  );
}

// ── PositionTable ────────────────────────────────────────────────────────────

interface PositionTableProps {
  holdings: Holding[];
  onEditHolding?: (holding: Holding) => void;
}

export function PositionTable({ holdings, onEditHolding }: PositionTableProps) {
  if (holdings.length === 0) {
    return (
      <div className="text-center py-10 text-aureus-muted text-sm">
        No holdings yet. Add a position to start tracking.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-aureus-rule text-aureus-muted text-[10px] uppercase tracking-widest">
            <th className="text-left  py-2 px-3">Ticker</th>
            <th className="text-right py-2 px-3">Qty</th>
            <th className="text-right py-2 px-3">Avg Cost</th>
            <th className="text-right py-2 px-3">Current</th>
            <th className="text-right py-2 px-3">P&amp;L</th>
            <th className="text-right py-2 px-3">Weight</th>
            <th className="text-right py-2 px-3">Beta</th>
            {onEditHolding && <th className="w-8"></th>}
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const pnl    = h.current_price != null ? (h.current_price - h.average_cost_basis) * h.quantity : null;
            const pnlPct = h.current_price != null ? ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100 : null;
            const isPos  = (pnl ?? 0) >= 0;

            return (
              <tr key={h.id || h.ticker}
                  onClick={() => onEditHolding?.(h)}
                  className={cn(
                    "border-b border-aureus-rule/50 transition-colors",
                    onEditHolding ? "hover:bg-white/[0.04] cursor-pointer" : "hover:bg-white/[0.02]"
                  )}>
                <td className="py-3 px-3 font-medium text-aureus-text">{h.ticker}</td>
                <td className="py-3 px-3 text-right font-mono-num text-aureus-muted">{h.quantity.toLocaleString()}</td>
                <td className="py-3 px-3 text-right font-mono-num text-aureus-muted">${h.average_cost_basis.toFixed(2)}</td>
                <td className="py-3 px-3 text-right font-mono-num text-aureus-text">
                  {h.current_price != null ? `$${h.current_price.toFixed(2)}` : "—"}
                </td>
                <td className={cn("py-3 px-3 text-right font-mono-num font-medium", isPos ? "text-aureus-verdigris" : "text-aureus-oxblood")}>
                  {pnl != null ? (
                    <>
                      {isPos ? "+" : ""}{pnl.toFixed(0)}
                      <span className="text-xs ml-1 opacity-70">({isPos ? "+" : ""}{pnlPct?.toFixed(1)}%)</span>
                    </>
                  ) : "—"}
                </td>
                <td className="py-3 px-3 text-right font-mono-num text-aureus-muted">
                  {h.current_weight != null ? `${h.current_weight.toFixed(1)}%` : "—"}
                </td>
                <td className="py-3 px-3 text-right font-mono-num text-aureus-muted">
                  {h.beta != null ? h.beta.toFixed(2) : "—"}
                </td>
                {onEditHolding && (
                  <td className="py-3 px-3 text-right text-aureus-muted text-xs">Edit ›</td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
