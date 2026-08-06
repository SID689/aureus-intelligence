"use client";
import { useEffect, useState, useCallback } from "react";
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Scatter, Cell,
  type TooltipProps,
} from "recharts";
import type { PriceBar } from "@/lib/api";
import { runQuickAnalysis, getBars } from "@/lib/api";

interface Props {
  ticker:   string;
  horizon?: "short_term" | "medium_term" | "long_term";
  days?:    number;
}

// ── Custom tooltip ──────────────────────────────────────────────────────────

function PriceTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as PriceBar;
  if (!d) return null;

  return (
    <div className="rounded-lg border border-aureus-border p-3 text-xs space-y-1 shadow-xl"
         style={{ background: "var(--bg)" }}>
      <div className="text-aureus-muted font-medium">{d.timestamp}</div>
      <div className="text-white">Close: <span className="text-aureus-gold font-bold">${d.close?.toFixed(2)}</span></div>
      <div className="text-aureus-muted">O: {d.open?.toFixed(2)} · H: {d.high?.toFixed(2)} · L: {d.low?.toFixed(2)}</div>
      <div className="text-aureus-muted">Vol: {((d.volume || 0) / 1_000_000).toFixed(1)}M</div>
      {d.signal && (
        <div className={
          d.signal === "BUY"  ? "text-aureus-green font-bold" :
          d.signal === "SELL" ? "text-aureus-red font-bold"   : "text-aureus-gold font-bold"
        }>
          ● {d.signal} {d.confidence != null ? `(${d.confidence.toFixed(0)}%)` : ""}
        </div>
      )}
    </div>
  );
}

// ── Signal dot ─────────────────────────────────────────────────────────────

function SignalDot(props: { cx?: number; cy?: number; payload?: PriceBar }) {
  const { cx, cy, payload } = props;
  if (!payload?.signal || cx == null || cy == null) return null;
  const color =
    payload.signal === "BUY"  ? "#22c55e" :
    payload.signal === "SELL" ? "#ef4444" : "#d4a843";

  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill={color} fillOpacity={0.2} stroke={color} strokeWidth={1.5} />
      <text x={cx} y={cy - 12} textAnchor="middle" fill={color} fontSize={9} fontWeight="bold">
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
  const [bars,     setBars]     = useState<PriceBar[]>([]);
  const [provider, setProvider] = useState<string>("");
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);

  const loadChart = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Real OHLCV data from the Polygon-first backend fallback chain —
      // this replaces the old random-walk mock generator entirely.
      const barsResponse = await getBars(ticker, days, "1d");
      let bars = barsResponse.bars;
      setProvider(barsResponse.provider);

      // Overlay the latest ensemble signal on the most recent bar
      try {
        const result = await runQuickAnalysis(ticker, horizon);
        if (result.result) {
          bars = injectSignal(bars, result.result.signal, result.result.confidence_index);
        }
      } catch {
        // Chart still renders with real prices even if analysis fails
      }

      setBars(bars);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Chart failed to load");
    } finally {
      setLoading(false);
    }
  }, [ticker, horizon, days]);

  useEffect(() => { loadChart(); }, [loadChart]);

  const priceMin = bars.length ? Math.min(...bars.map((b) => b.low))  * 0.995 : 0;
  const priceMax = bars.length ? Math.max(...bars.map((b) => b.high)) * 1.005 : 0;
  const volMax   = bars.length ? Math.max(...bars.map((b) => b.volume)) : 0;
  const lastBar  = bars[bars.length - 1];
  const firstBar = bars[0];
  const overallUp = lastBar && firstBar && lastBar.close >= firstBar.close;

  if (loading) {
    return (
      <div className="h-80 flex items-center justify-center text-aureus-muted text-sm">
        Loading {ticker} chart from live market data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-80 flex flex-col items-center justify-center gap-2 text-center px-4">
        <span className="text-aureus-red text-sm">{error}</span>
        <button onClick={loadChart} className="text-xs text-aureus-gold hover:underline">Retry</button>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* Chart header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-3">
          <span className="text-white font-bold text-lg">{ticker}</span>
          {lastBar && (
            <>
              <span className="text-white text-lg">${lastBar.close.toFixed(2)}</span>
              <span className={overallUp ? "text-aureus-green text-sm" : "text-aureus-red text-sm"}>
                {overallUp ? "▲" : "▼"}{" "}
                {firstBar
                  ? `${Math.abs(((lastBar.close - firstBar.close) / firstBar.close) * 100).toFixed(2)}%`
                  : ""}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-aureus-muted">
            {provider && `via ${provider}`}
          </span>
          <button onClick={loadChart}
                  className="text-xs text-aureus-muted hover:text-white transition-colors">
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-1 text-xs text-aureus-muted">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-aureus-gold inline-block" />Price</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-aureus-green inline-block" />BUY signal</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-aureus-red inline-block" />SELL signal</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-aureus-gold inline-block" />HOLD signal</span>
      </div>

      {/* Main price chart */}
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={bars} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={Math.max(1, Math.floor(bars.length / 6))}
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={[priceMin, priceMax]}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            width={60}
          />
          <YAxis yAxisId="vol" orientation="left" domain={[0, volMax * 4]} tick={false} axisLine={false} tickLine={false} width={0} />
          <Tooltip content={<PriceTooltip />} />

          <Bar yAxisId="vol" dataKey="volume" fill="#1e1e2e" opacity={0.7} radius={[1, 1, 0, 0]}>
            {bars.map((b, i) => <Cell key={i} fill={b.close >= b.open ? "#22c55e22" : "#ef444422"} />)}
          </Bar>

          <Line yAxisId="price" type="monotone" dataKey="close" stroke="#d4a843" strokeWidth={1.5}
                dot={false} activeDot={{ r: 4, fill: "#d4a843" }} />

          {/* Deliberately pass the SAME bars array the rest of the chart uses,
              not a filtered subset — Scatter positions each point by its
              INDEX within whatever array it's given, matched against the
              shared category axis. A filtered array (e.g. just the one bar
              with a signal) gets positioned by ITS index in the filtered
              array, not the bar's real position, so the dot lands on some
              arbitrary/earlier x-tick instead of the bar it belongs to.
              SignalDot already returns null for bars without a signal, so
              passing the full array is both correct and sufficient. */}
          <Scatter yAxisId="price" dataKey="close" data={bars} shape={<SignalDot />} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Volume chart */}
      <ResponsiveContainer width="100%" height={60}>
        <ComposedChart data={bars} margin={{ top: 0, right: 68, left: 0, bottom: 0 }}>
          <Bar dataKey="volume" radius={[1, 1, 0, 0]}>
            {bars.map((b, i) => <Cell key={i} fill={b.close >= b.open ? "#22c55e55" : "#ef444455"} />)}
          </Bar>
          <XAxis dataKey="timestamp" hide />
          <YAxis hide />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
