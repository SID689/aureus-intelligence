/**
 * Skeleton loaders.
 *
 * A page that renders a centred "Loading…" and then snaps into a full
 * layout makes the reader wait twice: once for the data, and again to find
 * their place when everything moves. These hold the shape of what is
 * coming (the same rules, columns and figure positions) so data lands in
 * place instead of arriving.
 *
 * Deliberately plain: flat panel-coloured bars that breathe in luminance.
 * No sweeping gradient sheen. Motion stops entirely under
 * prefers-reduced-motion (see .skeleton in globals.css).
 *
 * No "use client", so these render from server components and from the
 * route-level loading.tsx files as well.
 */
import * as React from "react";
import { cn } from "@/lib/utils";

/** The atom. Size it with width/height classes. */
export function Skeleton({
  className, delay = 0, style,
}: { className?: string; delay?: number; style?: React.CSSProperties }) {
  return (
    <span
      aria-hidden
      className={cn("skeleton block bg-aureus-panelhigh", className)}
      style={{ animationDelay: `${delay}ms`, ...style }}
    />
  );
}

/**
 * Announces loading to assistive technology once, while the bars inside
 * stay silent. Wrap every composite skeleton in one of these.
 */
export function LoadingRegion({
  label, className, children,
}: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

const LINE_WIDTHS = ["100%", "94%", "86%", "97%", "72%", "90%", "64%"];

/** A paragraph. The last line runs short, the way real text does. */
export function SkeletonLines({
  lines = 3, className, lineClassName = "h-2.5",
}: { lines?: number; className?: string; lineClassName?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          delay={i * 70}
          className={lineClassName}
          style={{ width: i === lines - 1 && lines > 1 ? "58%" : LINE_WIDTHS[i % LINE_WIDTHS.length] }}
        />
      ))}
    </div>
  );
}

/** A caps label over a figure, the unit every stat row is built from. */
export function SkeletonFigure({ className, delay = 0 }: { className?: string; delay?: number }) {
  return (
    <div className={cn("space-y-2", className)}>
      <Skeleton className="h-2 w-16" delay={delay} />
      <Skeleton className="h-5 w-24" delay={delay + 60} />
    </div>
  );
}

/** Mirrors StatColumns: figures divided by hairlines. */
export function SkeletonStatColumns({ columns = 3, className }: { columns?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col sm:flex-row", className)}>
      {Array.from({ length: columns }, (_, i) => (
        <div key={i} className={cn("flex-1 px-5 py-4", i > 0 && "border-t sm:border-t-0 sm:border-l border-aureus-rule")}>
          <SkeletonFigure delay={i * 90} />
        </div>
      ))}
    </div>
  );
}

/**
 * A ledger. `columns` are relative widths, so a skeleton can match the
 * real table's proportions: a narrow rank, a wide name, figures right.
 */
export function SkeletonTable({
  rows = 6, columns = [1, 4, 2, 2, 3], className, header = true,
}: { rows?: number; columns?: number[]; className?: string; header?: boolean }) {
  const template = columns.map((c) => `${c}fr`).join(" ");
  return (
    <div className={className}>
      {header && (
        <div className="grid gap-4 px-4 py-2.5 border-b border-aureus-rule" style={{ gridTemplateColumns: template }}>
          {columns.map((_, i) => <Skeleton key={i} className="h-2 w-3/5" delay={i * 40} />)}
        </div>
      )}
      {Array.from({ length: rows }, (_, r) => (
        <div
          key={r}
          className="grid gap-4 items-center px-4 py-3.5 border-b border-aureus-rulesoft"
          style={{ gridTemplateColumns: template }}
        >
          {columns.map((_, c) => (
            <Skeleton
              key={c}
              delay={r * 60 + c * 30}
              className={c === 1 ? "h-3" : "h-2.5"}
              style={{ width: c === 1 ? `${62 + ((r * 13) % 30)}%` : `${48 + ((r * 7 + c * 11) % 40)}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** A chart well: axis rules and a baseline, no invented data. */
export function SkeletonChart({ height = 260, className }: { height?: number; className?: string }) {
  return (
    <div className={cn("relative", className)} style={{ height }}>
      {[0.2, 0.45, 0.7].map((t) => (
        <span key={t} className="absolute left-0 right-0 h-px bg-aureus-rulesoft" style={{ top: `${t * 100}%` }} />
      ))}
      <span className="absolute left-0 right-0 bottom-6 h-px bg-aureus-rule" />
      <Skeleton className="absolute left-0 right-0 bottom-6 top-[12%] opacity-40" />
      <div className="absolute left-0 right-0 bottom-0 flex justify-between">
        {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-2 w-8" delay={i * 50} />)}
      </div>
    </div>
  );
}

/** A feed or list: a short leading gutter and two lines per entry. */
export function SkeletonList({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={className}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={cn("grid grid-cols-[3.25rem_1fr] gap-3 py-3", i > 0 && "border-t border-aureus-rulesoft")}>
          <Skeleton className="h-2.5 w-10" delay={i * 60} />
          <div className="space-y-2">
            <Skeleton className="h-3" delay={i * 60 + 40} style={{ width: `${70 + ((i * 17) % 28)}%` }} />
            <Skeleton className="h-2 w-1/3" delay={i * 60 + 80} />
          </div>
        </div>
      ))}
    </div>
  );
}

/** A bordered sheet with a caps heading, for any panel still loading. */
export function SkeletonSheet({
  className, children, title = true,
}: { className?: string; children?: React.ReactNode; title?: boolean }) {
  return (
    <div className={cn("border border-aureus-rule bg-aureus-panel", className)}>
      {title && (
        <div className="px-5 py-3.5 border-b border-aureus-rule">
          <Skeleton className="h-2 w-28" />
        </div>
      )}
      <div className="p-5">{children ?? <SkeletonLines lines={4} />}</div>
    </div>
  );
}

/** The page header every screen opens with: serif title, one line of lead. */
export function SkeletonPageHeader({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      <Skeleton className="h-7 w-56" />
      <Skeleton className="h-3 w-full max-w-xl" delay={80} />
    </div>
  );
}
