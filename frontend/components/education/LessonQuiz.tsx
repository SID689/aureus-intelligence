"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { submitEducationQuiz } from "@/lib/api";
import type { QuizOption, QuizResult } from "@/lib/api";

/**
 * End-of-lesson knowledge check.
 *
 * Correct answers are NOT present in the payload the page received — the
 * server withholds them until submission (see education.py). This component
 * therefore cannot grade locally even if it wanted to; it posts the selected
 * indices and renders whatever the server returns. That's the point: it makes
 * client-side answer peeking impossible rather than merely inconvenient.
 */

interface Props {
  lessonId: string;
  userId: string;
  questions: QuizOption[];
  passMark: number;
  bonusXp: number;
  alreadyPassed: boolean;
  onGraded: (result: QuizResult) => void;
}

export default function LessonQuiz({
  lessonId, userId, questions, passMark, bonusXp, alreadyPassed, onGraded,
}: Props) {
  const [answers, setAnswers] = useState<number[]>(() => questions.map(() => -1));
  const [result, setResult] = useState<QuizResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allAnswered = answers.every((a) => a >= 0);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitEducationQuiz(lessonId, userId, answers);
      setResult(res);
      onGraded(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not submit quiz");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = () => {
    setResult(null);
    setAnswers(questions.map(() => -1));
  };

  const resultFor = (qi: number) => result?.results.find((r) => r.index === qi);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-aureus-text font-semibold">Knowledge Check</h3>
          <p className="text-xs text-aureus-muted mt-0.5">
            {questions.length} question{questions.length === 1 ? "" : "s"} · {passMark} correct to pass
            {bonusXp > 0 && !alreadyPassed && ` · +${bonusXp} XP bonus`}
          </p>
        </div>
        {alreadyPassed && (
          <span className="text-xs text-aureus-emerald border border-aureus-emeralddim/40 bg-aureus-emerald/10 rounded px-2 py-0.5">
            Passed
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-sm border border-aureus-crimsondim bg-aureus-crimson/10 p-3 text-aureus-crimson text-xs">{error}</div>
      )}

      {questions.map((q, qi) => {
        const r = resultFor(qi);
        return (
          <div key={qi} className="rounded-sm border border-aureus-rule p-4 space-y-3"
               style={{ background: "var(--ink)" }}>
            <p className="text-sm text-aureus-text font-medium">
              <span className="text-aureus-muted mr-2">{qi + 1}.</span>{q.question}
            </p>

            <div className="space-y-1.5">
              {q.options.map((opt, oi) => {
                const selected = answers[qi] === oi;
                let tone = "border-aureus-rule text-aureus-text hover:border-aureus-muted";
                if (r) {
                  if (oi === r.correct_index) tone = "border-aureus-emeralddim bg-aureus-emerald/10 text-aureus-emerald";
                  else if (selected) tone = "border-aureus-crimsondim bg-aureus-crimson/10 text-aureus-crimson";
                  else tone = "border-aureus-rule/50 text-aureus-muted";
                } else if (selected) {
                  tone = "border-aureus-gold bg-aureus-gold/10 text-aureus-gold";
                }
                return (
                  <button
                    key={oi}
                    type="button"
                    disabled={!!result}
                    onClick={() => setAnswers((prev) => prev.map((a, i) => (i === qi ? oi : a)))}
                    className={`w-full text-left text-sm rounded-md border px-3 py-2 transition-colors disabled:cursor-default ${tone}`}
                  >
                    <span className="font-mono text-xs mr-2 opacity-70">
                      {String.fromCharCode(65 + oi)}
                    </span>
                    {opt}
                    {r && oi === r.correct_index && <span className="float-right label-caps text-aureus-emerald">Correct</span>}
                    {r && selected && oi !== r.correct_index && <span className="float-right label-caps text-aureus-crimson">Your answer</span>}
                  </button>
                );
              })}
            </div>

            {r && (
              <div className="rounded-sm border border-aureus-gold/25 bg-aureus-gold/[0.04] px-3 py-2">
                <p className="text-xs text-aureus-muted leading-relaxed">
                  <span className="text-aureus-gold font-semibold">Why: </span>{r.explanation}
                </p>
              </div>
            )}
          </div>
        );
      })}

      {!result ? (
        <Button onClick={handleSubmit} disabled={!allAnswered || submitting} className="w-full">
          {submitting ? "Checking" : allAnswered ? "Submit Answers" : `Answer all ${questions.length} questions`}
        </Button>
      ) : (
        <div className={`rounded-sm border p-4 text-center space-y-2 ${
          result.passed ? "border-aureus-emeralddim bg-aureus-emerald/10" : "border-aureus-gold bg-aureus-amber/10"
        }`}>
          <p className={`text-lg font-semibold ${result.passed ? "text-aureus-emerald" : "text-aureus-gold"}`}>
            {result.score} / {result.total} correct
          </p>
          <p className="text-xs text-aureus-muted">
            {result.passed
              ? `Passed: best score ${result.best_score}/${result.total}. Total XP for this lesson: ${result.xp_earned_total_for_lesson}.`
              : `${result.pass_mark} correct needed to pass. Review the explanations above and try again: your best score is kept.`}
          </p>
          <Button variant="outline" size="sm" onClick={handleRetry}>Retake Quiz</Button>
        </div>
      )}
    </div>
  );
}
