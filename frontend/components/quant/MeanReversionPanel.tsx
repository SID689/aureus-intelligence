"use client";
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { QuantLabReport } from "@/lib/api";

/**
 * Mean-reversion statistics: z-score, half-life, volatility regime, pairs.
 *
 * The half-life is presented adjacent to the z-score on purpose. A z-score
 * is the seductive half of this analysis — it always produces a number,
 * and a large one always looks tradeable. The half-life is the half that
 * says whether the series mean-reverts at all. Showing the z-score without
 * it would invite trading a displacement in a series that simply trends.
 */

export default function MeanReversionPanel({ report }: { report: QuantLabReport }) {
  const z = report.zscore;
  const hl = report.half_life;
  const vts = report.volatility_term_structure;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Mean Reversion</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {z ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
                  <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Z-Score</div>
                  <div className={`text-lg font-semibold font-mono mt-0.5 ${
                    Math.abs(z.z_score) >= 2 ? "text-aureus-gold" : "text-aureus-text"}`}>
                    {z.z_score >= 0 ? "+" : ""}{z.z_score.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-aureus-muted mt-0.5">{z.window_days}-day window</div>
                </div>
                <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
                  <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Percentile</div>
                  <div className="text-lg font-semibold text-aureus-text font-mono mt-0.5">
                    {z.percentile_in_window.toFixed(0)}
                  </div>
                  <div className="text-[10px] text-aureus-muted mt-0.5">within its window</div>
                </div>
                <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
                  <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Rolling Mean</div>
                  <div className="text-lg font-semibold text-aureus-text font-mono mt-0.5">
                    ${z.rolling_mean.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-aureus-muted mt-0.5">vs ${z.current_price.toFixed(2)} now</div>
                </div>
                <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
                  <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Half-Life</div>
                  <div className={`text-lg font-semibold font-mono mt-0.5 ${
                    hl?.reverting ? "text-aureus-verdigris" : "text-aureus-muted"}`}>
                    {hl?.half_life_days != null ? `${hl.half_life_days}d` : "None"}
                  </div>
                  <div className="text-[10px] text-aureus-muted mt-0.5">
                    {hl?.reverting ? "mean-reverting" : "trending / random walk"}
                  </div>
                </div>
              </div>

              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={z.series} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
                    <defs>
                      <linearGradient id="zfill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--gold)" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="var(--gold)" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--rule)" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--text-muted)" }} minTickGap={40} />
                    {/* Explicit ticks: Recharts' auto-ticking on this domain
                        produces an unevenly spaced set (-3.5, -1.5, 0.5, 3.5),
                        which misreads as a broken scale and leaves the ±2
                        threshold lines sitting between labels. */}
                    <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} domain={[-3.5, 3.5]}
                           ticks={[-3, -2, -1, 0, 1, 2, 3]} />
                    <Tooltip contentStyle={{ background: "var(--panel-lift)", border: "1px solid var(--rule)", borderRadius: 6, fontSize: 11 }} />
                    <ReferenceLine y={2} stroke="var(--oxblood)" strokeDasharray="4 4" />
                    <ReferenceLine y={0} stroke="var(--text-muted)" />
                    <ReferenceLine y={-2} stroke="var(--verdigris)" strokeDasharray="4 4" />
                    <Area type="monotone" dataKey="z" stroke="var(--gold)" strokeWidth={1.75} fill="url(#zfill)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <p className="text-[11px] text-aureus-text leading-relaxed">{z.interpretation}</p>
              {hl && <p className="text-[10px] text-aureus-muted leading-relaxed">{hl.note}</p>}
            </>
          ) : (
            <p className="text-sm text-aureus-muted">
              Not enough price history to compute a z-score for this ticker.
            </p>
          )}
        </CardContent>
      </Card>

      {vts && Object.keys(vts.windows).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Volatility Term Structure</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {Object.entries(vts.windows).map(([w, v]) => (
                <div key={w} className="rounded-lg border border-aureus-rule px-3 py-2 flex-1 min-w-[74px]"
                     style={{ background: "var(--bg)" }}>
                  <div className="text-[10px] uppercase text-aureus-muted">{w}</div>
                  <div className="text-sm font-mono text-aureus-text">{(v * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>
            {vts.regime && (
              <div className="flex items-start gap-2">
                <span className={`rounded px-2 py-0.5 text-[10px] font-bold tracking-wider flex-shrink-0 ${
                  vts.regime === "Elevated" ? "bg-aureus-oxblood/10 text-aureus-oxblood"
                  : vts.regime === "Compressed" ? "bg-aureus-verdigris/10 text-aureus-verdigris"
                  : "bg-aureus-rule/40 text-aureus-gold"}`}>
                  {vts.regime.toUpperCase()}
                </span>
                <p className="text-[11px] text-aureus-muted leading-relaxed">{vts.note}</p>
              </div>
            )}
            <p className="text-[10px] text-aureus-muted leading-relaxed pt-2 border-t border-aureus-rule">
              This is <em>realised</em> volatility across lookbacks, not implied volatility skew across
              option strikes — no free data source provides an options chain, so the realised term
              structure is shown instead of a number that would be labelled skew without being it.
            </p>
          </CardContent>
        </Card>
      )}

      {report.pairs.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Pairs &amp; Correlation</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-aureus-muted border-b border-aureus-rule">
                    <th className="text-left py-2 font-normal">Ticker</th>
                    <th className="text-right py-2 font-normal">Return Correlation</th>
                    <th className="text-right py-2 font-normal">Spread Z</th>
                    <th className="text-right py-2 font-normal">Obs</th>
                  </tr>
                </thead>
                <tbody>
                  {report.pairs.map((p) => (
                    <tr key={p.ticker} className="border-b border-aureus-rule/50">
                      <td className="py-2 text-aureus-text font-medium">{p.ticker}</td>
                      <td className="py-2 text-right font-mono text-aureus-text">
                        {p.return_correlation.toFixed(3)}
                      </td>
                      <td className={`py-2 text-right font-mono ${
                        p.spread_z_score != null && Math.abs(p.spread_z_score) >= 2
                          ? "text-aureus-gold" : "text-aureus-muted"}`}>
                        {p.spread_z_score != null
                          ? `${p.spread_z_score >= 0 ? "+" : ""}${p.spread_z_score.toFixed(2)}`
                          : "—"}
                      </td>
                      <td className="py-2 text-right font-mono text-aureus-muted">{p.observations}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[10px] text-aureus-muted mt-3 leading-relaxed">
              Correlation is computed on daily <strong>returns</strong>, never on prices. Two trending
              price series correlate near 1.0 almost regardless of any real relationship — the classic
              spurious regression — which would rank every large-cap as a perfect pair. Spread Z is the
              log price ratio versus its own 60-day mean.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
