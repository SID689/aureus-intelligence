"use client";
import { useEffect, useState, useCallback, useId } from "react";
import {
  Area, ComposedChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Scatter, Cell,
} from "recharts";
import { useSession } from "next-auth/react";
import { IconRefresh } from "@/components/ui/icons";
import { LoadingRegion, SkeletonChart } from "@/components/ui/Skeleton";
import { runQuickAnalysis, getBars } from "@/lib/api";
import type { PriceBar } from "@/lib/api";
import { Figure } from "@/components/ui/primitives";
import { signed } from "@/lib/format";

interface Props {
  ticker:   string;
  horizon?: "short_term" | "medium_term" | "long_term";
  days?:    number;
}

/**
 * Every colour here is a brand token. This chart used to hardcode a
 * blue-grey grid and flat traffic-light green/red signal dots — leftovers
 * from a theme the rest of the app stopped using, which is why the chart
 * never quite looked like it belonged on the page it sat on.
 */
const C = {
  gold:      "var(--gold)",
  up:        "var(--emerald)",
  down:      "var(--crimson)",
  grid:      "var(--grid-line)",
  muted:     "var(--text-muted)",
  panel:     "var(--panel-lift)",
  rule:      "var(--rule)",
  ink:       "var(--ink)",
};

function signalColor(signal?: string): string {
  return signal === "BUY" ? C.up : signal === "SELL" ? C.down : C.gold;
}

// ── Tooltip ─────────────────────────────────────────────────────────────────

function PriceTooltip({ active, payload }: { active?: boolean; payload?: { payload: PriceBar }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const up = d.close >= d.open;

  return (
    <div className="rounded-md border border-aureus-rule bg-aureus-panellift px-3 py-2 text-xs space-y-1 shadow-overlay">
      <div className="text-aureus-muted">{d.timestamp}</div>
      <div className="text-aureus-soft">
        Close <Figure tone={up ? "up" : "down"} className="font-semibold">${d.close?.toFixed(2)}</Figure>
      </div>
      <Figure tone="muted" className="block text-[11px]">
        O {d.open?.toFixed(2)} · H {d.high?.toFixed(2)} · L {d.low?.toFixed(2)}
      </Figure>
      <Figure tone="muted" className="block text-[11px]">
        Vol {((d.volume || 0) / 1_000_000).toFixed(1)}M
      </Figure>
      {d.signal && (
        <div className="pt-1 border-t border-aureus-rule font-mono text-[11px] font-semibold uppercase tracking-wide"
             style={{ color: signalColor(d.signal) }}>
          {d.signal}{d.confidence != null ? ` · ${d.confidence.toFixed(0)}% confidence` : ""}
        </div>
      )}
    </div>
  );
}

// ── Signal marker ───────────────────────────────────────────────────────────

function SignalDot(props: { cx?: number; cy?: number; payload?: PriceBar }) {
  const { cx, cy, payload } = props;
  if (!payload?.signal || cx == null || cy == null) return null;
  const color = signalColor(payload.signal);

  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill={color} fillOpacity={0.18} stroke={color} strokeWidth={1.5} />
      <text x={cx} y={cy - 12} textAnchor="middle" fill={color} fontSize={9} fontWeight="700"
            style={{ letterSpacing: "0.08em" }}>
        {payload.signal}
      </text>
    </g>
  );
}

function injectSignal(bars: PriceBar[], signal: string, confidence: number): PriceBar[] {
  if (!bars.length) return bars;
  const last = bars.length - 1;
  return bars.map((b, i) => ({
    ...b,
    signal:     i === last ? (signal as PriceBar["signal"]) : undefined,
    confidence: i === last ? confidence : undefined,
  }));
}

// ── Main component ──────────────────────────────────────────────────────────

export default function PriceChart({ ticker, horizon = "medium_term", days = 180 }: Props) {
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const gradientId = useId();
  const [bars,     setBars]     = useState<PriceBar[]>([]);
  const [provider, setProvider] = useState<string>("");
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);

  const loadChart = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const barsResponse = await getBars(ticker, days, "1d");
      let next = barsResponse.bars;
      setProvider(barsResponse.provider);

      // Overlay the latest ensemble signal on the most recent bar.
      try {
        const result = await runQuickAnalysis(ticker, userId, horizon);
        if (result.result) next = injectSignal(next, result.result.signal, result.result.confidence_index);
      } catch {
        // Chart still renders with real prices even if analysis fails.
      }

      setBars(next);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Chart failed to load");
    } finally {
      setLoading(false);
    }
  }, [ticker, horizon, days, userId]);

  useEffect(() => { loadChart(); }, [loadChart]);

  const priceMin = bars.length ? Math.min(...bars.map((b) => b.low))  * 0.995 : 0;
  const priceMax = bars.length ? Math.max(...bars.map((b) => b.high)) * 1.005 : 0;
  const volMax   = bars.length ? Math.max(...bars.map((b) => b.volume)) : 0;
  const lastBar  = bars[bars.length - 1];
  const firstBar = bars[0];
  const changePct = lastBar && firstBar ? ((lastBar.close - firstBar.close) / firstBar.close) * 100 : null;

  if (loading) {
    return (
      <LoadingRegion label={`Loading ${ticker} price history`}><SkeletonChart height={364} /></LoadingRegion>
    );
  }

  if (error) {
    return (
      <div className="h-[364px] flex flex-col items-center justify-center gap-2 text-center px-4">
        <span className="text-aureus-crimson text-sm">{error}</span>
        <button onClick={loadChart} className="text-xs text-aureus-gold hover:text-aureus-goldbright">Retry</button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-1">
        <div className="flex items-baseline gap-3">
          <span className="text-base font-medium text-aureus-text">{ticker}</span>
          {lastBar && <Figure className="text-lg">${lastBar.close.toFixed(2)}</Figure>}
          {changePct != null && (
            <Figure tone={changePct >= 0 ? "up" : "down"} className="text-[13px]">
              {signed(changePct)}% · {days}d
            </Figure>
          )}
        </div>
        <div className="flex items-center gap-3">
          {provider && <span className="text-[11px] text-aureus-muted">via {provider}</span>}
          <button onClick={loadChart} className="text-aureus-muted hover:text-aureus-text transition-colors" aria-label="Refresh chart">
            <IconRefresh className="w-3 h-3" />
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        {/* left:28 is load-bearing: recharts centres the first x-tick on
            x=0 and the SVG clips whatever hangs left of the plot area, so
            "Apr 27" renders as "27". The Y axis is on the right, so this
            margin costs nothing but the room the label needs. */}
        <ComposedChart data={bars} margin={{ top: 8, right: 4, left: 28, bottom: 0 }}>
          <defs>
            <linearGradient id={`px-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={C.gold} stopOpacity={0.28} />
              <stop offset="100%" stopColor={C.gold} stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
          <XAxis
            dataKey="timestamp" tickLine={false} axisLine={false}
            tick={{ fill: C.muted, fontSize: 10 }}
            interval={Math.max(1, Math.floor(bars.length / 6))}
          />
          <YAxis
            yAxisId="price" orientation="right" domain={[priceMin, priceMax]}
            tickLine={false} axisLine={false} width={56}
            tick={{ fill: C.muted, fontSize: 10 }}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
          />
          <YAxis yAxisId="vol" orientation="left" domain={[0, volMax * 4]} tick={false} axisLine={false} tickLine={false} width={0} />
          <Tooltip content={<PriceTooltip />} cursor={{ stroke: C.rule, strokeWidth: 1 }} />

          <Bar yAxisId="vol" dataKey="volume" radius={[1, 1, 0, 0]}>
            {bars.map((b, i) => (
              <Cell key={i} fill={b.close >= b.open ? C.up : C.down} fillOpacity={0.14} />
            ))}
          </Bar>

          <Area
            yAxisId="price" type="monotone" dataKey="close"
            stroke={C.gold} strokeWidth={1.6} fill={`url(#px-${gradientId})`}
            dot={false} activeDot={{ r: 3.5, fill: C.gold, stroke: C.ink, strokeWidth: 1.5 }}
          />

          {/* Deliberately the SAME bars array the rest of the chart uses,
              not a filtered subset — Scatter positions each point by its
              INDEX within whatever array it is given, matched against the
              shared category axis. A filtered array gets positioned by its
              index in the filtered array, so the dot lands on an arbitrary
              earlier tick. SignalDot returns null for bars with no signal,
              so passing everything is both correct and sufficient. */}
          <Scatter yAxisId="price" dataKey="close" data={bars} shape={<SignalDot />} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
