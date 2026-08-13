"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { newPatternScenario, submitPatternGuess } from "@/lib/api";
import type { PatternDirection, PatternResult, PatternScenario } from "@/lib/api";

/**
 * Chart Pattern & Candlestick Scenario Guesser.
 *
 * The setup chart is rendered from bars the server sent WITHOUT the ticker
 * or the outcome, so there is nothing in the payload to peek at. After
 * answering, the outcome bars arrive and are appended to the same series,
 * with a reference line marking the decision point — seeing the join is
 * what makes the lesson land.
 */

interface Props {
  userId: string;
  onRoundComplete: () => void;
}

export default function PatternGame({ userId, onRoundComplete }: Props) {
  const [scenario, setScenario] = useState<PatternScenario | null>(null);
  const [result, setResult] = useState<PatternResult | null>(null);
  const [choice, setChoice] = useState<PatternDirection | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setChoice(null);
    try {
      setScenario(await newPatternScenario(userId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load a scenario");
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
      const r = await submitPatternGuess(userId, scenario.scenario_id, choice);
      setResult(r);
      onRoundComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not submit your answer");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="py-16 text-center text-aureus-muted text-sm">Loading a chart…</div>;
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
  // Join the two series at the decision point so the line isn't broken.
  if (result && data[setupLen - 1]) {
    (data[setupLen - 1] as { outcome?: number }).outcome = scenario.setup_bars[setupLen - 1].close;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-white font-semibold">Which way did it resolve?</h3>
          <p className="text-xs text-aureus-muted mt-0.5">
            Real historical price action, ticker hidden. Predict the next{" "}
            {scenario.outcome_horizon_sessions} sessions.
          </p>
        </div>
        {result && <Badge variant="muted">{result.ticker}</Badge>}
      </div>

      {/* Setup notes */}
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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {scenario.choices.map((c) => (
              <button
                key={c.value}
                onClick={() => setChoice(c.value)}
                className={`rounded-lg border px-3 py-2.5 text-sm transition-colors ${
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
            {submitting ? "Checking…" : choice ? "Lock In Answer" : "Pick a direction"}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className={`rounded-lg border p-4 space-y-2 ${
            result.correct ? "border-aureus-green bg-green-950/20" : "border-aureus-red bg-red-950/20"
          }`}>
            <p className={`font-semibold ${result.correct ? "text-aureus-green" : "text-aureus-red"}`}>
              {result.correct ? "Correct" : "Not this time"} — it was a {result.correct_label}
            </p>
            <p className="text-sm text-aureus-text leading-relaxed">{result.rationale}</p>
            <p className="text-xs text-aureus-muted">
              {result.ticker} · +{result.score_awarded} knowledge XP
            </p>
          </div>
          <Button className="w-full" onClick={load}>Next Chart</Button>
        </div>
      )}
    </div>
  );
}
