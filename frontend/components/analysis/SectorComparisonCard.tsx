"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SectorComparison } from "@/lib/api";

/**
 * How the ticker's multiples sit against its sector's median.
 *
 * Shows the raw value, the peer median and the gap for every metric — not
 * just a verdict — because "expensive" is only meaningful next to what it is
 * expensive relative to.
 */

const LABELS: Record<string, string> = {
  pe_ratio: "P/E", price_to_sales: "P/S", pb_ratio: "P/B", ev_to_fcf: "EV/FCF",
  gross_margin: "Gross Margin", operating_margin: "Operating Margin",
  return_on_equity: "ROE", roic: "ROIC", debt_to_equity: "Debt/Equity",
};
const PCT_METRICS = new Set(["gross_margin", "operating_margin", "return_on_equity", "roic"]);

export default function SectorComparisonCard({ data }: { data: SectorComparison }) {
  if (data.stale) {
    return (
      <Card>
        <CardHeader><CardTitle>Sector Comparison</CardTitle></CardHeader>
        <CardContent>
          <p className="text-xs text-aureus-muted">
            Computing {data.sector} peer medians across {data.peer_count} companies —
            this appears on your next load.
          </p>
        </CardContent>
      </Card>
    );
  }

  const rows = Object.entries(data.comparisons);
  if (rows.length === 0) return null;

  const fmt = (k: string, v: number) => (PCT_METRICS.has(k) ? `${v.toFixed(1)}%` : `${v.toFixed(2)}x`);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Sector Comparison — {data.sector}</CardTitle>
          {data.relative_score != null && (
            <span className="text-[10px] text-aureus-muted">
              Relative valuation{" "}
              <span className={data.relative_score >= 50 ? "text-aureus-green" : "text-aureus-red"}>
                {data.relative_score.toFixed(0)}/100
              </span>
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-aureus-muted uppercase tracking-wider text-[10px]">
                <th className="text-left py-1.5">Metric</th>
                <th className="text-right py-1.5">This Stock</th>
                <th className="text-right py-1.5">Sector Median</th>
                <th className="text-right py-1.5">vs Median</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([k, c]) => (
                <tr key={k} className="border-t border-aureus-rule/50">
                  <td className="py-1.5 text-aureus-text">{LABELS[k] ?? k}</td>
                  <td className="py-1.5 text-right font-mono text-white">{fmt(k, c.value)}</td>
                  <td className="py-1.5 text-right font-mono text-aureus-muted">{fmt(k, c.median)}</td>
                  <td className={`py-1.5 text-right font-mono ${c.favourable ? "text-aureus-green" : "text-aureus-red"}`}>
                    {c.premium_pct >= 0 ? "+" : ""}{c.premium_pct.toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[10px] text-aureus-muted mt-2 leading-relaxed">
          Median of {data.peer_count} large-cap {data.sector} peers. Green means favourable —
          below the median for a valuation multiple, above it for a quality metric.
        </p>
      </CardContent>
    </Card>
  );
}
