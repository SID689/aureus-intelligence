"use client";
/**
 * The Tape design system, as components.
 *
 * These are the parts the whole platform is built from. Three rules they
 * all follow, and that anything new should follow too:
 *
 *   1. Rules divide space; boxes enclose objects. A section heading draws
 *      a hairline to the edge (`RuledLabel`) rather than wrapping its
 *      content in another bordered rectangle. Reserve `Sheet` for things
 *      that really are discrete objects.
 *   2. Every figure is tabular (`Figure`). Digits must not shift width as
 *      values update.
 *   3. Colour means direction. Verdigris is up, oxblood is down, gold
 *      means "you can act on this". Nothing is coloured for decoration.
 */
import * as React from "react";
import { useEffect, useId, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { clockTime, seriesColor, signed, type Tone } from "@/lib/format";

// ── Type ────────────────────────────────────────────────────────────────

const TONE_CLASS: Record<Tone, string> = {
  up:    "text-aureus-verdigris",
  down:  "text-aureus-oxblood",
  flat:  "text-aureus-text",
  muted: "text-aureus-muted",
};

/** A tabular figure. Everything numeric on the platform goes through this. */
export function Figure({
  children, tone = "flat", className, ...rest
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span className={cn("font-mono-num", TONE_CLASS[tone], className)} {...rest}>
      {children}
    </span>
  );
}

/**
 * Small-caps label with a hairline running to the far edge. This is the
 * platform's primary way of dividing a page — used in place of a card
 * header wherever the content below isn't a discrete object.
 */
export function RuledLabel({
  children, right, className,
}: {
  children: React.ReactNode; right?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-x-3 gap-y-1.5 flex-wrap", className)}>
      <span className="label-caps">{children}</span>
      {/* min-w-[2rem] keeps the rule visible when the row wraps; without a
          floor, flex-1 collapses it to nothing on the wrapped line. */}
      <span className="flex-1 min-w-[2rem] h-px bg-aureus-rule" />
      {right}
    </div>
  );
}

/** Section label with no rule, for use inside a Sheet that has its own edges. */
export function CapsLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("label-caps", className)}>{children}</span>;
}

/**
 * Every page opens the same way: a serif title, one line of lead saying
 * what the page is for, actions on the right. Consistency here is what
 * makes a set of screens feel like one product rather than seven.
 */
export function PageHeader({
  title, lead, actions, meta,
}: {
  title: React.ReactNode; lead?: React.ReactNode;
  actions?: React.ReactNode; meta?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <h1 className="font-display text-[28px] leading-none text-aureus-text">{title}</h1>
        {lead && <p className="text-[13px] text-aureus-muted mt-2.5 leading-relaxed max-w-2xl">{lead}</p>}
        {meta && <div className="mt-2.5">{meta}</div>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

// ── Form controls ───────────────────────────────────────────────────────

/** Inputs sit on the page ground, not the sheet, so they read as wells. */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-md border border-aureus-rule bg-aureus-ink px-3 py-2 text-sm text-aureus-text",
        "placeholder:text-aureus-muted/60 focus:outline-none focus:border-aureus-gold transition-colors",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "w-full rounded-md border border-aureus-rule bg-aureus-ink px-3 py-2 text-sm text-aureus-text",
        "focus:outline-none focus:border-aureus-gold transition-colors",
        className
      )}
      {...props}
    />
  )
);
Select.displayName = "Select";

export function Field({
  label, hint, children,
}: {
  label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="label-caps block mb-1.5">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-aureus-muted mt-1">{hint}</span>}
    </label>
  );
}

/** Inline error, in oxblood rather than a raw red. */
export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-aureus-oxblooddim bg-aureus-oxblood/10 px-4 py-3 text-[13px] text-aureus-oxblood leading-relaxed">
      {children}
    </div>
  );
}

/** Standing informational note — used for disclaimers and provenance. */
export function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-aureus-rule bg-aureus-panellift px-4 py-3 text-[12px] text-aureus-muted leading-relaxed">
      {children}
    </div>
  );
}

// ── Surfaces ────────────────────────────────────────────────────────────

export function Sheet({
  className, lift = false, accent = false, ...rest
}: React.HTMLAttributes<HTMLDivElement> & { lift?: boolean; accent?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-[10px] border border-aureus-rule bg-aureus-panel",
        lift && "border-t-aureus-golddim shadow-lift",
        accent && "guilloche-corner",
        className
      )}
      {...rest}
    />
  );
}

/**
 * Row of figures divided by vertical hairlines rather than rendered as
 * separate bordered cards. The four-identical-stat-cards row is the most
 * recognisable "generated dashboard" pattern there is; this says the same
 * thing without it.
 */
export function StatColumns({
  items, className,
}: {
  items: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: Tone }[];
  className?: string;
}) {
  // Flex rather than grid, because the column count is dynamic and
  // Tailwind cannot generate `sm:grid-cols-${n}` from a runtime value.
  // Below `sm` these stack: three columns inside 375px clipped both the
  // label ("Return on co…") and the figure, which is the one thing a
  // figure must never do.
  return (
    <div className={cn("flex flex-col sm:flex-row", className)}>
      {items.map((it, i) => (
        <div
          key={it.label}
          className={cn(
            "flex-1 px-5 py-4 min-w-0",
            i > 0 && "border-t sm:border-t-0 sm:border-l border-aureus-rule"
          )}
        >
          <CapsLabel>{it.label}</CapsLabel>
          <Figure tone={it.tone ?? "flat"} className="block text-xl mt-1.5 truncate">
            {it.value}
          </Figure>
          {it.sub && <div className="text-[11px] text-aureus-muted mt-1 truncate">{it.sub}</div>}
        </div>
      ))}
    </div>
  );
}

/** Label / value line with a hairline above. The building block of every
 *  "composition" or "key figures" list on the platform. */
export function DataRow({
  label, sub, value, tone = "flat", first = false,
}: {
  label: React.ReactNode; sub?: React.ReactNode; value: React.ReactNode;
  tone?: Tone; first?: boolean;
}) {
  return (
    <div className={cn("flex items-baseline justify-between gap-6 py-2.5", !first && "border-t border-aureus-rulesoft")}>
      <div className="min-w-0">
        <div className="text-[13px] text-aureus-soft">{label}</div>
        {sub && <div className="text-[11px] text-aureus-muted mt-0.5">{sub}</div>}
      </div>
      <Figure tone={tone} className="text-sm shrink-0">{value}</Figure>
    </div>
  );
}

// ── Status ──────────────────────────────────────────────────────────────

export function StatusDot({ on, className }: { on: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "inline-block w-1.5 h-1.5 rounded-full shrink-0",
        on ? "bg-aureus-verdigris pulse-gold" : "bg-aureus-muted",
        className
      )}
    />
  );
}

/**
 * Empty states. Replaces the 📡 / 📰 emoji blocks — an emoji standing in
 * for an icon is the loudest "generated" tell in a product that otherwise
 * sets its numbers in tabular monospace.
 */
export function EmptyState({
  icon: Icon, title, children, action,
}: {
  icon?: LucideIcon;
  title: string; children?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center text-center px-6 py-12">
      {Icon && (
        <span className="mb-3 w-9 h-9 rounded-full border border-aureus-rule flex items-center justify-center">
          <Icon className="w-4 h-4 text-aureus-muted" strokeWidth={1.5} />
        </span>
      )}
      <p className="text-aureus-soft text-sm font-medium">{title}</p>
      {children && <p className="text-aureus-muted text-[13px] mt-1.5 max-w-sm leading-relaxed">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── Bars ────────────────────────────────────────────────────────────────

/** Inline proportional bar, drawn in the table row it describes. */
export function WeightBar({ value, max, className }: { value: number; max: number; className?: string }) {
  return (
    <span className={cn("block h-1 rounded-sm overflow-hidden bg-aureus-panelhigh", className)}>
      <span
        className="block h-full bg-aureus-gold"
        style={{ width: `${Math.max(0, Math.min(100, (value / (max || 1)) * 100))}%` }}
      />
    </span>
  );
}

/**
 * A whole composition as one segmented bar. Replaces the donut: a pie
 * plus its legend spends 160×160 pixels saying what an 8-pixel bar says
 * more precisely, and the old donut's blue/purple/pink shared no hue with
 * anything else on the page.
 */
export function SegmentedBar({
  segments, className,
}: {
  segments: { label: string; value: number }[]; className?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex h-2.5 rounded-sm overflow-hidden bg-aureus-panelhigh">
        {segments.map((s, i) => (
          <span
            key={s.label}
            title={`${s.label} — ${s.value.toFixed(1)}%`}
            style={{ width: `${(s.value / total) * 100}%`, background: seriesColor(i) }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1.5">
        {segments.map((s, i) => (
          <span key={s.label} className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: seriesColor(i) }} />
            <span className="text-aureus-soft">{s.label}</span>
            <Figure tone="muted" className="text-[11px]">{s.value.toFixed(1)}%</Figure>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Horizontal score meter, 0–100, coloured by band. */
export function ScoreMeter({ score, className }: { score: number; className?: string }) {
  const tone = score >= 60 ? "bg-aureus-verdigris" : score >= 40 ? "bg-aureus-gold" : "bg-aureus-oxblood";
  return (
    <span className={cn("block h-1.5 rounded-sm overflow-hidden bg-aureus-panelhigh", className)}>
      <span className={cn("block h-full transition-all duration-500", tone)}
            style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
    </span>
  );
}

// ── Sparkline ───────────────────────────────────────────────────────────

/**
 * Hand-rolled rather than another charting instance: a sparkline has no
 * axes, tooltip or legend, so the whole thing is one path command and it
 * paints immediately instead of waiting on a chart library to mount.
 */
export function Sparkline({
  values, tone = "up", width = 140, height = 34, fill = true, className,
}: {
  values: number[]; tone?: "up" | "down" | "gold";
  width?: number; height?: number; fill?: boolean; className?: string;
}) {
  const id = useId();
  const color = tone === "up" ? "var(--verdigris)" : tone === "down" ? "var(--oxblood)" : "var(--gold)";
  if (values.length < 2) return <svg width={width} height={height} aria-hidden className={className} />;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const pt = (v: number, i: number) => [i * step, height - ((v - min) / span) * (height - 2) - 1];
  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${pt(v, i).map((n) => n.toFixed(1)).join(",")}`).join(" ");

  return (
    <svg width={width} height={height} aria-hidden className={className} style={{ display: "block" }}>
      <defs>
        <linearGradient id={`sk-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      {fill && <path d={`${line} L${width},${height} L0,${height} Z`} fill={`url(#sk-${id})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth={1.25} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── The wire ────────────────────────────────────────────────────────────

export interface WireItem {
  id: string;
  ticker?: string;
  headline: string;
  source?: string;
  href?: string;
  at?: string | null;
  score?: number;
  tone?: Tone;
}

/**
 * News and alerts, as a list with timestamps hanging in a left gutter —
 * the newspaper convention — instead of one bordered card per headline.
 * Twelve stacked cards is a wall; twelve hanging entries is a column you
 * can actually scan.
 */
export function Wire({ items, empty }: { items: WireItem[]; empty?: React.ReactNode }) {
  if (!items.length) return <>{empty}</>;
  return (
    <div>
      {items.map((it, i) => {
        const Row = it.href ? "a" : "div";
        return (
          <Row
            key={it.id}
            {...(it.href ? { href: it.href, target: "_blank", rel: "noopener noreferrer" } : {})}
            className={cn(
              "grid grid-cols-[3.25rem_1fr] gap-3 py-3 group",
              i > 0 && "border-t border-aureus-rulesoft",
              it.href && "cursor-pointer"
            )}
          >
            <Figure tone="muted" className="text-[10px] pt-0.5">{clockTime(it.at)}</Figure>
            <div className="min-w-0">
              {(it.ticker || it.score != null) && (
                <div className="flex items-center gap-2 mb-1">
                  {it.ticker && <Figure className="text-[10px] text-aureus-gold">{it.ticker}</Figure>}
                  {it.score != null && (
                    <Figure tone={it.tone ?? "muted"} className="text-[10px]">{signed(it.score)}</Figure>
                  )}
                </div>
              )}
              <p className={cn("text-[13px] leading-snug text-aureus-soft", it.href && "group-hover:text-aureus-text group-hover:underline")}>
                {it.headline}
              </p>
              {it.source && <p className="text-[11px] text-aureus-muted mt-1">{it.source}</p>}
            </div>
          </Row>
        );
      })}
    </div>
  );
}

// ── The tape ────────────────────────────────────────────────────────────

export interface TapeItem {
  ticker: string;
  price: number | null;
  changePct: number | null;
}

/**
 * The scrolling price strip above every dashboard page. It is the one
 * element that says "financial software" before a word has been read.
 *
 * The list is rendered twice: the track is 2× the content width, so
 * translating it -50% lands exactly on the start of the second copy and
 * the loop has no seam. Hover pauses it, and prefers-reduced-motion stops
 * it outright (see globals.css).
 */
export function TickerTape({ items, note }: { items: TapeItem[]; note?: string }) {
  if (!items.length) {
    return (
      <div className="border-b border-aureus-rule bg-aureus-panel">
        <div className="px-6 py-2 text-[11px] text-aureus-muted">
          {note ?? "Tape is empty — add a position and it starts running."}
        </div>
      </div>
    );
  }
  const doubled = [...items, ...items];
  return (
    <div className="tape overflow-hidden border-b border-aureus-rule bg-aureus-panel">
      <div className="tape-track flex whitespace-nowrap py-2">
        {doubled.map((it, i) => (
          <span key={`${it.ticker}-${i}`} className="flex items-baseline gap-2 px-5 border-r border-aureus-rulesoft">
            <span className="text-[11px] font-medium tracking-wide text-aureus-text">{it.ticker}</span>
            <Figure tone="muted" className="text-[11px]">
              {it.price != null ? it.price.toFixed(2) : "—"}
            </Figure>
            {it.changePct != null && (
              <Figure tone={it.changePct >= 0 ? "up" : "down"} className="text-[11px]">
                {signed(it.changePct)}%
              </Figure>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Tabs ────────────────────────────────────────────────────────────────

/** Compact segmented control. Used for tickers, horizons, feed switches. */
export function Segmented<T extends string>({
  options, value, onChange, size = "sm", className,
}: {
  options: { value: T; label: React.ReactNode }[];
  value: T; onChange: (v: T) => void;
  size?: "sm" | "md"; className?: string;
}) {
  return (
    <div className={cn("inline-flex gap-1 p-0.5 rounded-md bg-aureus-panellift", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded font-mono-num transition-colors",
            size === "sm" ? "px-2 py-1 text-[11px]" : "px-3 py-1.5 text-xs",
            o.value === value
              ? "bg-aureus-gold text-aureus-ink font-semibold"
              : "text-aureus-muted hover:text-aureus-text"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Hooks ───────────────────────────────────────────────────────────────

/**
 * Ticks once a minute. Starts null and fills in after mount on purpose:
 * rendering `new Date()` during SSR and again on the client produces two
 * different strings and React logs a hydration mismatch for each one.
 * Pair with `useMounted()` to render a blank until the client value lands.
 */
export function useClock(intervalMs = 60_000): Date {
  const [now, setNow] = useState<Date | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    setNow(new Date());
    timer.current = setInterval(() => setNow(new Date()), intervalMs);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [intervalMs]);
  return now ?? new Date(0);
}

export function useMounted(): boolean {
  const [m, setM] = useState(false);
  useEffect(() => setM(true), []);
  return m;
}
