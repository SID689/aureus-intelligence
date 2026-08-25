"use client";
import { useMemo } from "react";
import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { ThesisCase, ThesisPoint } from "@/lib/api";

/**
 * Bull or bear case, grouped by thematic category.
 *
 * Grouping happens here rather than server-side because the server returns
 * points already ordered by horizon priority — regrouping in the UI keeps
 * that order while letting the same payload render as a flat list elsewhere
 * (the dashboard summary) without a second API shape.
 */

interface Props {
  thesis: ThesisCase;
}

export default function ThesisCard({ thesis }: Props) {
  const bull = thesis.stance === "bull";

  const grouped = useMemo(() => {
    const m = new Map<string, ThesisPoint[]>();
    for (const p of thesis.points) {
      if (!m.has(p.category)) m.set(p.category, []);
      m.get(p.category)!.push(p);
    }
    return [...m.entries()];
  }, [thesis.points]);

  const accent = bull ? "border-l-aureus-green" : "border-l-aureus-red";
  const tone = bull ? "text-aureus-verdigris" : "text-aureus-oxblood";
  const badgeBg = bull ? "bg-aureus-verdigris/10 text-aureus-verdigris" : "bg-aureus-oxblood/10 text-aureus-oxblood";

  return (
    <Card className={`border-l-2 ${accent}`}>
      <CardContent className="p-4 space-y-4">
        <div className="flex items-center gap-2">
          {bull ? <TrendingUp className={`w-4 h-4 ${tone}`} />
                : <TrendingDown className={`w-4 h-4 ${tone}`} />}
          <h3 className={`font-semibold text-sm ${tone}`}>
            {bull ? "Bull Case" : "Bear Case"}
          </h3>
          {thesis.source === "llm_polished" && (
            <span className="text-[9px] uppercase tracking-wider text-aureus-muted ml-auto">
              LLM-polished
            </span>
          )}
        </div>

        <p className="text-xs text-aureus-muted leading-relaxed">{thesis.summary}</p>

        {grouped.length === 0 ? (
          <p className="text-xs text-aureus-muted italic">
            No points could be constructed from the data that computed for this ticker.
          </p>
        ) : (
          <div className="space-y-4">
            {grouped.map(([category, points]) => (
              <section key={category} className="space-y-2">
                <h4 className="text-[10px] font-semibold uppercase tracking-wider text-aureus-gold">
                  {category}
                </h4>
                {points.map((p, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-aureus-text font-medium leading-snug">{p.headline}</p>
                      <span className={`flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-mono ${badgeBg}`}>
                        {p.metric_label} {p.metric_value}
                      </span>
                    </div>
                    <p className="text-xs text-aureus-text leading-relaxed">{p.detail}</p>
                  </div>
                ))}
              </section>
            ))}
          </div>
        )}

        {thesis.what_would_change_this.length > 0 && (
          <section className="rounded-md border border-aureus-rule px-3 py-2.5 space-y-1"
                   style={{ background: "var(--bg)" }}>
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3 text-aureus-muted" />
              <h4 className="text-[10px] font-semibold uppercase tracking-wider text-aureus-muted">
                What would change this view
              </h4>
            </div>
            <ul className="space-y-1">
              {thesis.what_would_change_this.map((f, i) => (
                <li key={i} className="text-xs text-aureus-muted leading-relaxed">— {f}</li>
              ))}
            </ul>
          </section>
        )}
      </CardContent>
    </Card>
  );
}
