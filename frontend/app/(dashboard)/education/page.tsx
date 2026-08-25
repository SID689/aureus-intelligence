"use client";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Trophy, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNote, Figure, PageHeader, Sheet } from "@/components/ui/primitives";
import CourseBrowser from "@/components/education/CourseBrowser";
import LessonViewer from "@/components/education/LessonViewer";
import AchievementsModal from "@/components/education/AchievementsModal";
import { getEducationCatalog, getEducationProgress } from "@/lib/api";
import type { EducationCatalog, EducationProgress } from "@/lib/api";

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

  // Lesson viewer takes over the full pane when a lesson is open.
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

  return (
    <div className="space-y-6">
      {showAchievements && (
        <AchievementsModal progress={progress} onClose={() => setShowAchievements(false)} />
      )}

      {/* Header */}
      <PageHeader
        title="Education"
        lead="A structured curriculum from absolute beginner to institutional-grade. Work through it
              at your own pace — the dashboard's daily lesson draws from the same content."
        actions={
          <Button variant="outline" onClick={() => setShowAchievements(true)}>
            <Trophy className="w-4 h-4" /> Achievements ({earnedBadges})
          </Button>
        }
      />

      {/* Overall progress */}
      <Sheet lift accent className="p-5 space-y-3.5">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <span className="text-[15px] text-aureus-text">
            <Figure className="text-lg">{totals.lessons_completed}</Figure>
            <span className="text-aureus-muted"> of </span>
            <Figure tone="muted" className="text-lg">{totals.lessons_total}</Figure>
            <span className="text-aureus-muted text-[13px]"> lessons complete</span>
          </span>
          <span className="flex items-center gap-1.5 text-aureus-gold">
            <Zap className="w-3.5 h-3.5" strokeWidth={2} />
            <Figure className="text-[13px] text-aureus-gold">
              {totals.xp_earned.toLocaleString()} / {totals.xp_available.toLocaleString()} XP
            </Figure>
          </span>
        </div>
        <div className="h-1.5 rounded-sm bg-aureus-panelhigh overflow-hidden">
          <div className="h-full bg-aureus-gold transition-all duration-500" style={{ width: `${totals.percent_complete}%` }} />
        </div>
        {progress.quiz_accuracy_pct !== null && (
          <p className="text-[12px] text-aureus-muted">
            Quiz accuracy <Figure tone="muted" className="text-[12px]">{progress.quiz_accuracy_pct}%</Figure> across{" "}
            {progress.quizzes_taken} knowledge check{progress.quizzes_taken === 1 ? "" : "s"} ·{" "}
            {progress.perfect_quizzes} perfect
          </p>
        )}
      </Sheet>

      <CourseBrowser catalog={catalog} onOpenLesson={setActiveLessonId} />
    </div>
  );
}
