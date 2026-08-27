"use client";
/**
 * Numeric drills — the reader computes the answer rather than choosing it.
 *
 * Four options hand you a 25% chance for free; an empty field hands you
 * nothing. That is the entire reason these exist alongside the quiz, and
 * why they are worth more XP.
 *
 * The correct value AND the tolerance stay on the server until submission
 * (see api/v1/education.py). Shipping the tolerance would let a reader
 * binary-search the accepted range, which is a slower way of being told
 * the answer.
 */
import { useState } from "react";
import { Check, Lightbulb, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Figure } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { submitEducationPractice } from "@/lib/api";
import type { PracticeQuestion, PracticeResult } from "@/lib/api";

interface Props {
  lessonId: string;
  userId: string;
  questions: PracticeQuestion[];
  passMark: number;
  bonusXp: number;
  alreadyPassed: boolean;
  onGraded: (r: PracticeResult) => void;
}

export default function PracticeDrills({
  lessonId, userId, questions, passMark, bonusXp, alreadyPassed, onGraded,
}: Props) {
  // Stored as strings so a half-typed "-" or "1." doesn't get coerced to
  // NaN and wipe what the user is in the middle of writing.
  const [raw, setRaw] = useState<string[]>(() => questions.map(() => ""));
  const [hintsShown, setHintsShown] = useState<Set<number>>(new Set());
  const [result, setResult] = useState<PracticeResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = raw.map((r) => {
    const t = r.trim().replace(/,/g, "");
    if (t === "" || t === "-" || t === "." || t === "-.") return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  });
  const allAnswered = parsed.every((v) => v !== null);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const r = await submitEducationPractice(lessonId, userId, parsed);
      setResult(r);
      onGraded(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not submit");
    } finally {
      setSubmitting(false);
    }
  };

  const retry = () => {
    setResult(null);
    setRaw(questions.map(() => ""));
  };

  const resultFor = (i: number) => result?.results.find((r) => r.index === i);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg text-aureus-text">Work it out</h3>
          <p className="text-[12px] text-aureus-muted mt-0.5">
            {questions.length} calculation{questions.length === 1 ? "" : "s"} · {passMark} correct to pass
            {bonusXp > 0 && !alreadyPassed && ` · +${bonusXp} XP`}
          </p>
        </div>
        {alreadyPassed && (
          <span className="text-[11px] text-aureus-verdigris border border-aureus-verdigrisdim/40 bg-aureus-verdigris/10 rounded px-2 py-0.5">
            Passed
          </span>
        )}
      </div>

      <div className="space-y-4">
        {questions.map((q, i) => {
          const r = resultFor(i);
          const showHint = hintsShown.has(i);
          return (
            <div
              key={i}
              className={cn(
                "rounded-[10px] border p-4",
                !r && "border-aureus-rule bg-aureus-panel",
                r?.correct && "border-aureus-verdigrisdim/50 bg-aureus-verdigris/[0.06]",
                r && !r.correct && "border-aureus-oxblooddim/50 bg-aureus-oxblood/[0.06]",
              )}
            >
              <div className="flex items-start gap-3">
                <Figure tone="muted" className="text-[11px] pt-1 w-5 shrink-0">{i + 1}</Figure>
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] text-aureus-text leading-relaxed">{q.question}</p>

                  <div className="flex flex-wrap items-center gap-2 mt-3">
                    <div className="relative">
                      <input
                        type="text"
                        inputMode="decimal"
                        value={raw[i]}
                        onChange={(e) => {
                          const next = [...raw];
                          next[i] = e.target.value;
                          setRaw(next);
                        }}
                        disabled={!!result}
                        placeholder="Your answer"
                        aria-label={`Answer to question ${i + 1}`}
                        className={cn(
                          "w-40 rounded-md border bg-aureus-ink px-3 py-2 text-sm font-mono-num text-aureus-text",
                          "placeholder:text-aureus-muted/50 focus:outline-none transition-colors",
                          q.unit ? "pr-10" : "",
                          r?.correct ? "border-aureus-verdigrisdim"
                            : r ? "border-aureus-oxblooddim"
                            : "border-aureus-rule focus:border-aureus-gold",
                        )}
                      />
                      {q.unit && (
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-aureus-muted pointer-events-none">
                          {q.unit}
                        </span>
                      )}
                    </div>

                    {!result && q.hint && !showHint && (
                      <button
                        onClick={() => setHintsShown(new Set(hintsShown).add(i))}
                        className="flex items-center gap-1.5 text-[11px] text-aureus-muted hover:text-aureus-gold transition-colors"
                      >
                        <Lightbulb className="w-3 h-3" /> Hint
                      </button>
                    )}

                    {r && (
                      <span className={cn(
                        "flex items-center gap-1.5 text-[12px]",
                        r.correct ? "text-aureus-verdigris" : "text-aureus-oxblood",
                      )}>
                        {r.correct
                          ? <><Check className="w-3.5 h-3.5" strokeWidth={2.5} /> Correct</>
                          : <><X className="w-3.5 h-3.5" strokeWidth={2.5} /> Answer: {r.correct_answer}{r.unit}</>}
                      </span>
                    )}
                  </div>

                  {showHint && !result && (
                    <p className="text-[12px] text-aureus-amber mt-2.5 leading-relaxed rise-in">{q.hint}</p>
                  )}

                  {r && (
                    <p className="text-[12.5px] text-aureus-soft leading-relaxed mt-3 pt-3 border-t border-aureus-rulesoft rise-in">
                      {r.explanation}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {error && <p className="text-[13px] text-aureus-oxblood">{error}</p>}

      {!result ? (
        <Button onClick={submit} disabled={!allAnswered || submitting}>
          {submitting ? "Checking…" : allAnswered ? "Check my answers" : "Answer every question first"}
        </Button>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <span className={cn(
            "text-sm font-medium",
            result.passed ? "text-aureus-verdigris" : "text-aureus-amber",
          )}>
            {result.score} of {result.total} correct
            {result.passed ? " — passed" : ` — ${result.pass_mark} needed`}
          </span>
          <Button variant="outline" size="sm" onClick={retry}>Try again</Button>
        </div>
      )}
    </div>
  );
}
