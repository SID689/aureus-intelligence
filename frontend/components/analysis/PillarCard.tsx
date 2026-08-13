"use client";
import { Card, CardContent } from "@/components/ui/card";
import type { SignalBreakdownItem } from "@/lib/api";

/**
 * One pillar (Fundamental / Technical / Quantitative) with a circular gauge,
 * its weight in the composite, and the sub-signals actually driving it.
 *
 * The gauge is an SVG arc rather than a chart library: it's a single value,
 * so pulling in a charting dependency to draw one circle would be pure
 * overhead. `strokeDasharray` on a circle gives an exact arc for free.
 */

interface Props {
  title: string;
  score: number;
  weight: number;            // 0–1, the horizon-adjusted weight
  completeness: number;      // 0–1
  signals: SignalBreakdownItem[];
}

function toneFor(score: number): { stroke: string; text: string } {
  if (score >= 65) return { stroke: "#22c55e", text: "text-aureus-green" };
  if (score < 35) return { stroke: "#ef4444", text: "text-aureus-red" };
  return { stroke: "#d4a843", text: "text-aureus-gold" };
}

function Gauge({ score }: { score: number }) {
  const r = 34;
  const circumference = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const tone = toneFor(score);
  return (
    <div className="relative w-[86px] h-[86px] flex-shrink-0">
      <svg width="86" height="86" viewBox="0 0 86 86" className="-rotate-90">
        <circle cx="43" cy="43" r={r} fill="none" stroke="#2a2a3a" strokeWidth="7" />
        <circle
          cx="43" cy="43" r={r} fill="none" stroke={tone.stroke} strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${circumference * pct} ${circumference}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-xl font-semibold ${tone.text}`}>{score.toFixed(0)}</span>
        <span className="text-[9px] text-aureus-muted uppercase tracking-wide">/ 100</span>
      </div>
    </div>
  );
}

export default function PillarCard({ title, score, weight, completeness, signals }: Props) {
  const tone = toneFor(score);
  // Show the extremes — the signals actually pushing the score around.
  const ranked = [...signals].sort((a, b) => Math.abs(b.score - 50) - Math.abs(a.score - 50)).slice(0, 4);

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-3">
          <Gauge score={score} />
          <div className="min-w-0 flex-1">
            <h3 className="text-xs uppercase tracking-wider text-aureus-muted">{title}</h3>
            <p className={`text-sm font-semibold mt-0.5 ${tone.text}`}>
              {score >= 65 ? "Constructive" : score < 35 ? "Unfavourable" : "Neutral"}
            </p>
            <div className="mt-2 space-y-1 text-[11px] text-aureus-muted">
              <div className="flex justify-between gap-2">
                <span>Weight this horizon</span>
                <span className="text-white font-mono">{(weight * 100).toFixed(0)}%</span>
              </div>
              <div className="flex justify-between gap-2">
                <span>Data completeness</span>
                <span className={completeness < 0.5 ? "text-aureus-red font-mono" : "text-white font-mono"}>
                  {(completeness * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-1.5 pt-2 border-t border-aureus-rule">
          {ranked.length === 0 ? (
            <p className="text-[11px] text-aureus-muted">No sub-signals computed for this pillar.</p>
          ) : ranked.map((s) => (
            <div key={s.label} className="flex items-center gap-2 text-[11px]">
              <span className="flex-1 truncate text-aureus-text" title={s.detail}>{s.label}</span>
              <div className="w-16 h-1 rounded-full bg-aureus-rule overflow-hidden">
                <div className="h-full rounded-full"
                     style={{ width: `${Math.max(0, Math.min(100, s.score))}%`,
                              background: toneFor(s.score).stroke }} />
              </div>
              <span className="w-6 text-right font-mono text-aureus-muted">{s.score.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
