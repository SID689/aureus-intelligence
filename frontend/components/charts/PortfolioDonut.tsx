"use client";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { Holding } from "@/types";

const COLORS = [
  "#d4a843", "#22c55e", "#3b82f6", "#8b5cf6",
  "#f97316", "#06b6d4", "#ec4899", "#84cc16",
];

interface Props { holdings: Holding[] }

export default function PortfolioDonut({ holdings }: Props) {
  const data = holdings
    .filter((h) => h.current_weight != null && h.current_weight > 0)
    .sort((a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0))
    .slice(0, 8)
    .map((h) => ({ name: h.ticker, value: h.current_weight ?? 0 }));

  if (!data.length) {
    return (
      <div className="h-48 flex items-center justify-center text-aureus-muted text-sm">
        No holdings data
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width={160} height={160}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={72}
               dataKey="value" strokeWidth={0}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} opacity={0.85} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            formatter={(v: number) => [`${v.toFixed(1)}%`, ""]}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex-1 space-y-1.5">
        {data.map((item, i) => (
          <div key={item.name} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full flex-shrink-0"
                   style={{ background: COLORS[i % COLORS.length] }} />
              <span className="text-white font-medium">{item.name}</span>
            </div>
            <span className="text-aureus-muted">{item.value.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
