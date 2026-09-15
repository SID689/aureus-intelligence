"use client";
import { cn } from "@/lib/utils";
import { Figure, WeightBar } from "@/components/ui/primitives";
import { money, price, signed, signedMoney } from "@/lib/format";
import type { Holding, SignalType } from "@/types";

/**
 * MetricCard is gone. It rendered the row of four identical stat tiles
 * that made the dashboard read as a template; the same numbers now sit in
 * `StatColumns` (ui/primitives), divided by hairlines instead of each
 * being wrapped in its own bordered box.
 *
 * PortfolioDonut is gone too — `SegmentedBar` says the same thing in one
 * row, and the donut's blue/purple/pink ramp shared no hue with anything
 * else on the platform.
 */

// ── SignalBadge ────────────────────────────────────────────────────────────

const SIGNAL_STYLES: Record<SignalType, string> = {
  BUY:  "bg-aureus-emerald/10 text-aureus-emerald border-aureus-emerald/30",
  HOLD: "bg-aureus-gold/10      text-aureus-gold      border-aureus-gold/30",
  SELL: "bg-aureus-crimson/10   text-aureus-crimson   border-aureus-crimson/30",
};

export function SignalBadge({
  signal, strength, confidence, size = "md",
}: {
  signal: SignalType; strength?: string; confidence?: number; size?: "sm" | "md";
}) {
  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 rounded border font-mono font-semibold uppercase tracking-[0.1em]",
      size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
      SIGNAL_STYLES[signal]
    )}>
      <span>{signal}</span>
      {strength && <span className="opacity-60">· {strength}</span>}
      {confidence !== undefined && <span className="opacity-60">· {confidence.toFixed(0)}%</span>}
    </div>
  );
}

// ── PositionTable ───────────────────────────────────────────────────────────

/**
 * The weight column draws its own proportional bar in the row rather than
 * deferring to a separate allocation widget. The table then carries the
 * composition itself, instead of two components repeating each other.
 */
export function PositionTable({
  holdings, onEditHolding,
}: {
  holdings: Holding[]; onEditHolding?: (h: Holding) => void;
}) {
  if (holdings.length === 0) return null;

  const maxWeight = Math.max(1, ...holdings.map((h) => h.current_weight ?? 0));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={{ minWidth: 780 }}>
        <thead>
          <tr className="label-caps">
            <th className="text-left  py-2.5 px-5 font-medium">Ticker</th>
            <th className="text-right py-2.5 px-3 font-medium">Qty</th>
            <th className="text-right py-2.5 px-3 font-medium">Avg cost</th>
            <th className="text-right py-2.5 px-3 font-medium">Last</th>
            <th className="text-right py-2.5 px-3 font-medium">Market value</th>
            <th className="text-right py-2.5 px-3 font-medium">Gain / loss</th>
            <th className="text-left  py-2.5 px-3 font-medium w-40">Weight</th>
            <th className="text-right py-2.5 px-5 font-medium">Beta</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const pnl    = h.current_price != null ? (h.current_price - h.average_cost_basis) * h.quantity : null;
            const pnlPct = h.current_price != null
              ? ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100
              : null;
            const value  = h.current_price != null ? h.current_price * h.quantity : null;
            const tone   = pnl == null ? "muted" : pnl >= 0 ? "up" : "down";

            return (
              <tr
                key={h.id || h.ticker}
                onClick={() => onEditHolding?.(h)}
                className={cn("border-t border-aureus-rulesoft", onEditHolding && "ledger-row cursor-pointer")}
              >
                <td className="py-3 px-5 font-medium text-aureus-text">{h.ticker}</td>
                <td className="py-3 px-3 text-right"><Figure tone="muted" className="text-[13px]">{h.quantity.toLocaleString()}</Figure></td>
                <td className="py-3 px-3 text-right"><Figure tone="muted" className="text-[13px]">{price(h.average_cost_basis)}</Figure></td>
                <td className="py-3 px-3 text-right"><Figure className="text-[13px]">{price(h.current_price)}</Figure></td>
                <td className="py-3 px-3 text-right"><Figure className="text-[13px]">{value != null ? money(value) : "—"}</Figure></td>
                <td className="py-3 px-3 text-right">
                  {pnl != null ? (
                    <>
                      <Figure tone={tone} className="text-[13px]">{signedMoney(pnl)}</Figure>
                      <Figure tone={tone} className="text-[11px] opacity-70"> {signed(pnlPct!, 1)}%</Figure>
                    </>
                  ) : <Figure tone="muted" className="text-[13px]">—</Figure>}
                </td>
                <td className="py-3 px-3">
                  <span className="flex items-center gap-2">
                    <WeightBar value={h.current_weight ?? 0} max={maxWeight} className="flex-1" />
                    <Figure tone="muted" className="text-[11px] w-11 text-right">
                      {h.current_weight != null ? `${h.current_weight.toFixed(1)}%` : "—"}
                    </Figure>
                  </span>
                </td>
                <td className="py-3 px-5 text-right"><Figure tone="muted" className="text-[13px]">{h.beta != null ? h.beta.toFixed(2) : "—"}</Figure></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
