"use client";
import type { TileState } from "@/lib/api";

/**
 * The 6x5 letter grid.
 *
 * Flip animation: a submitted row's tiles reveal in sequence with a
 * per-column delay, which is what makes the reveal feel deliberate rather
 * than instant. The animation is CSS-only (no JS timers) so it can't drift
 * out of sync with React state or leave a tile stuck mid-flip if the
 * component re-renders while it's running.
 *
 * `prefers-reduced-motion` disables the flip — the colour still conveys
 * everything, so the animation is decoration, not information.
 */

interface Props {
  guesses: string[];
  tiles: TileState[][];
  current: string;
  maxGuesses: number;
  wordLength: number;
  shake: boolean;
}

const STATE_CLASS: Record<TileState, string> = {
  correct: "bg-aureus-verdigris border-aureus-verdigris text-white",
  present: "bg-aureus-gold border-aureus-gold text-aureus-ink",
  absent: "bg-aureus-rule/60 border-aureus-rule text-aureus-muted",
};

export default function WordGrid({ guesses, tiles, current, maxGuesses, wordLength, shake }: Props) {
  const rows = Array.from({ length: maxGuesses }, (_, r) => r);

  return (
    <>
      <style jsx>{`
        @keyframes flip {
          0% { transform: rotateX(0deg); }
          50% { transform: rotateX(90deg); }
          100% { transform: rotateX(0deg); }
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-6px); }
          40% { transform: translateX(6px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }
        .tile-flip { animation: flip 0.5s ease forwards; }
        .row-shake { animation: shake 0.4s ease; }
        @media (prefers-reduced-motion: reduce) {
          .tile-flip, .row-shake { animation: none; }
        }
      `}</style>

      <div className="grid gap-1.5 justify-center" role="grid" aria-label="FinWordle guess grid">
        {rows.map((r) => {
          const submitted = r < guesses.length;
          const isActive = r === guesses.length;
          const letters = submitted
            ? guesses[r].split("")
            : isActive
              ? current.padEnd(wordLength, " ").split("")
              : Array(wordLength).fill(" ");

          return (
            <div key={r} className={`flex gap-1.5 ${isActive && shake ? "row-shake" : ""}`} role="row">
              {letters.map((ch, c) => {
                const state = submitted ? tiles[r]?.[c] : undefined;
                const filled = ch.trim().length > 0;
                return (
                  <div
                    key={c}
                    role="gridcell"
                    aria-label={
                      submitted ? `${ch}, ${state}` : filled ? ch : "empty"
                    }
                    className={[
                      "w-12 h-12 sm:w-14 sm:h-14 flex items-center justify-center",
                      "rounded-md border-2 text-xl sm:text-2xl font-bold uppercase select-none",
                      state
                        ? STATE_CLASS[state]
                        : filled
                          ? "border-aureus-muted text-white"
                          : "border-aureus-rule text-white",
                      submitted ? "tile-flip" : "",
                    ].join(" ")}
                    style={submitted ? { animationDelay: `${c * 110}ms` } : undefined}
                  >
                    {ch.trim()}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </>
  );
}
