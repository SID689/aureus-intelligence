"use client";
import { useEffect, useState, useCallback } from "react";
import { ArrowLeft, BookOpen, Clock, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import LessonBody from "./LessonBody";
import LessonQuiz from "./LessonQuiz";
import {
  getEducationLesson, startEducationLesson, completeEducationLesson,
} from "@/lib/api";
import type { LessonCallout, LessonDetail, QuizResult } from "@/lib/api";

const CALLOUT_STYLE: Record<LessonCallout["kind"], { label: string; border: string; text: string; bg: string }> = {
  key_idea:       { label: "Key Idea",       border: "border-aureus-gold",      text: "text-aureus-gold",      bg: "bg-aureus-gold/[0.05]" },
  why_it_matters: { label: "Why It Matters", border: "border-aureus-verdigris", text: "text-aureus-verdigris", bg: "bg-emerald-950/20" },
  common_mistake: { label: "Common Mistake", border: "border-aureus-oxblood",   text: "text-aureus-oxblood",   bg: "bg-red-950/20" },
  example:        { label: "Worked Example", border: "border-blue-400",         text: "text-blue-300",         bg: "bg-blue-950/20" },
};

interface Props {
  lessonId: string;
  userId: string;
  onBack: () => void;
  onProgressChanged: () => void;
}

export default function LessonViewer({ lessonId, userId, onBack, onProgressChanged }: Props) {
  const [data, setData] = useState<LessonDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [justCompleted, setJustCompleted] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getEducationLesson(lessonId, userId);
      setData(res);
      // Fire-and-forget: recording that the lesson was opened must never
      // block or fail the actual reading experience.
      startEducationLesson(lessonId, userId).then(onProgressChanged).catch(() => {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load lesson");
    } finally {
      setLoading(false);
    }
  }, [lessonId, userId, onProgressChanged]);

  useEffect(() => { load(); }, [load]);

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await completeEducationLesson(lessonId, userId);
      setJustCompleted(true);
      onProgressChanged();
      const fresh = await getEducationLesson(lessonId, userId);
      setData(fresh);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not mark complete");
    } finally {
      setCompleting(false);
    }
  };

  const handleGraded = (_r: QuizResult) => {
    onProgressChanged();
    getEducationLesson(lessonId, userId).then(setData).catch(() => {});
  };

  if (loading) {
    return <div className="py-20 text-center text-aureus-muted text-sm">Loading lesson…</div>;
  }
  if (error || !data) {
    return (
      <div className="py-20 text-center space-y-3">
        <p className="text-aureus-red text-sm">{error ?? "Lesson not found"}</p>
        <Button variant="outline" size="sm" onClick={onBack}>Back to all modules</Button>
      </div>
    );
  }

  const { lesson, progress, quiz_pass_mark, quiz_bonus_xp } = data;
  const isComplete = progress.status === "completed";

  return (
    <article className="max-w-3xl space-y-6">
      <button onClick={onBack}
              className="flex items-center gap-1.5 text-xs text-aureus-muted hover:text-white transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to all modules
      </button>

      {/* Header */}
      <header className="space-y-3 pb-5 border-b border-aureus-rule">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default">{lesson.tier_label}</Badge>
          <span className="text-xs text-aureus-muted">{lesson.category}</span>
          {isComplete && <Badge variant="green">✓ Completed</Badge>}
        </div>
        <h1 className="text-2xl font-bold text-white leading-tight">{lesson.title}</h1>
        <div className="flex flex-wrap items-center gap-4 text-xs text-aureus-muted">
          <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{lesson.estimated_read_time_minutes} min read</span>
          <span className="flex items-center gap-1"><Zap className="w-3.5 h-3.5" />{lesson.max_xp} XP available</span>
          {lesson.quiz_question_count > 0 && (
            <span className="flex items-center gap-1"><BookOpen className="w-3.5 h-3.5" />{lesson.quiz_question_count}-question check</span>
          )}
          {progress.xp_earned > 0 && <span className="text-aureus-gold">{progress.xp_earned} XP earned</span>}
        </div>
      </header>

      {/* Body */}
      <LessonBody body={lesson.body} glossary={lesson.glossary} />

      {/* Callouts */}
      {lesson.callouts.length > 0 && (
        <div className="space-y-3">
          {lesson.callouts.map((c, i) => {
            const s = CALLOUT_STYLE[c.kind] ?? CALLOUT_STYLE.key_idea;
            return (
              <div key={i} className={`rounded-lg border-l-2 ${s.border} ${s.bg} px-4 py-3 space-y-1`}>
                <p className={`text-[10px] uppercase tracking-wider font-semibold ${s.text}`}>{s.label}</p>
                <p className="text-sm text-white font-medium">{c.title}</p>
                <p className="text-sm text-aureus-muted leading-relaxed">{c.body}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Key takeaway */}
      <div className="rounded-lg border border-aureus-gold/40 bg-aureus-gold/[0.06] p-4">
        <p className="text-[10px] uppercase tracking-wider font-semibold text-aureus-gold mb-1.5">Key Takeaway</p>
        <p className="text-sm text-white leading-relaxed">{lesson.key_takeaway}</p>
      </div>

      {/* Glossary */}
      {lesson.glossary.length > 0 && (
        <details className="rounded-lg border border-aureus-border p-4" style={{ background: "var(--surface)" }}>
          <summary className="text-xs uppercase tracking-wider text-aureus-muted cursor-pointer select-none hover:text-white">
            Glossary ({lesson.glossary.length} terms)
          </summary>
          <dl className="mt-3 space-y-2">
            {lesson.glossary.map((g) => (
              <div key={g.term} className="text-sm">
                <dt className="text-aureus-gold font-medium inline">{g.term}</dt>
                <dd className="text-aureus-muted inline"> — {g.definition}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}

      {/* Completion */}
      <div className="pt-2 border-t border-aureus-rule">
        {isComplete ? (
          <p className="text-sm text-aureus-green py-2">
            ✓ Lesson complete{justCompleted && ` — +${lesson.xp_points} XP`}
            {lesson.quiz_question_count > 0 && !progress.quiz_passed &&
              " · pass the knowledge check below for bonus XP"}
          </p>
        ) : (
          <Button onClick={handleComplete} disabled={completing}>
            {completing ? "Saving…" : `Mark Complete · +${lesson.xp_points} XP`}
          </Button>
        )}
      </div>

      {/* Quiz */}
      {lesson.quiz.length > 0 && (
        <section className="pt-4 border-t border-aureus-rule">
          <LessonQuiz
            lessonId={lesson.id}
            userId={userId}
            questions={lesson.quiz}
            passMark={quiz_pass_mark}
            bonusXp={quiz_bonus_xp}
            alreadyPassed={progress.quiz_passed}
            onGraded={handleGraded}
          />
        </section>
      )}

      <p className="text-xs text-aureus-muted pt-2">
        Educational content only · Not financial advice · Past performance is not indicative of future results
      </p>
    </article>
  );
}
