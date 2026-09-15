"use client";
/**
 * The three pillars as one ledger.
 *
 * Replaces three identical cards with a circular gauge each. The reader's
 * question is comparative (which pillar is carrying this score, how much it
 * counts on this horizon, and how much data stood behind it), and a table
 * answers that in one glance where three cards make you read across.
 *
 * The score bar carries tick marks at 35 and 65, the engine's own SELL and
 * BUY lines, so the verdict is visible as a position, not only as a word.
 */
import type { SignalBreakdownItem } from "@/lib/api";
import { Figure } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export interface PillarRow {
  key: string;
  title: string;
  score: number;
  weight: number;        // 0-1, the horizon weight actually applied
  completeness: number;  // 0-1
  signals: SignalBreakdownItem[];
}

function verdict(score: number) {
  if (score >= 65) return { label: "Constructive", text: "text-aureus-emerald", bar: "bg-aureus-emerald", tone: "up" as const };
  if (score < 35) return { label: "Unfavourable", text: "text-aureus-crimson", bar: "bg-aureus-crimson", tone: "down" as const };
  return { label: "Neutral", text: "text-aureus-gold", bar: "bg-aureus-gold", tone: "flat" as const };
}

const COLS = "md:grid-cols-[9.5rem_minmax(0,1fr)_4.5rem_4.5rem_minmax(0,1.3fr)]";

export default function PillarLedger({ pillars }: { pillars: PillarRow[] }) {
  return (
    <div className="border border-aureus-rule bg-aureus-panel">
      <div className={cn("hidden md:grid gap-6 px-5 py-2.5 border-b border-aureus-rule", COLS)}>
        <span className="label-caps">Pillar</span>
        <span className="label-caps">Score</span>
        <span className="label-caps text-right">Weight</span>
        <span className="label-caps text-right">Data</span>
        <span className="label-caps">Strongest signals</span>
      </div>

      {pillars.map((p, i) => {
        const v = verdict(p.score);
        const drivers = [...p.signals].sort((a, b) => Math.abs(b.score - 50) - Math.abs(a.score - 50)).slice(0, 3);
        return (
          <div key={p.key} className={cn("grid gap-x-6 gap-y-3 px-5 py-4 items-start", COLS, i > 0 && "border-t border-aureus-rule")}>
            <div className="flex md:block items-baseline justify-between">
              <div className="text-[14px] text-aureus-text">{p.title}</div>
              <div className={cn("text-[11.5px] md:mt-0.5", v.text)}>{v.label}</div>
            </div>

            <div className="flex items-center gap-4">
              <Figure className={cn("text-[26px] leading-none w-11", v.text)}>{p.score.toFixed(0)}</Figure>
              <div className="relative flex-1 h-1.5 bg-aureus-panelhigh" aria-hidden>
                <div className={cn("absolute inset-y-0 left-0", v.bar)} style={{ width: `${Math.max(0, Math.min(100, p.score))}%` }} />
                <span className="absolute -top-1 -bottom-1 w-px bg-aureus-rulestrong" style={{ left: "35%" }} />
                <span className="absolute -top-1 -bottom-1 w-px bg-aureus-rulestrong" style={{ left: "65%" }} />
              </div>
            </div>

            <div className="flex md:block justify-between md:text-right">
              <span className="md:hidden label-caps">Weight</span>
              <Figure className="text-[14px]">{(p.weight * 100).toFixed(0)}%</Figure>
            </div>
            <div className="flex md:block justify-between md:text-right">
              <span className="md:hidden label-caps">Data</span>
              <Figure tone={p.completeness < 0.5 ? "down" : "flat"} className="text-[14px]">{(p.completeness * 100).toFixed(0)}%</Figure>
            </div>

            <ul className="space-y-1.5 min-w-0">
              {drivers.length === 0 ? (
                <li className="text-[12px] text-aureus-muted">No sub-signals computed for this pillar.</li>
              ) : drivers.map((s) => (
                <li key={s.label} className="flex items-baseline justify-between gap-3 text-[12px]" title={s.detail}>
                  <span className="truncate text-aureus-soft">{s.label}</span>
                  <Figure tone={s.score >= 65 ? "up" : s.score < 35 ? "down" : "muted"} className="text-[12px] shrink-0">
                    {s.score.toFixed(0)}
                  </Figure>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
