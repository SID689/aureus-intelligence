"use client";
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, type TooltipProps,
} from "recharts";
import type { EquityCurvePoint } from "@/lib/api";

interface Props {
  points: EquityCurvePoint[];
}

function EquityTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const strategy = payload.find((p) => p.dataKey === "strategy_equity")?.value as number | undefined;
  const benchmark = payload.find((p) => p.dataKey === "benchmark_equity")?.value as number | undefined;
  return (
    <div className="rounded-sm border border-aureus-rule p-3 text-xs space-y-1 shadow-overlay" style={{ background: "var(--ink)" }}>
      <div className="text-aureus-muted font-medium">{label}</div>
      {strategy != null && (
        <div className="text-aureus-gold font-bold">Strategy: ${strategy.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
      )}
      {benchmark != null && (
        <div className="text-aureus-muted">SPY Benchmark: ${benchmark.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
      )}
    </div>
  );
}

export default function EquityCurveChart({ points }: Props) {
  if (points.length === 0) return null;

  const allValues = points.flatMap((p) => [p.strategy_equity, p.benchmark_equity ?? p.strategy_equity]);
  const min = Math.min(...allValues) * 0.98;
  const max = Math.max(...allValues) * 1.02;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-4 px-1 text-xs text-aureus-muted">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-aureus-gold inline-block" />Strategy Equity</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-aureus-muted inline-block" />SPY Benchmark</span>
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={Math.max(1, Math.floor(points.length / 8))}
          />
          <YAxis
            orientation="right"
            domain={[min, max]}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
            width={55}
          />
          <Tooltip content={<EquityTooltip />} />
          <Line type="monotone" dataKey="benchmark_equity" stroke="var(--text-muted)" strokeWidth={1.5} dot={false}
                activeDot={{ r: 4, fill: "var(--text-muted)" }} strokeDasharray="4 3" />
          <Line type="monotone" dataKey="strategy_equity" stroke="var(--gold)" strokeWidth={2} dot={false}
                activeDot={{ r: 4, fill: "var(--gold)" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
