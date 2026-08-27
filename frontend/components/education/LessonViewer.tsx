"use client";
/**
 * The lesson reader.
 *
 * Two things drove the layout. First, prose is read at a measure — roughly
 * 65-75 characters — and the old full-width column ran to well over a
 * hundred on a desktop, which is genuinely harder to read and not a
 * matter of taste. Second, the material a reader wants WHILE reading (the
 * takeaway, the glossary, where they are) was previously above and below
 * the text, so consulting it meant losing your place.
 *
 * So: a fixed measure for the prose, a sticky rail beside it on desktop
 * holding the reference material, and a progress bar that tracks actual
 * scroll position rather than a step count.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft, BookOpen, Check, ChevronRight, Clock, Sparkles, Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CapsLabel, ErrorNote, Figure, RuledLabel } from "@/components/ui/primitives";
import LessonBody from "./LessonBody";
import LessonQuiz from "./LessonQuiz";
import PracticeDrills from "./PracticeDrills";
import LessonExerciseCard from "./Exercises";
import {
  getEducationLesson, startEducationLesson, completeEducationLesson,
} from "@/lib/api";
import type { LessonCallout, LessonDetail, PracticeResult, QuizResult } from "@/lib/api";

const CALLOUT_STYLE: Record<LessonCallout["kind"], { label: string; accent: string; text: string; bg: string }> = {
  key_idea:       { label: "Key idea",       accent: "border-l-aureus-gold",      text: "text-aureus-gold",      bg: "bg-aureus-gold/[0.05]" },
  why_it_matters: { label: "Why it matters", accent: "border-l-aureus-verdigris", text: "text-aureus-verdigris", bg: "bg-aureus-verdigris/[0.07]" },
  common_mistake: { label: "Common mistake", accent: "border-l-aureus-oxblood",   text: "text-aureus-oxblood",   bg: "bg-aureus-oxblood/[0.07]" },
  example:        { label: "Worked example", accent: "border-l-aureus-amber",     text: "text-aureus-amber",     bg: "bg-aureus-amber/[0.07]" },
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
  const [readPct, setReadPct] = useState(0);

  const articleRef = useRef<HTMLDivElement>(null);

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

  // Reading progress, measured from the article's position inside the
  // scroll container rather than from a step counter — a step counter
  // would claim 50% after one of two sections regardless of their length.
  useEffect(() => {
    const scroller = document.querySelector("main");
    const el = articleRef.current;
    if (!scroller || !el) return;

    const onScroll = () => {
      const top = el.offsetTop;
      const total = Math.max(1, el.scrollHeight - scroller.clientHeight + 240);
      const seen = scroller.scrollTop - top + scroller.clientHeight;
      setReadPct(Math.max(0, Math.min(100, (seen / total) * 100)));
    };
    onScroll();
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => scroller.removeEventListener("scroll", onScroll);
  }, [data]);

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await completeEducationLesson(lessonId, userId);
      setJustCompleted(true);
      onProgressChanged();
      setData(await getEducationLesson(lessonId, userId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not mark complete");
    } finally {
      setCompleting(false);
    }
  };

  const onGraded = async (_r: QuizResult | PracticeResult) => {
    onProgressChanged();
    try { setData(await getEducationLesson(lessonId, userId)); } catch { /* display already updated */ }
  };

  if (loading) {
    return <div className="py-20 text-center text-sm text-aureus-muted">Loading lesson…</div>;
  }
  if (error || !data) {
    return (
      <div className="max-w-md mx-auto py-20 space-y-3">
        <ErrorNote>{error ?? "Lesson unavailable"}</ErrorNote>
        <Button variant="outline" size="sm" onClick={onBack}>Back to the curriculum</Button>
      </div>
    );
  }

  const { lesson, progress } = data;
  const done = progress.status === "completed";
  const exercises = lesson.exercises ?? [];
  const practice = lesson.practice ?? [];
  const checkpoints = lesson.checkpoints ?? [];

  return (
    <div className="relative">
      {/* Reading progress. Sits under the app chrome, above the content. */}
      <div className="sticky top-0 z-10 -mt-6 pt-6 bg-aureus-ink">
        <div className="h-0.5 bg-aureus-panelhigh rounded-full overflow-hidden">
          <div className="h-full bg-aureus-gold transition-[width] duration-150" style={{ width: `${readPct}%` }} />
        </div>
      </div>

      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-[13px] text-aureus-muted hover:text-aureus-gold transition-colors mt-5"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Curriculum
      </button>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="mt-4 pb-6 border-b border-aureus-rule">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={done ? "green" : "muted"}>{lesson.difficulty_level}</Badge>
          <span className="text-[11px] text-aureus-muted">{lesson.category}</span>
          {done && (
            <span className="flex items-center gap-1 text-[11px] text-aureus-verdigris">
              <Check className="w-3 h-3" strokeWidth={2.5} /> Completed
            </span>
          )}
        </div>
        <h1 className="font-display text-[30px] leading-tight text-aureus-text mt-3 max-w-3xl">
          {lesson.title}
        </h1>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 mt-3.5 text-[11px] text-aureus-muted">
          <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />{lesson.estimated_read_time_minutes} min</span>
          <span className="flex items-center gap-1.5 text-aureus-gold"><Zap className="w-3.5 h-3.5" />{lesson.max_xp} XP available</span>
          {lesson.quiz.length > 0 && <span>{lesson.quiz.length}-question check</span>}
          {practice.length > 0 && <span>{practice.length} calculation{practice.length === 1 ? "" : "s"}</span>}
          {exercises.length > 0 && (
            <span className="flex items-center gap-1.5 text-aureus-verdigris">
              <Sparkles className="w-3.5 h-3.5" />{exercises.length} interactive
            </span>
          )}
        </div>
      </header>

      {/* ── Body + sticky reference rail ───────────────────────────── */}
      <div ref={articleRef} className="grid lg:grid-cols-[minmax(0,1fr)_260px] gap-x-10 gap-y-8 pt-7">
        <article className="min-w-0 max-w-[68ch]">
          <LessonBody body={lesson.body} glossary={lesson.glossary} checkpoints={checkpoints} />

          {lesson.callouts.length > 0 && (
            <div className="space-y-3 mt-8">
              {lesson.callouts.map((c, i) => {
                const st = CALLOUT_STYLE[c.kind];
                return (
                  <div key={i} className={`rounded-r-md border-l-2 ${st.accent} ${st.bg} px-4 py-3.5`}>
                    <span className={`label-caps ${st.text}`}>{st.label}</span>
                    <h4 className="text-[14px] text-aureus-text font-medium mt-1.5">{c.title}</h4>
                    <p className="text-[13px] text-aureus-soft leading-relaxed mt-1">{c.body}</p>
                  </div>
                );
              })}
            </div>
          )}

          {exercises.length > 0 && (
            <div className="mt-10 space-y-5">
              <RuledLabel>Interactive</RuledLabel>
              {exercises.map((ex, i) => <LessonExerciseCard key={i} exercise={ex} />)}
            </div>
          )}

          {practice.length > 0 && (
            <div className="mt-10 pt-8 border-t border-aureus-rule">
              <PracticeDrills
                lessonId={lesson.id}
                userId={userId}
                questions={practice}
                passMark={data.practice_pass_mark ?? 1}
                bonusXp={data.practice_bonus_xp ?? 0}
                alreadyPassed={!!progress.practice_passed}
                onGraded={onGraded}
              />
            </div>
          )}

          {lesson.quiz.length > 0 && (
            <div className="mt-10 pt-8 border-t border-aureus-rule">
              <LessonQuiz
                lessonId={lesson.id}
                userId={userId}
                questions={lesson.quiz}
                passMark={data.quiz_pass_mark}
                bonusXp={data.quiz_bonus_xp}
                alreadyPassed={progress.quiz_passed}
                onGraded={onGraded}
              />
            </div>
          )}

          {/* ── Completion ─────────────────────────────────────────── */}
          <div className="mt-10 pt-8 border-t border-aureus-rule">
            {done ? (
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <span className="w-8 h-8 rounded-full bg-aureus-verdigris/15 flex items-center justify-center">
                    <Check className="w-4 h-4 text-aureus-verdigris" strokeWidth={2.5} />
                  </span>
                  <div>
                    <p className="text-[14px] text-aureus-text">Lesson complete</p>
                    <Figure tone="muted" className="text-[11px]">{progress.xp_earned} XP earned here</Figure>
                  </div>
                </div>
                <Button variant="outline" onClick={onBack}>
                  Next lesson <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-4">
                <p className="text-[13px] text-aureus-muted max-w-md">
                  {justCompleted ? "Saved." : `Mark this complete to bank ${lesson.xp_points} XP. The quiz and drills are worth more on top.`}
                </p>
                <Button onClick={handleComplete} disabled={completing}>
                  {completing ? "Saving…" : "Mark complete"}
                </Button>
              </div>
            )}
          </div>
        </article>

        {/* Reference rail — what you want available WHILE reading. */}
        <aside className="hidden lg:block">
          <div className="sticky top-16 space-y-6">
            <div className="rounded-[10px] border border-aureus-rule border-t-aureus-golddim bg-aureus-panel p-4">
              <CapsLabel>The one thing</CapsLabel>
              <p className="text-[13px] text-aureus-soft leading-relaxed mt-2">{lesson.key_takeaway}</p>
            </div>

            {lesson.glossary.length > 0 && (
              <div>
                <CapsLabel>Terms in this lesson</CapsLabel>
                <dl className="mt-2.5">
                  {lesson.glossary.map((g) => (
                    <div key={g.term} className="py-2.5 border-t border-aureus-rulesoft">
                      <dt className="text-[12px] text-aureus-gold">{g.term}</dt>
                      <dd className="text-[11.5px] text-aureus-muted leading-relaxed mt-0.5">{g.definition}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}

            <div className="flex items-center gap-2 text-[11px] text-aureus-muted">
              <BookOpen className="w-3.5 h-3.5" />
              <span>{Math.round(readPct)}% read</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
