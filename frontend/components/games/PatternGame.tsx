"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { LoadingRegion, Skeleton, SkeletonChart } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { newPatternScenario, submitPatternGuess } from "@/lib/api";
import type { PatternResult, PatternScenario } from "@/lib/api";

/**
 * Chart Pattern & Candlestick Scenario Guesser — one chart per day.
 *
 * Handles three question types from the same payload:
 *   direction           — predict how it resolved
 *   pattern_id          — name the formation
 *   pattern_implication — state what that formation conventionally signals
 *
 * The component doesn't branch on type for anything except copy: the server
 * sends the question text and its choices, and grades the answer. That keeps
 * the answer key server-side and means adding a fourth question type later
 * needs no frontend change at all.
 */

interface Props {
  userId: string;
  onRoundComplete: () => void;
}

const BIAS_TONE: Record<string, string> = {
  bullish_reversal: "text-aureus-emerald",
  bullish_continuation: "text-aureus-emerald",
  bearish_reversal: "text-aureus-crimson",
  bearish_continuation: "text-aureus-crimson",
  bilateral: "text-aureus-gold",
};

export default function PatternGame({ userId, onRoundComplete }: Props) {
  const [scenario, setScenario] = useState<PatternScenario | null>(null);
  const [result, setResult] = useState<PatternResult | null>(null);
  const [choice, setChoice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setChoice(null);
    try {
      const s = await newPatternScenario(userId);
      setScenario(s);
      // An already-answered chart returns its result inline, so a refresh
      // reopens the reveal instead of appearing to offer a second attempt.
      setResult(s.result ?? null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load today's chart");
      setScenario(null);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { if (userId) load(); }, [userId, load]);

  const handleAnswer = async () => {
    if (!scenario || !choice) return;
    setSubmitting(true);
    try {
      setResult(await submitPatternGuess(userId, scenario.scenario_id, choice));
      onRoundComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not submit your answer");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingRegion label="Loading today’s chart" className="space-y-4"><SkeletonChart height={300} /><Skeleton className="h-10 w-full" delay={120} /></LoadingRegion>;
  if (error && !scenario) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="text-aureus-crimson text-sm">{error}</p>
        <Button variant="outline" size="sm" onClick={load}>Try Again</Button>
      </div>
    );
  }
  if (!scenario) return null;

  const setupLen = scenario.setup_bars.length;
  const data = [
    ...scenario.setup_bars.map((b, i) => ({ i, date: b.date, setup: b.close, outcome: undefined as number | undefined })),
    ...(result
      ? result.outcome_bars.map((b, i) => ({
          i: setupLen + i, date: b.date, setup: undefined as number | undefined, outcome: b.close,
        }))
      : []),
  ];
  if (result && data[setupLen - 1]) {
    (data[setupLen - 1] as { outcome?: number }).outcome = scenario.setup_bars[setupLen - 1].close;
  }

  const pattern = result?.pattern;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex-1 min-w-[240px]">
          <h3 className="text-aureus-text font-semibold">{scenario.question}</h3>
          <p className="text-xs text-aureus-muted mt-0.5">
            Real historical price action, ticker hidden · one chart per day
          </p>
        </div>
        {result && <Badge variant="muted">{result.ticker}</Badge>}
      </div>

      {/* For implication questions the formation is named in the prompt, so
          describing its shape here gives away nothing extra. */}
      {scenario.named_pattern && !result && (
        <div className="rounded-sm border border-aureus-gold/30 bg-aureus-gold/[0.05] px-3 py-2.5">
          <p className="text-xs text-aureus-gold uppercase tracking-wider mb-1">
            {scenario.named_pattern.name}
          </p>
          <p className="text-sm text-aureus-text leading-relaxed">{scenario.named_pattern.shape}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {scenario.setup_notes.map((n, i) => (
          <span key={i} className="text-xs text-aureus-muted rounded-md border border-aureus-rule px-2 py-1">
            {n}
          </span>
        ))}
      </div>

      <div className="rounded-sm border border-aureus-rule p-3" style={{ background: "var(--panel)" }}>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--grid-line)" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "var(--text-muted)", fontSize: 10 }} tickLine={false} axisLine={false}
                   interval={Math.max(1, Math.floor(data.length / 6))} />
            <YAxis orientation="right" domain={["auto", "auto"]} tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                   tickLine={false} axisLine={false} width={52}
                   tickFormatter={(v) => `$${Number(v).toFixed(0)}`} />
            <Tooltip
              contentStyle={{ background: "var(--ink)", border: "1px solid var(--rule)", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "var(--text-muted)" }}
              // Left unannotated on purpose: recharts types a formatter's
              // value as ValueType (string | number | array), so declaring
              // the parameter as `number` makes the overload unassignable.
              formatter={(v) => (v == null ? "—" : `$${Number(v).toFixed(2)}`)}
            />
            <Line type="monotone" dataKey="setup" stroke="var(--gold)" strokeWidth={1.8} dot={false} connectNulls={false} />
            {result && (
              <Line type="monotone" dataKey="outcome" strokeWidth={2} dot={false} connectNulls={false}
                    stroke={result.correct_direction === "bullish_breakout" ? "var(--emerald)"
                          : result.correct_direction === "bearish_breakdown" ? "var(--crimson)" : "var(--text-muted)"} />
            )}
            {result && (
              <ReferenceLine x={data[setupLen - 1]?.date} stroke="var(--text-muted)" strokeDasharray="4 3"
                             label={{ value: "decision", fill: "var(--text-muted)", fontSize: 10, position: "top" }} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {!result ? (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {scenario.choices.map((c) => (
              <button
                key={c.value}
                onClick={() => setChoice(c.value)}
                className={`rounded-sm border px-3 py-2.5 text-sm text-left transition-colors ${
                  choice === c.value
                    ? "border-aureus-gold bg-aureus-gold/10 text-aureus-gold"
                    : "border-aureus-rule text-aureus-text hover:border-aureus-muted"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          <Button className="w-full" disabled={!choice || submitting} onClick={handleAnswer}>
            {submitting ? "Checking" : choice ? "Lock In Answer" : "Pick an answer"}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className={`rounded-sm border p-4 space-y-2 ${
            result.correct ? "border-aureus-emeralddim bg-aureus-emerald/10" : "border-aureus-crimsondim bg-aureus-crimson/10"
          }`}>
            <p className={`font-semibold ${result.correct ? "text-aureus-emerald" : "text-aureus-crimson"}`}>
              {result.correct ? "Correct" : "Not this time"}
              {!result.correct && (
                <span className="text-aureus-muted font-normal">
                  {": the answer was "}
                  {scenario.choices.find((c) => c.value === result.correct_answer)?.label ?? result.correct_answer}
                </span>
              )}
            </p>
            <p className="text-sm text-aureus-text leading-relaxed">{result.rationale}</p>
            <p className="text-xs text-aureus-muted">
              {result.ticker} · resolved {result.correct_direction_label} · +{result.score_awarded} knowledge XP
            </p>
          </div>

          {/* Pattern deep-dive — the teaching payload */}
          {pattern && (
            <div className="rounded-sm border border-aureus-rule p-4 space-y-3" style={{ background: "var(--panel)" }}>
              <div className="flex items-center gap-2">
                <h4 className="text-aureus-text font-semibold text-sm">{pattern.name}</h4>
                <Badge variant="muted" className={BIAS_TONE[pattern.bias] ?? ""}>
                  {pattern.bias.replace(/_/g, " ")}
                </Badge>
              </div>

              {pattern.detected_detail && (
                <p className="text-xs text-aureus-muted font-mono leading-relaxed">
                  Detected: {pattern.detected_detail}
                </p>
              )}

              {[
                ["What it looks like", pattern.shape],
                ["What it's read as", pattern.implication],
                ["What confirms it", pattern.confirmation],
              ].map(([label, body]) => (
                <section key={label}>
                  <h5 className="text-[10px] uppercase tracking-wider text-aureus-muted mb-0.5">{label}</h5>
                  <p className="text-sm text-aureus-text leading-relaxed">{body}</p>
                </section>
              ))}

              <section className="rounded-sm border border-aureus-crimsondim bg-aureus-crimson/10 px-3 py-2">
                <h5 className="text-[10px] uppercase tracking-wider text-aureus-crimson mb-0.5">Why it isn&apos;t a guarantee</h5>
                <p className="text-sm text-aureus-text leading-relaxed">{pattern.caveat}</p>
              </section>
            </div>
          )}

          <div className="rounded-sm border border-aureus-rule px-4 py-3 text-center"
               style={{ background: "var(--ink)" }}>
            <p className="text-sm text-aureus-muted">
              That&apos;s today&apos;s chart. A new one unlocks tomorrow.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
