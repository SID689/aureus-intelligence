"use client";
import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ThesisCase, ThesisPoint } from "@/lib/api";

/**
 * Bull or bear case, grouped by category.
 *
 * Direction is carried by the heading alone. Each point is set as a claim,
 * its figure, and the reasoning, with hairlines between points rather than
 * a box per point. The conditions that would change the view are numbered,
 * because they are meant to be checked one at a time.
 */
export default function ThesisCard({ thesis }: { thesis: ThesisCase }) {
  const bull = thesis.stance === "bull";

  const grouped = useMemo(() => {
    const m = new Map<string, ThesisPoint[]>();
    for (const p of thesis.points) {
      if (!m.has(p.category)) m.set(p.category, []);
      m.get(p.category)!.push(p);
    }
    return [...m.entries()];
  }, [thesis.points]);

  return (
    <Card flat>
      <CardContent className="p-5 space-y-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className={cn("font-display text-[22px] leading-none", bull ? "text-aureus-emerald" : "text-aureus-crimson")}>
            {bull ? "Bull case" : "Bear case"}
          </h3>
          {thesis.source === "llm_polished" && <span className="label-caps">Edited by AI</span>}
        </div>

        <p className="text-[13px] text-aureus-muted leading-relaxed">{thesis.summary}</p>

        {grouped.length === 0 ? (
          <p className="text-[13px] text-aureus-muted">No points could be built from the data that computed for this ticker.</p>
        ) : (
          <div className="space-y-5">
            {grouped.map(([category, points]) => (
              <section key={category}>
                <p className="label-caps text-aureus-gold">{category}</p>
                <div className="mt-1">
                  {points.map((p, i) => (
                    <div key={i} className={cn("py-3", i > 0 && "border-t border-aureus-rulesoft")}>
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-[14px] text-aureus-text leading-snug">{p.headline}</p>
                        <span className="shrink-0 border border-aureus-rule px-1.5 py-0.5 font-mono-num text-[10.5px] text-aureus-soft whitespace-nowrap">
                          {p.metric_label} {p.metric_value}
                        </span>
                      </div>
                      <p className="text-[12.5px] text-aureus-soft leading-relaxed mt-1.5">{p.detail}</p>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}

        {thesis.what_would_change_this.length > 0 && (
          <section className="pt-4 border-t border-aureus-rule">
            <p className="label-caps">What would change this view</p>
            <ol className="mt-3 space-y-2">
              {thesis.what_would_change_this.map((f, i) => (
                <li key={i} className="grid grid-cols-[1.5rem_1fr] text-[12.5px] text-aureus-muted leading-relaxed">
                  <span className="font-mono-num text-aureus-golddim">{i + 1}.</span>
                  <span>{f}</span>
                </li>
              ))}
            </ol>
          </section>
        )}
      </CardContent>
    </Card>
  );
}
