"use client";
/**
 * The command surface, behind Cmd-K.
 *
 * A terminal is operated by typing at it, so the fast path through this
 * app is a prompt rather than a pointer. Three things answer here:
 *
 *   a destination   "lead" -> Leaderboard, and so does "03"
 *   a ticker        "NVDA" -> run the analysis, which is the single
 *                   most common thing anyone does on this platform and
 *                   previously took a page load and a form
 *   an account action  settings, sign out
 *
 * Matching is substring over the label, the figure and a short keyword
 * list, scored so that a prefix beats a mid-word hit. Nothing fuzzier:
 * on a list of eight destinations, edit distance mostly produces
 * surprises, and a wrong jump costs more than a second attempt.
 *
 * Locked destinations stay in the list and say which plan they need.
 * Hiding them would make the palette quietly disagree with the function
 * row, and someone searching for a feature deserves to learn it exists.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { IconArrowRight, IconLock, IconLogout, IconSearch } from "@/components/ui/icons";
import { DESTINATIONS, asTickerQuery, lockedHref } from "@/lib/navigation";
import { TIER_LABEL, meetsTier } from "@/lib/tiers";
import type { TierName } from "@/types";

type Row = {
  key: string;
  figure: string;
  label: string;
  hint: string;
  /** Small caps note on the right, e.g. the plan a locked destination needs. */
  tag?: string;
  locked?: boolean;
  run: () => void;
};

export default function CommandPalette({
  open,
  onClose,
  tier,
}: {
  open: boolean;
  onClose: () => void;
  tier: TierName;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Each opening starts clean. A palette that remembers the last query
  // makes the second use a correction rather than a fresh thought.
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setCursor(0);
    // The input mounts with the overlay, so focus has to wait a frame.
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  const go = useCallback((href: string) => {
    onClose();
    router.push(href);
  }, [onClose, router]);

  const rows = useMemo<Row[]>(() => {
    const q = query.trim().toLowerCase();
    const out: Row[] = [];

    const ticker = asTickerQuery(query);
    if (ticker) {
      out.push({
        key: `analyse:${ticker}`,
        figure: "->",
        label: `Analyse ${ticker}`,
        hint: "Run all three pillars on this ticker",
        run: () => go(`/analysis/${ticker}`),
      });
    }

    const scored = DESTINATIONS.map((d) => {
      const label = d.label.toLowerCase();
      const hay = [label, d.figure, ...(d.keywords ?? [])];
      let score = -1;
      if (!q) score = 0;
      else if (label.startsWith(q) || d.figure === q) score = 3;
      else if (hay.some((h) => h.startsWith(q))) score = 2;
      else if (hay.some((h) => h.includes(q))) score = 1;
      return { d, score };
    })
      .filter((s) => s.score >= 0)
      .sort((a, b) => b.score - a.score);

    for (const { d } of scored) {
      const locked = !!d.tier && !meetsTier(tier, d.tier);
      out.push({
        key: d.href,
        figure: d.figure,
        label: d.label,
        hint: d.note,
        tag: locked ? TIER_LABEL[d.tier!] : undefined,
        locked,
        run: () => go(locked ? lockedHref(d) : d.href),
      });
    }

    const actions: Row[] = [
      { key: "settings", figure: "··", label: "Settings", hint: "Plan, usage, API keys", run: () => go("/settings") },
      { key: "upgrade", figure: "··", label: "Plans", hint: "Compare what each plan includes", run: () => go("/upgrade") },
      {
        key: "signout", figure: "··", label: "Sign out", hint: "End this session",
        run: () => { onClose(); void signOut({ callbackUrl: "/welcome" }); },
      },
    ];
    for (const a of actions) {
      if (!q || a.label.toLowerCase().includes(q)) out.push(a);
    }

    return out;
  }, [query, tier, go, onClose]);

  // The cursor is an index into a list that changes on every keystroke,
  // so it is clamped rather than preserved.
  useEffect(() => { setCursor(0); }, [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, rows.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
      if (e.key === "Enter") { e.preventDefault(); rows[cursor]?.run(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, rows, cursor, onClose]);

  // Keep the highlighted row in view when arrowing past the fold.
  useEffect(() => {
    listRef.current?.children[cursor]?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/80 px-4 pt-[12vh]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="w-full max-w-xl border border-aureus-rule bg-aureus-panel shadow-overlay"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 border-b border-aureus-rule">
          <IconSearch className="w-4 h-4 text-aureus-muted shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Go to a page, or type a ticker to analyse it"
            aria-label="Search destinations and tickers"
            spellCheck={false}
            autoComplete="off"
            className="flex-1 bg-transparent py-4 text-[15px] text-aureus-text placeholder:text-aureus-muted/70 focus:outline-none"
          />
          <kbd className="hidden sm:block label-caps text-[9px] border border-aureus-rule px-1.5 py-1 text-aureus-muted">
            Esc
          </kbd>
        </div>

        {rows.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-aureus-muted">
            Nothing matches that. Try a page name, a two-digit number, or a ticker.
          </p>
        ) : (
          <ul ref={listRef} className="max-h-[52vh] overflow-y-auto py-1" role="listbox">
            {rows.map((row, i) => (
              <li key={row.key} role="option" aria-selected={i === cursor}>
                <button
                  onMouseEnter={() => setCursor(i)}
                  onClick={row.run}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                    i === cursor ? "bg-aureus-panelhigh" : "hover:bg-aureus-panellift",
                  )}
                >
                  <span
                    className={cn(
                      "w-[22px] h-[22px] shrink-0 grid place-items-center rounded-sm border font-mono-num text-[10px] leading-none",
                      i === cursor
                        ? "border-aureus-gold text-aureus-gold"
                        : "border-aureus-rule text-aureus-muted",
                    )}
                  >
                    {row.figure}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className={cn("block text-[13.5px] truncate", row.locked ? "text-aureus-muted" : "text-aureus-text")}>
                      {row.label}
                    </span>
                    <span className="block text-[11.5px] text-aureus-muted truncate">{row.hint}</span>
                  </span>

                  {row.tag ? (
                    <span className="shrink-0 flex items-center gap-1.5 label-caps text-[9px] text-aureus-golddim">
                      <IconLock className="w-3 h-3" />
                      {row.tag}
                    </span>
                  ) : row.key === "signout" ? (
                    <IconLogout className="w-3.5 h-3.5 shrink-0 text-aureus-muted" />
                  ) : i === cursor ? (
                    <IconArrowRight className="w-3.5 h-3.5 shrink-0 text-aureus-gold" />
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex items-center gap-4 px-4 py-2 border-t border-aureus-rule label-caps text-[9px]">
          <span>↑ ↓ to move</span>
          <span>Enter to open</span>
          <span className="ml-auto hidden sm:block">Type a ticker to analyse it</span>
        </div>
      </div>
    </div>
  );
}
