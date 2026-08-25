"use client";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BetaStability, MonteCarloResult, QuantLabReport, VarResult } from "@/lib/api";

/**
 * Distributional risk: Monte Carlo, VaR/CVaR, beta stability, drawdown.
 *
 * VaR and CVaR are always shown as a PAIR. VaR alone is the single most
 * over-trusted number in retail risk tooling — it states a threshold and
 * says nothing about the severity beyond it, so two positions with
 * identical VaR can have completely different tails. Showing expected
 * shortfall beside it is what makes the pair honest.
 */

const pct = (v: number | null | undefined, d = 2) =>
  v == null ? "—" : `${(v * 100).toFixed(d)}%`;

function Stat({ label, value, hint, tone }: {
  label: string; value: string; hint?: string; tone?: "good" | "bad" | "neutral";
}) {
  const color = tone === "good" ? "text-aureus-verdigris"
              : tone === "bad" ? "text-aureus-oxblood" : "text-aureus-text";
  return (
    <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
      <div className="text-[10px] uppercase tracking-wider text-aureus-muted">{label}</div>
      <div className={`text-base font-semibold font-mono mt-0.5 ${color}`}>{value}</div>
      {hint && <div className="text-[10px] text-aureus-muted mt-0.5">{hint}</div>}
    </div>
  );
}

function VarBlock({ v, label }: { v: VarResult | null; label: string }) {
  if (!v || v.var_pct == null) {
    return <Stat label={label} value="—" hint="Insufficient history" />;
  }
  return (
    <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
      <div className="text-[10px] uppercase tracking-wider text-aureus-muted">{label}</div>
      <div className="text-base font-semibold font-mono mt-0.5 text-aureus-oxblood">
        −{pct(v.var_pct)}
      </div>
      <div className="text-[10px] text-aureus-muted mt-0.5">
        Expected shortfall −{pct(v.cvar_pct)}
      </div>
      <div className="text-[10px] text-aureus-muted/70">
        {(v.confidence * 100).toFixed(0)}% confidence · n={v.observations}
      </div>
    </div>
  );
}

function MonteCarloChart({ mc }: { mc: MonteCarloResult }) {
  const data = mc.histogram.map((h) => ({
    mid: h.mid * 100,
    count: h.count,
    fill: h.mid < 0 ? "var(--oxblood-dim)" : "var(--verdigris-dim)",
  }));
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
        <span className="text-xs text-aureus-muted">
          {mc.paths.toLocaleString()} simulated {mc.horizon_days}-day paths
        </span>
        <span className="text-[10px] text-aureus-muted font-mono">
          P(loss) {(mc.probability_of_loss * 100).toFixed(1)}%
        </span>
      </div>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--rule)" vertical={false} />
            <XAxis dataKey="mid" tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                   tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
            <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
            <Tooltip
              contentStyle={{ background: "var(--panel-lift)", border: "1px solid var(--rule)", borderRadius: 6, fontSize: 11 }}
              labelFormatter={(v) => `Return ${Number(v).toFixed(1)}%`}
              formatter={(v: number) => [`${v} paths`, "Frequency"]}
            />
            <ReferenceLine x={0} stroke="var(--text-muted)" strokeDasharray="3 3" />
            <Bar dataKey="count" fill="var(--gold)" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-5 gap-1.5 mt-2">
        {(["p5", "p25", "p50", "p75", "p95"] as const).map((k) => (
          <div key={k} className="text-center rounded border border-aureus-rule py-1.5"
               style={{ background: "var(--bg)" }}>
            <div className="text-[9px] uppercase text-aureus-muted">{k}</div>
            <div className={`text-[11px] font-mono ${
              mc.percentiles[k] >= 0 ? "text-aureus-verdigris" : "text-aureus-oxblood"}`}>
              {(mc.percentiles[k] * 100).toFixed(1)}%
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-aureus-muted mt-2 leading-relaxed">
        {mc.method}. Historical returns are resampled rather than drawn from a normal
        distribution — equity returns are fat-tailed, and a Gaussian simulation understates
        precisely the tail this chart exists to show.
      </p>
    </div>
  );
}

function BetaChart({ b }: { b: BetaStability }) {
  return (
    <div>
      <div className="grid grid-cols-4 gap-2 mb-3">
        <Stat label="Full-sample β" value={b.full_sample_beta?.toFixed(2) ?? "—"} />
        <Stat label="Rolling range" value={`${b.rolling_min.toFixed(2)}–${b.rolling_max.toFixed(2)}`} />
        <Stat label="Rolling σ" value={b.rolling_std.toFixed(3)} />
        <Stat
          label="Instability"
          value={b.instability?.toFixed(2) ?? "—"}
          tone={b.instability != null && b.instability > 0.25 ? "bad" : "good"}
          hint={b.instability != null && b.instability > 0.25 ? "Unstable" : "Stable"}
        />
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={b.series} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--rule)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--text-muted)" }} minTickGap={40} />
            <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} domain={["auto", "auto"]} />
            <Tooltip contentStyle={{ background: "var(--panel-lift)", border: "1px solid var(--rule)", borderRadius: 6, fontSize: 11 }} />
            {b.full_sample_beta != null && (
              <ReferenceLine y={b.full_sample_beta} stroke="var(--gold)" strokeDasharray="4 4" />
            )}
            <Line type="monotone" dataKey="beta" stroke="var(--verdigris)" strokeWidth={1.75} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[10px] text-aureus-muted mt-2 leading-relaxed">
        The gold line is the full-sample beta. Where the rolling estimate ranges widely around it,
        that single number describes no actual period — and any hedge ratio derived from it will be
        wrong most of the time.
      </p>
    </div>
  );
}

export default function RiskPanel({ report }: { report: QuantLabReport }) {
  const p = report.performance;
  const dd = report.max_drawdown;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Risk &amp; Performance</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Sharpe (ann.)" value={p?.sharpe_ratio?.toFixed(2) ?? "—"}
                  tone={p?.sharpe_ratio != null && p.sharpe_ratio >= 1 ? "good" : "neutral"}
                  hint="Return per unit of total volatility" />
            <Stat label="Sortino (ann.)" value={p?.sortino_ratio?.toFixed(2) ?? "—"}
                  tone={p?.sortino_ratio != null && p.sortino_ratio >= 1 ? "good" : "neutral"}
                  hint="Penalises downside only" />
            <Stat label="Annualised Return" value={pct(p?.annualised_return, 1)}
                  tone={(p?.annualised_return ?? 0) >= 0 ? "good" : "bad"} />
            <Stat label="Annualised Volatility" value={pct(p?.annualised_volatility, 1)} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <VarBlock v={report.var_1d} label="1-Day VaR" />
            <VarBlock v={report.var_10d} label="10-Day VaR" />
            <Stat label="Max Drawdown" value={pct(dd?.max_drawdown_pct, 1)} tone="bad"
                  hint={dd?.peak_date ? `${dd.peak_date} → ${dd.trough_date}` : undefined} />
            <Stat label="Drawdown Recovery"
                  value={dd?.recovered ? "Recovered" : "Not recovered"}
                  tone={dd?.recovered ? "good" : "bad"}
                  hint={dd?.recovery_date ?? "Still below the prior peak"} />
          </div>
          {/* Phrased against the ticker's OWN figure rather than a fixed
              example — a hardcoded "a VaR of 2.7% means…" sitting beside a
              displayed 4.17% reads as if it is describing that number. */}
          <p className="text-[10px] text-aureus-muted leading-relaxed">
            VaR is a threshold, not a worst case
            {report.var_1d?.var_pct != null && (
              <>
                : a 1-day VaR of {pct(report.var_1d.var_pct)} means a loss larger than that is
                expected roughly one day in twenty
              </>
            )}
            . Expected shortfall (CVaR) is the average loss on those days, which is the number that
            describes what the tail actually costs
            {report.var_1d?.worst_observed_pct != null && (
              <> — the worst single day in this sample was {pct(report.var_1d.worst_observed_pct)}</>
            )}
            .
          </p>
        </CardContent>
      </Card>

      {report.monte_carlo && (
        <Card>
          <CardHeader><CardTitle>Monte Carlo Return Distribution</CardTitle></CardHeader>
          <CardContent><MonteCarloChart mc={report.monte_carlo} /></CardContent>
        </Card>
      )}

      {report.beta_stability && (
        <Card>
          <CardHeader>
            <CardTitle>Beta Stability vs {report.benchmark}</CardTitle>
          </CardHeader>
          <CardContent><BetaChart b={report.beta_stability} /></CardContent>
        </Card>
      )}
    </div>
  );
}
