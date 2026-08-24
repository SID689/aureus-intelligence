"use client";
/**
 * Shared kit for the dashboard design previews.
 *
 * WHY THIS EXISTS SEPARATELY FROM THE REAL WIDGETS
 * The production widgets (DashboardWidgets, AlertFeed, PriceChart,
 * DailyLesson) hardcode the dark palette — `text-aureus-muted`, `#1e1e2e`
 * grid lines, `var(--panel)` backgrounds. One of the variants below is a
 * light "paper" treatment, and those components would render as dark
 * bruises on it. Rather than modify shipped components to take a theme
 * they don't need yet, every preview draws from this kit, which takes a
 * Palette and paints with inline styles.
 *
 * That also means these files are purely additive: delete the previews
 * directory and the app is exactly as it was.
 *
 * WHAT THE PREVIEWS DELIBERATELY DON'T DO
 * They don't call runQuickAnalysis. The real chart overlays a live
 * ensemble signal on the last bar, which costs an analysis against the
 * user's quota every time the ticker changes. Flipping between three
 * layouts would burn through a day's allowance to show the same dot three
 * times, so the previews chart real prices and skip the signal overlay.
 */
import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { getBars, getRecentNews, getTodaysLesson } from "@/lib/api";
import type { NewsArticle, PriceBar, TodaysLesson } from "@/lib/api";
import type { Holding } from "@/types";

// ── The contract every variant implements ───────────────────────────────────
// Identical props across all three, so switching variants is a component
// swap and never a data refetch — you're comparing layouts against the same
// holdings, not against whatever loaded that second.

export interface VariantProps {
  userId: string;
  holdings: Holding[];
  totals: { totalValue: number; pnl: number; pnlPct: number };
  loading: boolean;
  tickers: string[];
  activeTicker: string;
  onSelectTicker: (t: string) => void;
  onAdd: () => void;
  onEdit: (h: Holding) => void;
}

// ── Palettes ────────────────────────────────────────────────────────────────
// Every value is a member of the existing Aureus family: warm near-black,
// antique gold, oxidized verdigris, ledger oxblood, bone text. What changes
// between variants is luminance and which member does the structural work —
// not the hues themselves.

export interface Palette {
  name: string;
  /** True when the ground is light — a few components flip shadow/graining. */
  light: boolean;
  ground: string;
  sheet: string;
  sheetAlt: string;
  rule: string;
  ruleStrong: string;
  text: string;
  textSoft: string;
  muted: string;
  accent: string;
  accentSoft: string;
  up: string;
  down: string;
  gridLine: string;
  /** Allocation ramp — alternating warm/cool inside the brand family. */
  ramp: string[];
}

export const PAPER: Palette = {
  name: "paper",
  light: true,
  ground: "#efeade",
  sheet: "#faf7ef",
  sheetAlt: "#e9e3d3",
  rule: "#d6cfbc",
  ruleStrong: "#3a372a",
  text: "#15180f",
  textSoft: "#474433",
  muted: "#7a755f",
  accent: "#8a6a34",
  accentSoft: "#c4a469",
  up: "#3a6a54",
  down: "#8b3838",
  gridLine: "#e0d9c6",
  ramp: ["#8a6a34", "#3a6a54", "#a98a4d", "#5c8a76", "#6d5c33", "#7f9c8e"],
};

export const TAPE: Palette = {
  name: "tape",
  light: false,
  ground: "#101309",
  sheet: "#191d12",
  sheetAlt: "#232719",
  rule: "#3a3728",
  ruleStrong: "#57523c",
  text: "#f4f1e6",
  textSoft: "#cdc8b6",
  muted: "#9c9783",
  accent: "#d9b478",
  accentSoft: "#8a7145",
  up: "#83bda2",
  down: "#c46e6e",
  gridLine: "#262a1c",
  ramp: ["#d9b478", "#83bda2", "#a8894f", "#5f8f7c", "#c0a577", "#4d7a67"],
};

export const LEDGER: Palette = {
  name: "ledger",
  light: false,
  ground: "#1b1e15",
  sheet: "#272a20",
  sheetAlt: "#31352a",
  rule: "#454133",
  ruleStrong: "#615c45",
  text: "#f1ede1",
  textSoft: "#ccc7b5",
  muted: "#9d9884",
  accent: "#cfa96f",
  accentSoft: "#7d6740",
  up: "#86c3a8",
  down: "#c97474",
  gridLine: "#33372b",
  ramp: ["#cfa96f", "#86c3a8", "#a08a5c", "#5f8f7c", "#c0a577", "#4d7a67"],
};

// ── Formatting ──────────────────────────────────────────────────────────────

export function money(n: number, digits = 0): string {
  return `$${n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

/** Compact form for headline figures: $1.24M rather than $1,238,411. */
export function moneyCompact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `$${(n / 1_000).toFixed(1)}K`;
  return money(n);
}

export function signed(n: number, digits = 2): string {
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(digits)}`;
}

export function signedMoney(n: number): string {
  return `${n >= 0 ? "+" : "−"}${money(Math.abs(n))}`;
}

/** "4:12 PM" — used in the hanging-timestamp gutter of the wire. */
export function clockTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function pnlOf(h: Holding): { abs: number | null; pct: number | null } {
  if (h.current_price == null) return { abs: null, pct: null };
  const abs = (h.current_price - h.average_cost_basis) * h.quantity;
  const pct = ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100;
  return { abs, pct };
}

/**
 * US equities regular session, expressed in the reader's own clock.
 * A dashboard that says "Live" at 2am on a Sunday is the fastest way to
 * tell someone the status light is decorative.
 */
export function marketPhase(now = new Date()): { label: string; open: boolean } {
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

// ── Primitives ──────────────────────────────────────────────────────────────

/**
 * A section label with a rule running from the text to the far edge — the
 * standard editorial device for dividing a page without drawing a box
 * around everything. Used instead of card headers in two of the variants.
 */
export function RuledLabel({
  children, p, right, className = "",
}: {
  children: React.ReactNode; p: Palette; right?: React.ReactNode; className?: string;
}) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <span
        className="text-[10px] uppercase whitespace-nowrap"
        style={{ color: p.muted, letterSpacing: "0.18em" }}
      >
        {children}
      </span>
      <span className="flex-1 h-px" style={{ background: p.rule }} />
      {right}
    </div>
  );
}

/** Small tabular figure with semantic colour. */
export function Figure({
  value, p, tone, className = "", style,
}: {
  value: React.ReactNode; p: Palette; tone?: "up" | "down" | "muted";
  className?: string; style?: React.CSSProperties;
}) {
  const color =
    tone === "up" ? p.up : tone === "down" ? p.down : tone === "muted" ? p.muted : p.text;
  return (
    <span className={`font-mono-num ${className}`} style={{ color, ...style }}>
      {value}
    </span>
  );
}

// ── Sparkline ───────────────────────────────────────────────────────────────

/**
 * Hand-rolled rather than a fourth recharts instance: a sparkline has no
 * axes, no tooltip and no legend, so the whole component is one path
 * command and it renders instantly instead of waiting on a chart mount.
 */
export function Sparkline({
  values, color, width = 120, height = 32, fill = true,
}: {
  values: number[]; color: string; width?: number; height?: number; fill?: boolean;
}) {
  const id = useId();
  if (values.length < 2) return <svg width={width} height={height} aria-hidden />;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const pt = (v: number, i: number) => [i * step, height - ((v - min) / span) * (height - 2) - 1];

  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${pt(v, i).map((n) => n.toFixed(1)).join(",")}`).join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;

  return (
    <svg width={width} height={height} aria-hidden style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#spark-${id})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth={1.25} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Bars hook ───────────────────────────────────────────────────────────────

export function useBars(ticker: string, days = 120) {
  const [bars, setBars] = useState<PriceBar[]>([]);
  const [provider, setProvider] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getBars(ticker, days, "1d")
      .then((res) => {
        if (cancelled) return;
        setBars(res.bars);
        setProvider(res.provider);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Chart unavailable");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, days]);

  const stats = useMemo(() => {
    if (bars.length < 2) return null;
    const first = bars[0], last = bars[bars.length - 1];
    const closes = bars.map((b) => b.close);
    return {
      last: last.close,
      changePct: ((last.close - first.close) / first.close) * 100,
      high: Math.max(...bars.map((b) => b.high)),
      low: Math.min(...bars.map((b) => b.low)),
      closes,
    };
  }, [bars]);

  return { bars, provider, loading, error, stats };
}

// ── Chart ───────────────────────────────────────────────────────────────────

export function PreviewChart({
  bars, p, height = 260, volume = true,
}: {
  bars: PriceBar[]; p: Palette; height?: number; volume?: boolean;
}) {
  const id = useId();
  if (bars.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm" style={{ height, color: p.muted }}>
        No price history available.
      </div>
    );
  }

  const lo = Math.min(...bars.map((b) => b.low)) * 0.995;
  const hi = Math.max(...bars.map((b) => b.high)) * 1.005;

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        {/* The left margin is not cosmetic. Recharts centres the first
            x-tick on x=0, and the SVG clips whatever hangs left of the
            plot area — so "Apr 27" rendered as "27" at left:0 and as
            "or 27" at left:10. The Y axis is on the right, so this margin
            costs nothing but the room the label needs. */}
        <AreaChart data={bars} margin={{ top: 6, right: 4, left: 28, bottom: 0 }}>
          <defs>
            <linearGradient id={`px-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={p.accent} stopOpacity={p.light ? 0.22 : 0.3} />
              <stop offset="100%" stopColor={p.accent} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={p.gridLine} vertical={false} strokeDasharray="2 4" />
          <XAxis
            dataKey="timestamp" tickLine={false} axisLine={false}
            tick={{ fill: p.muted, fontSize: 10 }}
            interval={Math.max(1, Math.floor(bars.length / 6))}
          />
          <YAxis
            orientation="right" domain={[lo, hi]} width={52}
            tickLine={false} axisLine={false}
            tick={{ fill: p.muted, fontSize: 10 }}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
          />
          <Tooltip
            cursor={{ stroke: p.ruleStrong, strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as PriceBar;
              const up = d.close >= d.open;
              return (
                <div
                  className="rounded px-3 py-2 text-xs space-y-1"
                  style={{
                    background: p.sheet, border: `1px solid ${p.rule}`, color: p.text,
                    boxShadow: p.light ? "0 4px 14px rgba(0,0,0,0.10)" : "0 6px 20px rgba(0,0,0,0.5)",
                  }}
                >
                  <div style={{ color: p.muted, letterSpacing: "0.08em" }}>{d.timestamp}</div>
                  <div className="font-mono-num" style={{ color: up ? p.up : p.down }}>
                    ${d.close.toFixed(2)}
                  </div>
                  <div className="font-mono-num" style={{ color: p.muted }}>
                    H {d.high.toFixed(2)} · L {d.low.toFixed(2)}
                  </div>
                </div>
              );
            }}
          />
          <Area
            type="monotone" dataKey="close" stroke={p.accent} strokeWidth={1.6}
            fill={`url(#px-${id})`} dot={false}
            activeDot={{ r: 3, fill: p.accent, stroke: p.ground, strokeWidth: 1.5 }}
          />
        </AreaChart>
      </ResponsiveContainer>

      {volume && (
        <ResponsiveContainer width="100%" height={44}>
          <BarChart data={bars} margin={{ top: 2, right: 56, left: 28, bottom: 0 }}>
            <XAxis dataKey="timestamp" hide />
            <YAxis hide />
            <Bar dataKey="volume" fill={p.accentSoft} opacity={p.light ? 0.35 : 0.45} radius={[1, 1, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ── Allocation, two ways ────────────────────────────────────────────────────

/** Ruled proportional bars — a ledger of weights, readable at a glance. */
export function AllocationRows({ holdings, p }: { holdings: Holding[]; p: Palette }) {
  const rows = holdings
    .filter((h) => (h.current_weight ?? 0) > 0)
    .sort((a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0))
    .slice(0, 8);

  if (!rows.length) {
    return <p className="text-sm py-6" style={{ color: p.muted }}>Add a position to see allocation.</p>;
  }
  const max = Math.max(...rows.map((r) => r.current_weight ?? 0));

  return (
    <div>
      {rows.map((h, i) => (
        <div
          key={h.id || h.ticker}
          className="flex items-center gap-3 py-2"
          style={{ borderTop: i === 0 ? "none" : `1px solid ${p.rule}` }}
        >
          <span className="w-14 text-sm font-medium" style={{ color: p.text }}>{h.ticker}</span>
          <span className="flex-1 h-1.5 rounded-sm overflow-hidden" style={{ background: p.sheetAlt }}>
            <span
              className="block h-full"
              style={{
                width: `${((h.current_weight ?? 0) / max) * 100}%`,
                background: p.ramp[i % p.ramp.length],
              }}
            />
          </span>
          <Figure
            value={`${(h.current_weight ?? 0).toFixed(1)}%`}
            p={p} tone="muted" className="text-xs w-12 text-right"
          />
        </div>
      ))}
    </div>
  );
}

/** One segmented bar — the whole portfolio as a single object. */
export function AllocationStack({ holdings, p }: { holdings: Holding[]; p: Palette }) {
  const rows = holdings
    .filter((h) => (h.current_weight ?? 0) > 0)
    .sort((a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0))
    .slice(0, 8);
  if (!rows.length) {
    return <p className="text-sm py-4" style={{ color: p.muted }}>Add a position to see allocation.</p>;
  }
  const total = rows.reduce((s, h) => s + (h.current_weight ?? 0), 0);

  return (
    <div className="space-y-3">
      <div className="flex h-2.5 rounded-sm overflow-hidden" style={{ background: p.sheetAlt }}>
        {rows.map((h, i) => (
          <span
            key={h.id || h.ticker}
            title={`${h.ticker} — ${(h.current_weight ?? 0).toFixed(1)}%`}
            style={{
              width: `${((h.current_weight ?? 0) / total) * 100}%`,
              background: p.ramp[i % p.ramp.length],
            }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1.5">
        {rows.map((h, i) => (
          <span key={h.id || h.ticker} className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full" style={{ background: p.ramp[i % p.ramp.length] }} />
            <span style={{ color: p.textSoft }}>{h.ticker}</span>
            <Figure value={`${(h.current_weight ?? 0).toFixed(1)}%`} p={p} tone="muted" className="text-[11px]" />
          </span>
        ))}
      </div>
    </div>
  );
}

// ── The wire (news) ─────────────────────────────────────────────────────────

/**
 * Replaces AlertFeed inside previews. Same source (getRecentNews), themed,
 * and without the 📡 / 📰 emoji placeholders — an emoji standing in for an
 * icon is the single loudest "this was generated" tell in a product that
 * otherwise sets its numbers in tabular monospace.
 */
export function useWire(userId: string, limit = 14) {
  const [items, setItems] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getRecentNews(limit, userId || undefined)
      .then((r) => { if (!cancelled) setItems(r.articles); })
      .catch(() => { /* the wire is supplementary — never block the page on it */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [userId, limit]);

  return { items, loading };
}

export function sentimentTone(score: number): "up" | "down" | "muted" {
  if (score > 0.15) return "up";
  if (score < -0.15) return "down";
  return "muted";
}

// ── Daily lesson ────────────────────────────────────────────────────────────

export function useTodaysLesson(userId: string) {
  const [lesson, setLesson] = useState<TodaysLesson | null>(null);
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    getTodaysLesson(userId)
      .then((r) => { if (!cancelled) setLesson(r); })
      .catch(() => { /* nice-to-have */ });
    return () => { cancelled = true; };
  }, [userId]);
  return lesson;
}

/** First sentence of the lesson body — enough for a standing teaser. */
export function firstSentence(text: string, max = 190): string {
  const flat = text.replace(/\s+/g, " ").trim();
  const stop = flat.search(/[.!?](\s|$)/);
  const cut = stop > 40 ? flat.slice(0, stop + 1) : flat.slice(0, max);
  return cut.length < flat.length && stop <= 40 ? `${cut.trim()}…` : cut;
}

// ── Live status dot ─────────────────────────────────────────────────────────

export function StatusDot({ p, on }: { p: Palette; on: boolean }) {
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full ${on ? "pulse-gold" : ""}`}
      style={{ background: on ? p.up : p.muted }}
    />
  );
}

/** Ticks once a minute so a printed "as of" time doesn't go stale on screen. */
export function useClock(): Date {
  const [now, setNow] = useState<Date | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Deliberately starts null and fills in after mount: rendering
  // `new Date()` during SSR and again on the client produces two different
  // strings and React logs a hydration mismatch for every one of them.
  useEffect(() => {
    setNow(new Date());
    timer.current = setInterval(() => setNow(new Date()), 60_000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  return now ?? new Date(0);
}

export function useMounted(): boolean {
  const [m, setM] = useState(false);
  useEffect(() => setM(true), []);
  return m;
}
