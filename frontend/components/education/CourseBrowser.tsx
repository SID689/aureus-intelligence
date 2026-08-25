"use client";
import { CheckCircle2, Circle, Clock, PlayCircle, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { EducationCatalog, LessonSummary } from "@/lib/api";

interface Props {
  catalog: EducationCatalog;
  onOpenLesson: (lessonId: string) => void;
}

function StatusIcon({ status }: { status: LessonSummary["status"] }) {
  if (status === "completed") return <CheckCircle2 className="w-4 h-4 text-aureus-verdigris flex-shrink-0" />;
  if (status === "in_progress") return <PlayCircle className="w-4 h-4 text-aureus-gold flex-shrink-0" />;
  return <Circle className="w-4 h-4 text-aureus-muted/50 flex-shrink-0" />;
}

function ProgressBar({ pct, tone = "gold" }: { pct: number; tone?: "gold" | "green" }) {
  return (
    <div className="h-1.5 rounded-full bg-aureus-rule/40 overflow-hidden">
      <div
        className={`h-full transition-all ${tone === "green" ? "bg-aureus-verdigris" : "bg-aureus-gold"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function CourseBrowser({ catalog, onOpenLesson }: Props) {
  return (
    <div className="space-y-5">
      {catalog.modules.map((m) => {
        const done = m.percent_complete === 100;
        return (
          <Card key={m.tier}>
            <CardContent className="p-5 space-y-4">
              {/* Module header */}
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-aureus-muted">
                    Module {m.tier}
                  </span>
                  <Badge variant={done ? "green" : "default"}>{m.difficulty_level}</Badge>
                  {done && <span className="text-xs text-aureus-verdigris">✓ Complete</span>}
                </div>
                <h2 className="text-lg font-semibold text-aureus-text">{m.label}</h2>
                <p className="text-sm text-aureus-muted leading-relaxed">{m.description}</p>

                <div className="flex flex-wrap items-center gap-4 text-xs text-aureus-muted pt-1">
                  <span>{m.lessons_completed}/{m.lesson_count} lessons</span>
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{m.estimated_minutes} min</span>
                  <span className="flex items-center gap-1 text-aureus-gold">
                    <Zap className="w-3.5 h-3.5" />{m.xp_earned}/{m.total_xp_available} XP
                  </span>
                  <span className="ml-auto font-mono">{m.percent_complete}%</span>
                </div>
                <ProgressBar pct={m.percent_complete} tone={done ? "green" : "gold"} />
              </div>

              {/* Lessons */}
              <div className="space-y-1 pt-1">
                {m.lessons.map((l) => (
                  <button
                    key={l.id}
                    onClick={() => onOpenLesson(l.id)}
                    className="w-full text-left rounded-md border border-transparent hover:border-aureus-rule
                               hover:bg-aureus-panellift px-3 py-2.5 transition-colors group"
                  >
                    <div className="flex items-start gap-3">
                      <div className="pt-0.5"><StatusIcon status={l.status} /></div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className={`text-sm truncate ${
                            l.status === "completed" ? "text-aureus-muted" : "text-aureus-text group-hover:text-aureus-gold"
                          }`}>
                            {l.title}
                          </span>
                          <span className="text-[11px] text-aureus-muted font-mono flex-shrink-0">
                            {l.estimated_read_time_minutes}m
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-aureus-muted">
                          <span>{l.category}</span>
                          {l.quiz_question_count > 0 && (
                            <span className={l.quiz_passed ? "text-aureus-verdigris" : ""}>
                              · {l.quiz_passed
                                  ? `quiz ${l.quiz_best_score}/${l.quiz_total} ✓`
                                  : `${l.quiz_question_count}-q check`}
                            </span>
                          )}
                          {l.xp_earned > 0 && <span className="text-aureus-gold">· {l.xp_earned} XP</span>}
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
