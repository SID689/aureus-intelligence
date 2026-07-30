"use client";
import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { getLearningLevel, setLearningLevel } from "@/lib/api";

const LEVELS = [
  { value: 0, label: "Foundational+", desc: "Assumes you've placed trades and know the basics — goes one layer deeper." },
  { value: 1, label: "Advanced",      desc: "Factor mechanics, options greeks, correlation math, market microstructure." },
  { value: 2, label: "Expert",        desc: "Institutional-grade: risk model internals, execution theory, crowding dynamics." },
];

export default function LearningLevelCard({ userId }: { userId: string }) {
  const [current,  setCurrent]  = useState<number | null>(null);
  const [completed, setCompleted] = useState(0);
  const [effective, setEffective] = useState<number | null>(null);
  const [saving,   setSaving]   = useState(false);

  useEffect(() => {
    if (!userId) return;
    getLearningLevel(userId).then((res) => {
      setCurrent(res.base_level);
      setEffective(res.effective_tier);
      setCompleted(res.lessons_completed_count);
    }).catch(() => {});
  }, [userId]);

  const handleSelect = async (level: number) => {
    setSaving(true);
    try {
      await setLearningLevel(userId, level);
      setCurrent(level);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle>Daily Lesson Difficulty</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-aureus-muted text-sm">
          Sets your starting level for the daily lesson shown on the dashboard. Your level also
          rises automatically as you read more lessons — every 15 completed lessons advances you
          one tier, on top of whatever you set here.
        </p>

        <div className="space-y-2">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              onClick={() => handleSelect(l.value)}
              disabled={saving}
              className={`w-full text-left rounded-lg border p-3 transition-colors ${
                current === l.value
                  ? "border-aureus-gold bg-aureus-gold/5"
                  : "border-aureus-rule hover:border-aureus-muted"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={current === l.value ? "text-aureus-gold font-medium text-sm" : "text-aureus-text text-sm"}>
                  {l.label}
                </span>
                {current === l.value && <span className="text-[10px] text-aureus-gold uppercase tracking-wide">Current</span>}
              </div>
              <p className="text-xs text-aureus-muted mt-1">{l.desc}</p>
            </button>
          ))}
        </div>

        {effective !== null && effective !== current && (
          <p className="text-xs text-aureus-muted font-mono">
            You're currently seeing {LEVELS[effective].label} lessons ({completed} completed have advanced you past your base level).
          </p>
        )}
      </CardContent>
    </Card>
  );
}
