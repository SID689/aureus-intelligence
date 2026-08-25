"use client";
import { X } from "lucide-react";
import type { EducationProgress } from "@/lib/api";

interface Props {
  progress: EducationProgress;
  onClose: () => void;
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
      <div className="text-[10px] uppercase tracking-wider text-aureus-muted mb-1">{label}</div>
      <div className="text-lg font-semibold text-aureus-text">{value}</div>
      {sub && <div className="text-xs text-aureus-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export default function AchievementsModal({ progress, onClose }: Props) {
  const earned = progress.badges.filter((b) => b.earned);
  const locked = progress.badges.filter((b) => !b.earned);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl border border-aureus-rule p-6 space-y-5"
           style={{ background: "var(--panel)" }}
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-display text-aureus-text text-xl" style={{ fontWeight: 600 }}>Progress &amp; Achievements</h2>
            <p className="text-xs text-aureus-muted mt-0.5">
              {earned.length} of {progress.badges.length} badges unlocked
            </p>
          </div>
          <button onClick={onClose} className="text-aureus-muted hover:text-aureus-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Headline stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="XP Earned" value={progress.xp_earned.toLocaleString()}
                sub={`of ${progress.xp_available.toLocaleString()}`} />
          <Stat label="Lessons" value={`${progress.lessons_completed}/${progress.lessons_total}`}
                sub={`${Math.round((progress.lessons_completed / Math.max(1, progress.lessons_total)) * 100)}% complete`} />
          <Stat label="Quiz Accuracy"
                value={progress.quiz_accuracy_pct == null ? "—" : `${progress.quiz_accuracy_pct}%`}
                sub={progress.total_answers > 0 ? `${progress.correct_answers}/${progress.total_answers} correct` : "no quizzes yet"} />
          <Stat label="Perfect Scores" value={String(progress.perfect_quizzes)}
                sub={`${progress.quizzes_passed} passed`} />
        </div>

        {/* Per-tier breakdown */}
        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-wider text-aureus-muted">Modules</h3>
          {progress.by_tier.map((t) => {
            const pct = t.total ? Math.round((t.completed / t.total) * 100) : 0;
            return (
              <div key={t.tier} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-aureus-text">{t.label}</span>
                  <span className="text-aureus-muted font-mono">{t.completed}/{t.total}</span>
                </div>
                <div className="h-1.5 rounded-full bg-aureus-rule/40 overflow-hidden">
                  <div className="h-full bg-aureus-gold transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Badges */}
        <div className="space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-aureus-muted">Skill Badges</h3>

          {earned.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {earned.map((b) => (
                <div key={b.id} className="flex items-start gap-3 rounded-lg border border-aureus-gold/40 bg-aureus-gold/[0.06] p-3">
                  <span className="text-2xl leading-none">{b.icon}</span>
                  <div>
                    <p className="text-sm text-aureus-gold font-medium">{b.name}</p>
                    <p className="text-xs text-aureus-muted mt-0.5">{b.description}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {locked.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {locked.map((b) => {
                const pct = b.progress_target ? Math.round((b.progress_current / b.progress_target) * 100) : 0;
                return (
                  <div key={b.id} className="flex items-start gap-3 rounded-lg border border-aureus-rule p-3 opacity-60">
                    <span className="text-2xl leading-none grayscale">{b.icon}</span>
                    <div className="flex-1">
                      <p className="text-sm text-aureus-text font-medium">{b.name}</p>
                      <p className="text-xs text-aureus-muted mt-0.5">{b.description}</p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <div className="flex-1 h-1 rounded-full bg-aureus-rule/40 overflow-hidden">
                          <div className="h-full bg-aureus-muted" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-[10px] text-aureus-muted font-mono">
                          {b.progress_current}/{b.progress_target}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {progress.legacy_daily_lessons_completed > 0 && (
          <p className="text-xs text-aureus-muted border-t border-aureus-rule pt-3">
            You also dismissed {progress.legacy_daily_lessons_completed} daily lesson
            {progress.legacy_daily_lessons_completed === 1 ? "" : "s"} on the dashboard before per-lesson
            tracking existed. Those aren&apos;t counted above because there&apos;s no record of which lessons they were.
          </p>
        )}
      </div>
    </div>
  );
}
