"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { BookOpen } from "lucide-react";
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
  bullish_reversal: "text-aureus-green",
  bullish_continuation: "text-aureus-green",
  bearish_reversal: "text-aureus-red",
  bearish_continuation: "text-aureus-red",
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

  if (loading) return <div className="py-16 text-center text-aureus-muted text-sm">Loading today&apos;s chart…</div>;
  if (error && !scenario) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="text-aureus-red text-sm">{error}</p>
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
          <h3 className="text-white font-semibold">{scenario.question}</h3>
          <p className="text-xs text-aureus-muted mt-0.5">
            Real historical price action, ticker hidden · one chart per day
          </p>
        </div>
        {result && <Badge variant="muted">{result.ticker}</Badge>}
      </div>

      {/* For implication questions the formation is named in the prompt, so
          describing its shape here gives away nothing extra. */}
      {scenario.named_pattern && !result && (
        <div className="rounded-lg border-l-2 border-aureus-gold bg-aureus-gold/[0.05] px-3 py-2.5">
          <p className="text-xs text-aureus-gold uppercase tracking-wider mb-1">
            {scenario.named_pattern.name}
          </p>
          <p className="text-sm text-aureus-text leading-relaxed">{scenario.named_pattern.shape}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {scenario.setup_notes.map((n, i) => (
          <span key={i} className="text-xs text-aureus-muted rounded-md border border-aureus-border px-2 py-1">
            {n}
          </span>
        ))}
      </div>

      <div className="rounded-lg border border-aureus-border p-3" style={{ background: "var(--surface)" }}>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} axisLine={false}
                   interval={Math.max(1, Math.floor(data.length / 6))} />
            <YAxis orientation="right" domain={["auto", "auto"]} tick={{ fill: "#6b7280", fontSize: 10 }}
                   tickLine={false} axisLine={false} width={52}
                   tickFormatter={(v) => `$${Number(v).toFixed(0)}`} />
            <Tooltip
              contentStyle={{ background: "var(--bg)", border: "1px solid #2a2a3a", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#6b7280" }}
              formatter={(v: number | undefined) => (v == null ? "—" : `$${Number(v).toFixed(2)}`)}
            />
            <Line type="monotone" dataKey="setup" stroke="#d4a843" strokeWidth={1.8} dot={false} connectNulls={false} />
            {result && (
              <Line type="monotone" dataKey="outcome" strokeWidth={2} dot={false} connectNulls={false}
                    stroke={result.correct_direction === "bullish_breakout" ? "#22c55e"
                          : result.correct_direction === "bearish_breakdown" ? "#ef4444" : "#6b7280"} />
            )}
            {result && (
              <ReferenceLine x={data[setupLen - 1]?.date} stroke="#6b7280" strokeDasharray="4 3"
                             label={{ value: "decision", fill: "#6b7280", fontSize: 10, position: "top" }} />
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
                className={`rounded-lg border px-3 py-2.5 text-sm text-left transition-colors ${
                  choice === c.value
                    ? "border-aureus-gold bg-aureus-gold/10 text-aureus-gold"
                    : "border-aureus-border text-aureus-text hover:border-aureus-muted"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          <Button className="w-full" disabled={!choice || submitting} onClick={handleAnswer}>
            {submitting ? "Checking…" : choice ? "Lock In Answer" : "Pick an answer"}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className={`rounded-lg border p-4 space-y-2 ${
            result.correct ? "border-aureus-green bg-green-950/20" : "border-aureus-red bg-red-950/20"
          }`}>
            <p className={`font-semibold ${result.correct ? "text-aureus-green" : "text-aureus-red"}`}>
              {result.correct ? "Correct" : "Not this time"}
              {!result.correct && (
                <span className="text-aureus-muted font-normal">
                  {" — the answer was "}
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
            <div className="rounded-lg border border-aureus-border p-4 space-y-3" style={{ background: "var(--surface)" }}>
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-aureus-gold" />
                <h4 className="text-white font-semibold text-sm">{pattern.name}</h4>
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

              <section className="rounded-md border-l-2 border-aureus-red bg-red-950/15 px-3 py-2">
                <h5 className="text-[10px] uppercase tracking-wider text-aureus-red mb-0.5">Why it isn&apos;t a guarantee</h5>
                <p className="text-sm text-aureus-text leading-relaxed">{pattern.caveat}</p>
              </section>
            </div>
          )}

          <div className="rounded-lg border border-aureus-border px-4 py-3 text-center"
               style={{ background: "var(--bg)" }}>
            <p className="text-sm text-aureus-muted">
              That&apos;s today&apos;s chart. A new one unlocks tomorrow.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
