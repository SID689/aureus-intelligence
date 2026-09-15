import { Card, CardContent } from "@/components/ui/card";
import type { StrategyBacktestSummary } from "@/lib/api";

interface Props {
  summary: StrategyBacktestSummary;
}

function StatCard({
  label, value, tone = "neutral", sub,
}: { label: string; value: string; tone?: "good" | "bad" | "neutral"; sub?: string }) {
  const color = tone === "good" ? "text-aureus-emerald" : tone === "bad" ? "text-aureus-crimson" : "text-aureus-text";
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-aureus-muted text-xs uppercase tracking-wider mb-1">{label}</div>
        <div className={`text-xl font-semibold ${color}`}>{value}</div>
        {sub && <div className="text-aureus-muted text-xs mt-0.5">{sub}</div>}
      </CardContent>
    </Card>
  );
}

const fmtPct = (v: number | null, digits = 2) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`);
const fmtNum = (v: number | null, digits = 2) => (v == null ? "—" : v.toFixed(digits));
const fmtMoney = (v: number | null) =>
  v == null ? "—" : `${v >= 0 ? "+" : "-"}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function ResultsOverviewCards({ summary }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatCard label="Total Return" value={fmtPct(summary.total_return_pct)}
                tone={summary.total_return_pct >= 0 ? "good" : "bad"}
                sub={`Final equity $${summary.final_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
      <StatCard label="Win Rate" value={summary.win_rate_pct == null ? "—" : `${summary.win_rate_pct.toFixed(1)}%`}
                sub={`${summary.winning_trades}W / ${summary.losing_trades}L`} />
      <StatCard label="Sharpe Ratio" value={fmtNum(summary.sharpe_ratio)}
                tone={summary.sharpe_ratio == null ? "neutral" : summary.sharpe_ratio >= 1 ? "good" : summary.sharpe_ratio < 0 ? "bad" : "neutral"} />
      <StatCard label="Max Drawdown" value={fmtPct(summary.max_drawdown_pct)} tone="bad" />
      <StatCard label="Sortino Ratio" value={fmtNum(summary.sortino_ratio)} />
      <StatCard label="CAGR" value={fmtPct(summary.cagr_pct)} tone={summary.cagr_pct >= 0 ? "good" : "bad"} />
      <StatCard label="Profit Factor" value={summary.profit_factor == null ? "—" : summary.profit_factor.toFixed(2)}
                tone={summary.profit_factor == null ? "neutral" : summary.profit_factor >= 1.5 ? "good" : summary.profit_factor < 1 ? "bad" : "neutral"} />
      <StatCard label="Total Trades" value={String(summary.total_trades)} />

      <StatCard label="Expectancy / Trade" value={fmtMoney(summary.expectancy_dollars)}
                tone={summary.expectancy_dollars == null ? "neutral" : summary.expectancy_dollars >= 0 ? "good" : "bad"} />
      <StatCard label="Avg Win" value={fmtMoney(summary.avg_win_dollars)} tone="good" />
      <StatCard label="Avg Loss" value={fmtMoney(summary.avg_loss_dollars)} tone="bad" />
      <StatCard label="Avg Trade Duration" value={summary.avg_trade_duration_days == null ? "—" : `${summary.avg_trade_duration_days.toFixed(1)}d`} />

      <StatCard label="Longest Win Streak" value={String(summary.longest_win_streak)} tone="good" />
      <StatCard label="Longest Loss Streak" value={String(summary.longest_loss_streak)} tone="bad" />
    </div>
  );
}
