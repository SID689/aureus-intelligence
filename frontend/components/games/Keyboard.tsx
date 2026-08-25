"use client";
import { useEffect } from "react";
import { Delete } from "lucide-react";
import type { TileState } from "@/lib/api";

/**
 * On-screen keyboard, colour-coded by best-known state per letter.
 *
 * Also owns the PHYSICAL keyboard listener. Putting it here rather than in
 * the page keeps the two input paths on one code path — if they were wired
 * separately they'd inevitably drift (a guard added to one and forgotten on
 * the other), which is how "typing works but tapping doesn't" bugs happen.
 */

const ROWS = [
  "QWERTYUIOP".split(""),
  "ASDFGHJKL".split(""),
  ["ENTER", ..."ZXCVBNM".split(""), "BACK"],
];

const STATE_CLASS: Record<TileState, string> = {
  correct: "bg-aureus-verdigris text-aureus-text border-aureus-verdigris",
  present: "bg-aureus-gold text-aureus-ink border-aureus-gold",
  absent: "bg-aureus-rule/40 text-aureus-muted/60 border-transparent",
};

interface Props {
  keyStates: Record<string, TileState>;
  onKey: (key: string) => void;
  disabled: boolean;
}

export default function Keyboard({ keyStates, onKey, disabled }: Props) {
  useEffect(() => {
    if (disabled) return;
    const handler = (e: KeyboardEvent) => {
      // Don't hijack typing in a real input, or browser/OS shortcuts.
      const el = document.activeElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "Enter") { onKey("ENTER"); return; }
      if (e.key === "Backspace") { onKey("BACK"); return; }
      const k = e.key.toUpperCase();
      if (k.length === 1 && k >= "A" && k <= "Z") onKey(k);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onKey, disabled]);

  return (
    <div className="space-y-1.5 select-none">
      {ROWS.map((row, i) => (
        <div key={i} className="flex justify-center gap-1.5">
          {row.map((k) => {
            const wide = k === "ENTER" || k === "BACK";
            const state = keyStates[k];
            return (
              <button
                key={k}
                type="button"
                disabled={disabled}
                onClick={() => onKey(k)}
                aria-label={k === "BACK" ? "Backspace" : k}
                className={[
                  "h-11 sm:h-12 rounded-md border text-xs sm:text-sm font-semibold uppercase",
                  "transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
                  wide ? "px-2.5 sm:px-3.5 min-w-[3.5rem]" : "w-8 sm:w-10",
                  state
                    ? STATE_CLASS[state]
                    : "bg-aureus-rule/20 border-aureus-rule text-aureus-text hover:bg-aureus-rule/40",
                ].join(" ")}
              >
                {k === "BACK" ? <Delete className="w-4 h-4 mx-auto" /> : k}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
