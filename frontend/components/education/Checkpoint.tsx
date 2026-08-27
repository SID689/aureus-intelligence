"use client";
/**
 * A single question placed mid-lesson, answered where the idea was just
 * explained rather than at the end.
 *
 * An end-of-lesson quiz tests recall of the whole; this tests
 * comprehension of the part, which is where misunderstanding actually
 * begins. Getting it wrong here costs nothing and the explanation appears
 * immediately, four paragraphs from the passage that caused the
 * confusion — not ten minutes later when the reader has forgotten which
 * bit they misread.
 *
 * Graded in the browser, deliberately. Checkpoints carry no XP, so there
 * is nothing to game by inspecting the payload, and local grading is what
 * makes the response instant.
 */
import { useState } from "react";
import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LessonCheckpoint } from "@/lib/api";

export default function Checkpoint({ checkpoint }: { checkpoint: LessonCheckpoint }) {
  const [picked, setPicked] = useState<number | null>(null);
  const answered = picked !== null;
  const correct = picked === checkpoint.correct_index;

  return (
    <aside
      className="my-7 rounded-[10px] border border-aureus-rule bg-aureus-panellift overflow-hidden"
      // Not an <article>: this interrupts the prose rather than continuing
      // it, and screen readers benefit from the distinction.
      aria-label="Comprehension checkpoint"
    >
      <div className="px-5 py-2.5 border-b border-aureus-rule flex items-center justify-between gap-3">
        <span className="label-caps">Quick check</span>
        <span className="text-[10px] text-aureus-muted">no XP · just for you</span>
      </div>

      <div className="p-5">
        <p className="text-[14px] text-aureus-text leading-relaxed">{checkpoint.question}</p>

        <div className="mt-3.5 space-y-2">
          {checkpoint.options.map((opt, i) => {
            const isPicked = picked === i;
            const isAnswer = i === checkpoint.correct_index;
            // After answering, always reveal which was right — including
            // when the reader got it right, so the reasoning still lands.
            const state = !answered ? "idle" : isAnswer ? "right" : isPicked ? "wrong" : "dim";

            return (
              <button
                key={i}
                onClick={() => !answered && setPicked(i)}
                disabled={answered}
                className={cn(
                  "w-full text-left rounded-md border px-3.5 py-2.5 text-[13px] transition-colors flex items-start gap-2.5",
                  state === "idle" &&
                    "border-aureus-rule text-aureus-soft hover:border-aureus-gold hover:text-aureus-text cursor-pointer",
                  state === "right" && "border-aureus-verdigris bg-aureus-verdigris/10 text-aureus-verdigris",
                  state === "wrong" && "border-aureus-oxblood bg-aureus-oxblood/10 text-aureus-oxblood",
                  state === "dim" && "border-aureus-rulesoft text-aureus-muted opacity-60",
                )}
              >
                <span className="pt-0.5 shrink-0 w-4">
                  {state === "right" && <Check className="w-3.5 h-3.5" strokeWidth={2.5} />}
                  {state === "wrong" && <X className="w-3.5 h-3.5" strokeWidth={2.5} />}
                </span>
                <span>{opt}</span>
              </button>
            );
          })}
        </div>

        {answered && (
          <div className="mt-4 pt-3.5 border-t border-aureus-rule rise-in">
            <span className={cn("label-caps", correct ? "text-aureus-verdigris" : "text-aureus-amber")}>
              {correct ? "Correct" : "Not quite"}
            </span>
            <p className="text-[13px] text-aureus-soft leading-relaxed mt-1.5">{checkpoint.explanation}</p>
            <button
              onClick={() => setPicked(null)}
              className="text-[11px] text-aureus-muted hover:text-aureus-gold mt-2.5 transition-colors"
            >
              Reset
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
