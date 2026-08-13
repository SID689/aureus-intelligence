"use client";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Trophy, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
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
      <div className="py-20 text-center space-y-3">
        <p className="text-aureus-red text-sm">{error ?? "Curriculum unavailable"}</p>
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
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Education</h1>
          <p className="text-aureus-muted text-sm mt-0.5">
            A structured curriculum from absolute beginner to institutional-grade. Work through it
            at your own pace — the dashboard&apos;s daily lesson draws from the same content.
          </p>
        </div>
        <Button variant="outline" onClick={() => setShowAchievements(true)}>
          <Trophy className="w-4 h-4 mr-2" />
          Achievements ({earnedBadges})
        </Button>
      </div>

      {/* Overall progress */}
      <div className="rounded-lg border border-aureus-rule p-4 space-y-3" style={{ background: "var(--panel)" }}>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <span className="text-white font-medium">
            {totals.lessons_completed} of {totals.lessons_total} lessons complete
          </span>
          <span className="flex items-center gap-1.5 text-aureus-gold font-mono text-sm">
            <Zap className="w-4 h-4" />
            {totals.xp_earned.toLocaleString()} / {totals.xp_available.toLocaleString()} XP
          </span>
        </div>
        <div className="h-2 rounded-full bg-aureus-rule/40 overflow-hidden">
          <div className="h-full bg-aureus-gold transition-all" style={{ width: `${totals.percent_complete}%` }} />
        </div>
        {progress.quiz_accuracy_pct !== null && (
          <p className="text-xs text-aureus-muted">
            Quiz accuracy {progress.quiz_accuracy_pct}% across {progress.quizzes_taken} knowledge
            check{progress.quizzes_taken === 1 ? "" : "s"} · {progress.perfect_quizzes} perfect
          </p>
        )}
      </div>

      <CourseBrowser catalog={catalog} onOpenLesson={setActiveLessonId} />
    </div>
  );
}
