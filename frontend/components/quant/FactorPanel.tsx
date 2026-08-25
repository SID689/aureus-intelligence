"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FactorModel } from "@/lib/api";

/**
 * Fama-French factor exposures.
 *
 * The presentation decision that matters here is statistical significance.
 * With five factors and a few hundred observations, some loading always
 * looks non-zero, and a reader will happily build a story on a t-stat of
 * 0.4. So insignificant loadings are visually muted and labelled "not
 * significant" rather than shown identically to real ones — the chart
 * should make it hard to over-read noise, not easy.
 */

export default function FactorPanel({ model }: { model: FactorModel | null }) {
  if (!model) {
    return (
      <Card>
        <CardHeader><CardTitle>Factor Exposures</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-aureus-muted">
            Fama-French factor data was unavailable, or the price history doesn&apos;t overlap it
            enough to estimate exposures.
          </p>
        </CardContent>
      </Card>
    );
  }

  const maxAbs = Math.max(1, ...model.loadings.map((l) => Math.abs(l.loading)));

  return (
    <Card>
      <CardHeader><CardTitle>{model.model}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
            <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Annualised Alpha</div>
            <div className={`text-lg font-semibold font-mono mt-0.5 ${
              model.alpha_annualised >= 0 ? "text-aureus-verdigris" : "text-aureus-oxblood"}`}>
              {(model.alpha_annualised * 100).toFixed(2)}%
            </div>
            <div className="text-[10px] text-aureus-muted mt-0.5">
              t = {model.alpha_t_stat.toFixed(2)}{" "}
              {model.alpha_significant
                ? <span className="text-aureus-gold">significant</span>
                : <span>not significant</span>}
            </div>
          </div>
          <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
            <div className="text-[10px] uppercase tracking-wider text-aureus-muted">R²</div>
            <div className="text-lg font-semibold text-aureus-text font-mono mt-0.5">
              {(model.r_squared * 100).toFixed(1)}%
            </div>
            <div className="text-[10px] text-aureus-muted mt-0.5">of variance explained</div>
          </div>
          <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
            <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Sample</div>
            <div className="text-lg font-semibold text-aureus-text font-mono mt-0.5">{model.observations}</div>
            <div className="text-[10px] text-aureus-muted mt-0.5">{model.start} → {model.end}</div>
          </div>
        </div>

        <div className="space-y-2.5">
          {model.loadings.map((l) => {
            const pct = (Math.abs(l.loading) / maxAbs) * 50;
            const pos = l.loading >= 0;
            return (
              <div key={l.factor}>
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <span className={`text-xs ${l.significant ? "text-aureus-text" : "text-aureus-muted/60"}`}>
                    {l.label}
                  </span>
                  <span className={`text-xs font-mono ${
                    l.significant ? (pos ? "text-aureus-verdigris" : "text-aureus-oxblood") : "text-aureus-muted/60"}`}>
                    {pos ? "+" : ""}{l.loading.toFixed(3)}
                    <span className="text-aureus-muted ml-1.5">t={l.t_stat.toFixed(1)}</span>
                  </span>
                </div>
                {/* Centre-anchored bar: left of centre is negative exposure. */}
                <div className="relative h-2 rounded-full bg-aureus-rule overflow-hidden">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-aureus-muted/40 z-10" />
                  <div
                    className="absolute inset-y-0 rounded-full"
                    style={{
                      left: pos ? "50%" : `${50 - pct}%`,
                      width: `${pct}%`,
                      background: pos ? "var(--verdigris)" : "var(--oxblood)",
                      opacity: l.significant ? 1 : 0.3,
                    }}
                  />
                </div>
                <p className={`text-[10px] mt-0.5 ${
                  l.significant ? "text-aureus-muted" : "text-aureus-muted/50 italic"}`}>
                  {l.significant ? l.meaning : "Not statistically distinguishable from zero — do not read a tilt into this."}
                </p>
              </div>
            );
          })}
        </div>

        <p className="text-[10px] text-aureus-muted leading-relaxed pt-2 border-t border-aureus-rule">
          Alpha here is the return left over after every factor above is accounted for — a much
          higher bar than &ldquo;beat the S&amp;P&rdquo;, which credits a stock for simply carrying a
          size or value tilt. An alpha that is not statistically significant is indistinguishable
          from luck over this sample.
        </p>
      </CardContent>
    </Card>
  );
}
