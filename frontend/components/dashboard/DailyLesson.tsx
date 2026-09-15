"use client";
import { useEffect, useState } from "react";
import { IconClose } from "@/components/ui/icons";
import { getTodaysLesson, dismissTodaysLesson } from "@/lib/api";
import type { TodaysLesson } from "@/lib/api";

const LEVEL_TONE = ["text-aureus-gold", "text-aureus-emerald", "text-aureus-text"];

export default function DailyLesson({ userId }: { userId: string }) {
  const [data, setData] = useState<TodaysLesson | null>(null);
  const [visible, setVisible] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    if (!userId) return;
    getTodaysLesson(userId)
      .then((res) => {
        setData(res);
        if (!res.already_dismissed_today) setVisible(true);
      })
      .catch(() => { /* a daily lesson is optional; never block the dashboard on it */ });
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
  const paragraphs = data.lesson.body.split("\n\n");

  return (
    <section className="border border-aureus-rule bg-aureus-panel">
      <div className="grid lg:grid-cols-[14rem_minmax(0,1fr)]">
        <div className="px-5 py-4 border-b lg:border-b-0 lg:border-r border-aureus-rule">
          <p className="label-caps">Today’s lesson</p>
          <p className={`text-[12.5px] mt-2 ${LEVEL_TONE[data.tier] ?? LEVEL_TONE[0]}`}>{data.tier_label}</p>
          <p className="text-[12px] text-aureus-muted mt-0.5">{data.lesson.category}</p>
          <p className="font-mono-num text-[11px] text-aureus-muted mt-4">{data.lessons_completed_count} completed</p>
          {data.lessons_to_next_tier != null && (
            <p className="font-mono-num text-[11px] text-aureus-muted">{data.lessons_to_next_tier} to the next level</p>
          )}
        </div>

        <div className="px-5 py-4 min-w-0">
          <div className="flex items-start justify-between gap-4">
            <h3 className="font-display text-[20px] leading-snug text-aureus-text">{data.lesson.title}</h3>
            <button onClick={handleDismiss} disabled={dismissing} aria-label="Dismiss today’s lesson"
                    className="p-1 -mr-1 text-aureus-muted hover:text-aureus-text disabled:opacity-40">
              <IconClose className="w-4 h-4" />
            </button>
          </div>

          <div className="text-[14px] text-aureus-soft leading-relaxed mt-2 max-w-[68ch] space-y-2">
            {(expanded ? paragraphs : paragraphs.slice(0, 1)).map((para, i) => <p key={i}>{para}</p>)}
          </div>

          {expanded ? (
            <div className="mt-4 pt-3 border-t border-aureus-rule max-w-[68ch]">
              <p className="label-caps text-aureus-gold">Key takeaway</p>
              <p className="text-[13.5px] text-aureus-text mt-1.5 leading-relaxed">{data.lesson.key_takeaway}</p>
            </div>
          ) : (
            <button onClick={() => setExpanded(true)} className="mt-3 text-[12.5px] text-aureus-gold hover:text-aureus-goldbright">
              Read the full lesson
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
