"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { ArrowRight, Calculator, Sparkles, Trophy, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  CapsLabel, ErrorNote, Figure, PageHeader, Sheet, StatColumns,
} from "@/components/ui/primitives";
import CourseBrowser from "@/components/education/CourseBrowser";
import LessonViewer from "@/components/education/LessonViewer";
import AchievementsModal from "@/components/education/AchievementsModal";
import { getEducationCatalog, getEducationProgress } from "@/lib/api";
import type { EducationCatalog, EducationProgress, LessonSummary } from "@/lib/api";

export default function EducationPage() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";

  const [catalog, setCatalog] = useState<EducationCatalog | null>(null);
  const [progress, setProgress] = useState<EducationProgress | null>(null);
  const [activeLessonId, setActiveLessonId] = useState<string | null>(null);
  const [showAchievements, setShowAchievements] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const [c, p] = await Promise.all([
        getEducationCatalog(userId),
        getEducationProgress(userId),
      ]);
      setCatalog(c);
      setProgress(p);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load the curriculum");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { refresh(); }, [refresh]);

  /**
   * Where to send someone who just wants to carry on.
   *
   * A curriculum of sixty lessons has a real cost of re-entry: you open
   * it, you cannot remember where you stopped, and you scroll. Resolving
   * that to a single button is the highest-value thing this page does.
   * Priority is whatever is genuinely in progress, then the first thing
   * not yet started, walking modules in order.
   */
  const nextUp = useMemo((): { lesson: LessonSummary; moduleLabel: string; resuming: boolean } | null => {
    if (!catalog) return null;
    for (const m of catalog.modules) {
      const started = m.lessons.find((l) => l.status === "in_progress");
      if (started) return { lesson: started, moduleLabel: m.label, resuming: true };
    }
    for (const m of catalog.modules) {
      const fresh = m.lessons.find((l) => l.status === "not_started");
      if (fresh) return { lesson: fresh, moduleLabel: m.label, resuming: false };
    }
    return null;
  }, [catalog]);

  if (!userId || loading) {
    return <div className="py-20 text-center text-aureus-muted text-sm">Loading curriculum…</div>;
  }

  if (error || !catalog || !progress) {
    return (
      <div className="py-20 max-w-md mx-auto space-y-3 text-center">
        <ErrorNote>{error ?? "Curriculum unavailable"}</ErrorNote>
        <Button variant="outline" size="sm" onClick={refresh}>Retry</Button>
      </div>
    );
  }

  // The lesson viewer takes the whole pane. Deliberately not a modal —
  // reading a 2,000-word lesson inside a dialog is a bad experience, and
  // it breaks the browser back button people expect to use.
  if (activeLessonId) {
    return (
      <LessonViewer
        lessonId={activeLessonId}
        userId={userId}
        onBack={() => { setActiveLessonId(null); refresh(); }}
        onProgressChanged={refresh}
      />
    );
  }

  const { totals } = catalog;
  const earnedBadges = progress.badges.filter((b) => b.earned).length;

  // Counted here rather than served, so the figure cannot drift from the
  // catalogue actually rendered below it.
  const interactiveCount = catalog.modules.reduce(
    (n, m) => n + m.lessons.filter((l) => (l.exercise_count ?? 0) > 0).length, 0,
  );
  const drillCount = catalog.modules.reduce(
    (n, m) => n + m.lessons.reduce((k, l) => k + (l.practice_count ?? 0), 0), 0,
  );

  return (
    <div className="space-y-7">
      {showAchievements && (
        <AchievementsModal progress={progress} onClose={() => setShowAchievements(false)} />
      )}

      <PageHeader
        title="Education"
        lead="Sixty lessons from never-bought-a-stock to institutional risk modelling. Work through
              it in order or dip in anywhere — nothing is locked, and the dashboard's daily lesson
              draws from the same material."
        actions={
          <Button variant="outline" onClick={() => setShowAchievements(true)}>
            <Trophy className="w-4 h-4" /> Achievements ({earnedBadges})
          </Button>
        }
      />

      {/* ── Continue ─────────────────────────────────────────────────
          The single most useful control on the page: sixty lessons means
          the cost of re-entry is remembering where you stopped. */}
      {nextUp && (
        <Sheet lift accent className="overflow-hidden">
          <div className="p-5 flex flex-wrap items-center gap-x-6 gap-y-4">
            <div className="flex-1 min-w-[18rem]">
              <CapsLabel>{nextUp.resuming ? "Pick up where you left off" : "Start here"}</CapsLabel>
              <h2 className="font-display text-[21px] text-aureus-text mt-1.5">{nextUp.lesson.title}</h2>
              <p className="text-[12px] text-aureus-muted mt-1.5">
                {nextUp.moduleLabel} · {nextUp.lesson.category} · {nextUp.lesson.estimated_read_time_minutes} min
                {(nextUp.lesson.exercise_count ?? 0) > 0 && " · interactive"}
              </p>
            </div>
            <Button onClick={() => setActiveLessonId(nextUp.lesson.id)}>
              {nextUp.resuming ? "Continue" : "Begin"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>

          <StatColumns
            className="border-t border-aureus-rule"
            items={[
              {
                label: "Lessons complete",
                value: `${totals.lessons_completed}/${totals.lessons_total}`,
                sub: `${totals.percent_complete}% of the curriculum`,
                tone: totals.lessons_completed > 0 ? "up" : "muted",
              },
              {
                label: "XP earned",
                value: totals.xp_earned.toLocaleString(),
                sub: `of ${totals.xp_available.toLocaleString()} available`,
              },
              {
                label: "Quiz accuracy",
                value: progress.quiz_accuracy_pct !== null ? `${progress.quiz_accuracy_pct}%` : "—",
                sub: progress.quizzes_taken > 0
                  ? `${progress.quizzes_taken} taken · ${progress.perfect_quizzes} perfect`
                  : "no checks taken yet",
                tone: (progress.quiz_accuracy_pct ?? 0) >= 70 ? "up" : undefined,
              },
            ]}
          />

          <div className="px-5 py-3 border-t border-aureus-rule">
            <div className="h-1 rounded-sm bg-aureus-panelhigh overflow-hidden">
              <div
                className="h-full bg-aureus-gold transition-all duration-500"
                style={{ width: `${totals.percent_complete}%` }}
              />
            </div>
          </div>
        </Sheet>
      )}

      {/* What is actually in here, beyond reading */}
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <span className="flex items-center gap-2 text-[12px] text-aureus-muted">
          <Sparkles className="w-3.5 h-3.5 text-aureus-verdigris" />
          <Figure tone="muted" className="text-[12px]">{interactiveCount}</Figure> lessons with interactive models
        </span>
        <span className="flex items-center gap-2 text-[12px] text-aureus-muted">
          <Calculator className="w-3.5 h-3.5 text-aureus-gold" />
          <Figure tone="muted" className="text-[12px]">{drillCount}</Figure> calculations to work through
        </span>
        <span className="flex items-center gap-2 text-[12px] text-aureus-muted">
          <Zap className="w-3.5 h-3.5 text-aureus-gold" />
          <Figure tone="muted" className="text-[12px]">{totals.xp_available.toLocaleString()}</Figure> XP in total
        </span>
      </div>

      <CourseBrowser catalog={catalog} onOpenLesson={setActiveLessonId} />
    </div>
  );
}
