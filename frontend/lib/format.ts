/**
 * Number, money and time formatting for the whole platform.
 *
 * Centralised because inconsistency here is the fastest way to make a
 * finance product feel amateur: one panel showing "+1,240.5" beside
 * another showing "1240.50" reads as two different applications. Every
 * figure the user sees should come through one of these.
 *
 * Note the minus sign. These use U+2212 MINUS SIGN, not the hyphen on
 * your keyboard — in a tabular monospace column a hyphen is visibly
 * narrower and shorter than the plus it aligns against.
 */

const MINUS = "−";

export function money(n: number, digits = 0): string {
  return `$${n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

/** Compact form for headline figures: $1.24M rather than $1,238,411. */
export function moneyCompact(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? MINUS : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${money(abs)}`;
}

export function price(n: number | null | undefined): string {
  return n == null ? "—" : `$${n.toFixed(2)}`;
}

export function signed(n: number, digits = 2): string {
  return `${n >= 0 ? "+" : MINUS}${Math.abs(n).toFixed(digits)}`;
}

export function signedPct(n: number, digits = 2): string {
  return `${signed(n, digits)}%`;
}

export function signedMoney(n: number): string {
  return `${n >= 0 ? "+" : MINUS}${money(Math.abs(n))}`;
}

export function compactNumber(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

/** "4:12 PM" — the hanging-timestamp gutter used by every news list. */
export function clockTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function shortDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** "3m ago" / "2h ago" / "Tue" — for feeds where exact time is noise. */
export function relativeTime(iso?: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const mins = Math.floor((Date.now() - then) / 60_000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return shortDate(iso);
}

export type Tone = "up" | "down" | "flat" | "muted";

export function toneOf(n: number | null | undefined, deadband = 0): Tone {
  if (n == null) return "muted";
  if (n > deadband) return "up";
  if (n < -deadband) return "down";
  return "flat";
}

/** Sentiment has a genuine neutral band; a raw sign test would paint
 *  a score of 0.02 green and imply a signal that isn't there. */
export function sentimentTone(score: number | null | undefined): Tone {
  return toneOf(score, 0.15);
}

/**
 * US equities regular session, expressed in the reader's own clock.
 * A dashboard that says "Live" at 2am on a Sunday tells the user, very
 * efficiently, that the status light is decorative.
 *
 * Regular hours only — this does not know about market holidays, so it
 * says "Market open" on Thanksgiving. Wiring a holiday calendar in is a
 * backend job; the label is honest about weekends and clock time, which
 * is what it claims to cover.
 */
export function marketPhase(now: Date = new Date()): { label: string; open: boolean } {
  const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  const day = et.getDay();
  const mins = et.getHours() * 60 + et.getMinutes();
  if (day === 0 || day === 6) return { label: "Market closed · weekend", open: false };
  if (mins < 4 * 60) return { label: "Market closed", open: false };
  if (mins < 9 * 60 + 30) return { label: "Pre-market", open: false };
  if (mins < 16 * 60) return { label: "Market open", open: true };
  if (mins < 20 * 60) return { label: "After hours", open: false };
  return { label: "Market closed", open: false };
}

/** First sentence, for teasers that must not run past their box. */
export function firstSentence(text: string, max = 200): string {
  const flat = (text || "").replace(/\s+/g, " ").trim();
  if (!flat) return "";
  const stop = flat.search(/[.!?](\s|$)/);
  if (stop > 40 && stop < max) return flat.slice(0, stop + 1);
  if (flat.length <= max) return flat;
  return `${flat.slice(0, max).trimEnd()}…`;
}

/** Categorical series colour, matching --series-N in globals.css. */
export const SERIES = [
  "#d9b478", "#83bda2", "#a8894f", "#5f8f7c",
  "#c0a577", "#4d7a67", "#8a7145", "#6f9f8c",
];

export function seriesColor(i: number): string {
  return SERIES[i % SERIES.length];
}
