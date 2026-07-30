"use client";
import { useEffect, useState } from "react";
import { X, GraduationCap, ChevronRight } from "lucide-react";
import { getTodaysLesson, dismissTodaysLesson } from "@/lib/api";
import type { TodaysLesson } from "@/lib/api";

const TIER_COLORS = ["text-aureus-gold", "text-aureus-verdigris", "text-purple-300"];

export default function DailyLesson({ userId }: { userId: string }) {
  const [data,      setData]      = useState<TodaysLesson | null>(null);
  const [visible,   setVisible]   = useState(false);
  const [expanded,  setExpanded]  = useState(false);
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    if (!userId) return;
    getTodaysLesson(userId)
      .then((res) => {
        setData(res);
        if (!res.already_dismissed_today) setVisible(true);
      })
      .catch(() => { /* fail quietly — lesson is a nice-to-have, not critical path */ });
  }, [userId]);

  const handleDismiss = async () => {
    if (!data) return;
    setDismissing(true);
    try {
      await dismissTodaysLesson(userId, data.lesson.id);
    } finally {
      setVisible(false);
      setDismissing(false);
    }
  };

  if (!visible || !data) return null;

  const tierColor = TIER_COLORS[data.tier] ?? TIER_COLORS[0];

  return (
    <div className="rounded-lg border border-aureus-rule guilloche-corner overflow-hidden"
         style={{ background: "var(--panel)" }}>
      <div className="p-4 space-y-2">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <GraduationCap className={`w-4 h-4 ${tierColor}`} strokeWidth={1.75} />
            <span className="text-[10px] uppercase tracking-widest text-aureus-muted">
              Today's Lesson · <span className={tierColor}>{data.tier_label}</span> · {data.lesson.category}
            </span>
          </div>
          <button onClick={handleDismiss} disabled={dismissing}
                  className="text-aureus-muted hover:text-aureus-text transition-colors disabled:opacity-40"
                  aria-label="Dismiss lesson">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Title */}
        <h3 className="font-display text-aureus-text text-lg" style={{ fontWeight: 600 }}>
          {data.lesson.title}
        </h3>

        {/* Body — collapsed to first paragraph until expanded */}
        <div className="text-sm text-gray-300 leading-relaxed">
          {expanded ? (
            data.lesson.body.split("\n\n").map((para, i) => (
              <p key={i} className={i > 0 ? "mt-2" : ""}>{para}</p>
            ))
          ) : (
            <p>{data.lesson.body.split("\n\n")[0]}</p>
          )}
        </div>

        {!expanded && (
          <button onClick={() => setExpanded(true)}
                  className="flex items-center gap-1 text-xs text-aureus-gold hover:underline">
            Read more <ChevronRight className="w-3 h-3" />
          </button>
        )}

        {expanded && (
          <div className="rounded border border-aureus-gold/20 bg-aureus-gold/5 p-3 mt-2">
            <span className="text-[10px] uppercase tracking-widest text-aureus-gold">Key takeaway</span>
            <p className="text-sm text-aureus-text mt-1">{data.lesson.key_takeaway}</p>
          </div>
        )}

        {/* Progress footer */}
        <div className="flex items-center justify-between text-[10px] text-aureus-muted pt-1 font-mono">
          <span>{data.lessons_completed_count} lessons completed</span>
          {data.lessons_to_next_tier != null && (
            <span>{data.lessons_to_next_tier} more to reach the next level</span>
          )}
        </div>
      </div>
    </div>
  );
}
