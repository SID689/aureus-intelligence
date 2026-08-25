"use client";
import { useState } from "react";
import { X, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { FinWordleSession } from "@/lib/api";

/**
 * Post-game educational deep-dive. This is the actual point of the game —
 * the puzzle is the hook, the definition is the payload — so it shows on a
 * LOSS as well as a win, and leads with the teaching rather than the score.
 */

interface Props {
  session: FinWordleSession;
  currentStreak: number;
  onClose: () => void;
  onPlayPractice: () => void;
}

export default function ResultModal({ session, currentStreak, onClose, onPlayPractice }: Props) {
  const [copied, setCopied] = useState(false);
  const edu = session.education;
  const won = session.status === "won";

  const shareText = [
    `Aureus FinWordle ${session.puzzle_number != null ? `#${session.puzzle_number}` : "Practice"}`,
    `${won ? session.guesses_used : "X"}/${session.max_guesses}`,
    "",
    session.emoji_grid ?? "",
  ].join("\n");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div className="w-full max-w-lg max-h-[88vh] overflow-y-auto rounded-xl border border-aureus-rule p-6 space-y-5"
           style={{ background: "var(--panel)" }}
           onClick={(e) => e.stopPropagation()}>

        <div className="flex items-start justify-between">
          <div>
            <p className={`text-sm font-semibold ${won ? "text-aureus-verdigris" : "text-aureus-gold"}`}>
              {won ? `Solved in ${session.guesses_used}/${session.max_guesses}` : "Out of guesses"}
            </p>
            <h2 className="font-display text-3xl text-aureus-gold tracking-wide mt-1" style={{ fontWeight: 600 }}>
              {session.answer}
            </h2>
            {edu && <Badge variant="muted" className="mt-2">{edu.category}</Badge>}
          </div>
          <button onClick={onClose} className="text-aureus-muted hover:text-aureus-text transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {edu && (
          <div className="space-y-3">
            <section>
              <h3 className="text-[10px] uppercase tracking-wider text-aureus-muted mb-1">Definition</h3>
              <p className="text-sm text-aureus-text leading-relaxed">{edu.definition}</p>
            </section>
            <section className="rounded-lg border-l-2 border-aureus-gold bg-aureus-gold/[0.05] px-3 py-2.5">
              <h3 className="text-[10px] uppercase tracking-wider text-aureus-gold mb-1">Where You Meet It</h3>
              <p className="text-sm text-aureus-text leading-relaxed">{edu.trading_context}</p>
            </section>
            <section className="rounded-lg border-l-2 border-aureus-amber bg-aureus-amber/10 px-3 py-2.5">
              <h3 className="text-[10px] uppercase tracking-wider text-aureus-amber mb-1">Real-World Example</h3>
              <p className="text-sm text-aureus-text leading-relaxed">{edu.example}</p>
            </section>
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 py-1">
          {[
            { label: "Result", value: won ? `${session.guesses_used}/${session.max_guesses}` : "X" },
            { label: "Streak", value: String(currentStreak) },
            { label: "Score", value: `+${session.score_awarded}` },
          ].map((s) => (
            <div key={s.label} className="rounded-lg border border-aureus-rule p-2.5 text-center"
                 style={{ background: "var(--bg)" }}>
              <div className="text-[10px] uppercase tracking-wider text-aureus-muted">{s.label}</div>
              <div className="text-lg font-semibold text-aureus-text mt-0.5">{s.value}</div>
            </div>
          ))}
        </div>

        {session.emoji_grid && (
          <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
            <pre className="text-center text-base leading-tight font-sans">{session.emoji_grid}</pre>
          </div>
        )}

        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={handleCopy}>
            {copied ? <><Check className="w-4 h-4 mr-2" />Copied</> : <><Copy className="w-4 h-4 mr-2" />Share Result</>}
          </Button>
          <Button className="flex-1" onClick={onPlayPractice}>Practice Round</Button>
        </div>

        <p className="text-xs text-aureus-muted">
          Educational content only · Not financial advice
        </p>
      </div>
    </div>
  );
}
