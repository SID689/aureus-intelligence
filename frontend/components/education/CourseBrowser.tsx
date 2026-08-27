"use client";
/**
 * The curriculum, as a path rather than a list.
 *
 * The old view stacked five identical cards, each containing an
 * undifferentiated run of lesson rows. With sixty lessons that is a wall:
 * nothing indicates where you are, what to do next, or why the modules
 * are in that order.
 *
 * This renders a vertical spine with each module as a station on it, so
 * sequence is visible at a glance, and collapses modules you have not
 * reached yet — the reader sees their own position rather than everyone's
 * whole syllabus. Modules stay openable regardless: nothing here is
 * locked, because gating a beginner out of an advanced lesson they are
 * curious about teaches them nothing.
 */
import { useState } from "react";
import {
  Calculator, Check, ChevronDown, Circle, Clock, PlayCircle, Sparkles, Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CapsLabel, Figure } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import type { EducationCatalog, EducationModule, LessonSummary } from "@/lib/api";

interface Props {
  catalog: EducationCatalog;
  onOpenLesson: (lessonId: string) => void;
}

function StatusMark({ status }: { status: LessonSummary["status"] }) {
  if (status === "completed") {
    return (
      <span className="w-5 h-5 rounded-full bg-aureus-verdigris/15 flex items-center justify-center shrink-0">
        <Check className="w-3 h-3 text-aureus-verdigris" strokeWidth={3} />
      </span>
    );
  }
  if (status === "in_progress") {
    return (
      <span className="w-5 h-5 rounded-full bg-aureus-gold/15 flex items-center justify-center shrink-0">
        <PlayCircle className="w-3 h-3 text-aureus-gold" strokeWidth={2.5} />
      </span>
    );
  }
  return (
    <span className="w-5 h-5 rounded-full border border-aureus-rule flex items-center justify-center shrink-0">
      <Circle className="w-1.5 h-1.5 text-aureus-muted/60 fill-current" />
    </span>
  );
}

function LessonRow({ lesson, onOpen }: { lesson: LessonSummary; onOpen: () => void }) {
  const interactive = (lesson.exercise_count ?? 0) > 0;
  const drills = lesson.practice_count ?? 0;

  return (
    <button
      onClick={onOpen}
      className="w-full text-left group flex items-start gap-3 pl-3 pr-3 py-2.5 rounded-md
                 border-l-2 border-transparent hover:border-aureus-gold hover:bg-aureus-panellift transition-colors"
    >
      <span className="pt-0.5"><StatusMark status={lesson.status} /></span>
      <span className="flex-1 min-w-0">
        <span className="flex items-baseline justify-between gap-3">
          <span className={cn(
            "text-[13.5px] truncate",
            lesson.status === "completed" ? "text-aureus-muted" : "text-aureus-text group-hover:text-aureus-gold",
          )}>
            {lesson.title}
          </span>
          <Figure tone="muted" className="text-[11px] shrink-0">{lesson.estimated_read_time_minutes}m</Figure>
        </span>
        <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1 mt-1 text-[11px] text-aureus-muted">
          <span>{lesson.category}</span>
          {lesson.quiz_question_count > 0 && (
            <span className={lesson.quiz_passed ? "text-aureus-verdigris" : ""}>
              {lesson.quiz_passed ? `quiz ${lesson.quiz_best_score}/${lesson.quiz_total}` : `${lesson.quiz_question_count}q`}
            </span>
          )}
          {drills > 0 && (
            <span className="flex items-center gap-1"><Calculator className="w-3 h-3" />{drills}</span>
          )}
          {interactive && (
            <span className="flex items-center gap-1 text-aureus-verdigris">
              <Sparkles className="w-3 h-3" />interactive
            </span>
          )}
          {lesson.xp_earned > 0 && <span className="text-aureus-gold">{lesson.xp_earned} XP</span>}
        </span>
      </span>
    </button>
  );
}

function ModuleStation({
  module, index, total, defaultOpen, onOpenLesson,
}: {
  module: EducationModule; index: number; total: number;
  defaultOpen: boolean; onOpenLesson: (id: string) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const done = module.percent_complete === 100;
  const started = module.lessons_completed > 0;

  return (
    <div className="relative pl-11">
      {/* The spine. Drawn per-station and stopped on the last one, so the
          line does not dangle past the final module. */}
      {index < total - 1 && (
        <span
          className="absolute left-[15px] top-8 bottom-0 w-px bg-aureus-rule"
          aria-hidden
        />
      )}

      {/* Station marker */}
      <span
        className={cn(
          "absolute left-0 top-0.5 w-8 h-8 rounded-full flex items-center justify-center",
          "font-mono-num text-[12px] border-2 shrink-0",
          done ? "bg-aureus-verdigris/15 border-aureus-verdigris text-aureus-verdigris"
            : started ? "bg-aureus-gold/10 border-aureus-gold text-aureus-gold"
            : "bg-aureus-panel border-aureus-rule text-aureus-muted",
        )}
        aria-hidden
      >
        {done ? <Check className="w-4 h-4" strokeWidth={3} /> : module.tier}
      </span>

      <div className="pb-8">
        <button
          onClick={() => setOpen(!open)}
          className="w-full text-left group"
          aria-expanded={open}
        >
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-display text-[19px] text-aureus-text group-hover:text-aureus-gold transition-colors">
              {module.label}
            </h2>
            <Badge variant={done ? "green" : "muted"}>{module.difficulty_level}</Badge>
            <ChevronDown className={cn(
              "w-4 h-4 text-aureus-muted transition-transform ml-auto shrink-0",
              open && "rotate-180",
            )} />
          </div>
          <p className="text-[13px] text-aureus-muted leading-relaxed mt-1.5 max-w-2xl">
            {module.description}
          </p>
        </button>

        {/* Progress line for the module */}
        <div className="mt-3 space-y-1.5 max-w-2xl">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-aureus-muted">
            <Figure tone={done ? "up" : "muted"} className="text-[11px]">
              {module.lessons_completed}/{module.lesson_count} lessons
            </Figure>
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{module.estimated_minutes} min</span>
            <span className="flex items-center gap-1 text-aureus-gold">
              <Zap className="w-3 h-3" />{module.xp_earned}/{module.total_xp_available} XP
            </span>
            <Figure tone="muted" className="text-[11px] ml-auto">{module.percent_complete}%</Figure>
          </div>
          <div className="h-1 rounded-sm bg-aureus-panelhigh overflow-hidden">
            <div
              className={cn("h-full transition-all duration-500", done ? "bg-aureus-verdigris" : "bg-aureus-gold")}
              style={{ width: `${module.percent_complete}%` }}
            />
          </div>
        </div>

        {open && (
          <div className="mt-3 -ml-3 space-y-0.5 rise-in">
            {module.lessons.map((l) => (
              <LessonRow key={l.id} lesson={l} onOpen={() => onOpenLesson(l.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CourseBrowser({ catalog, onOpenLesson }: Props) {
  const modules = catalog.modules;

  // Open the module you are actually working through, plus the first
  // unstarted one. Everything else collapses: sixty lessons expanded at
  // once is a wall, not a curriculum.
  const inProgressTier = modules.find((m) => m.lessons_completed > 0 && m.percent_complete < 100)?.tier;
  const firstUnstartedTier = modules.find((m) => m.lessons_completed === 0)?.tier;
  const openTier = inProgressTier ?? firstUnstartedTier ?? modules[0]?.tier;

  return (
    <div>
      <CapsLabel>The path</CapsLabel>
      <div className="mt-5">
        {modules.map((m, i) => (
          <ModuleStation
            key={m.tier}
            module={m}
            index={i}
            total={modules.length}
            defaultOpen={m.tier === openTier}
            onOpenLesson={onOpenLesson}
          />
        ))}
      </div>
    </div>
  );
}
