"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { usePortfolio } from "@/components/dashboard/PortfolioProvider";
import { Button } from "@/components/ui/button";
import { Figure, Input, PageHeader, RuledLabel } from "@/components/ui/primitives";
import { IconArrowRight, IconSearch } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { price, signed } from "@/lib/format";

const POPULAR = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM"];

type Horizon = "short_term" | "medium_term" | "long_term";

/**
 * The horizon is chosen here, before the analysis runs, and travels in the
 * URL. Each option shows the pillar weights it applies, straight from the
 * engine (backend/app/analysis/ensemble.py _HORIZON_WEIGHTS), so choosing a
 * horizon is choosing a visible weighting, not an opaque mode.
 */
const HORIZONS: { value: Horizon; label: string; range: string; weights: [number, number, number]; note: string }[] = [
  { value: "short_term", label: "Short", range: "1d to 1m", weights: [10, 50, 40],
    note: "Price action and news lead. A discounted cash flow cannot explain a move this fast." },
  { value: "medium_term", label: "Medium", range: "1m to 6m", weights: [35, 35, 30],
    note: "The three pillars weighted near evenly." },
  { value: "long_term", label: "Long", range: "1y and beyond", weights: [65, 20, 15],
    note: "Business quality leads. This quarter’s mood carries little information at this range." },
];

const METHOD: [string, string][] = [
  ["Fundamental", "Valuation, growth, profitability and balance-sheet strength from filed financials, compared with sector medians."],
  ["Technical", "Trend, momentum, volatility and support levels computed from daily price bars."],
  ["Sentiment", "Aspect-based scoring of news wires, SEC filing tone and retail messages, weighted by source authority."],
];

export default function AnalysisIndexPage() {
  const router = useRouter();
  const { holdings } = usePortfolio();
  const [ticker, setTicker] = useState("");
  const [horizon, setHorizon] = useState<Horizon>("medium_term");

  const go = (t: string) => {
    const clean = t.trim().toUpperCase();
    if (clean) router.push(`/analysis/${clean}?horizon=${horizon}`);
  };
  const active = HORIZONS.find((h) => h.value === horizon)!;

  return (
    <div className="space-y-9 max-w-4xl">
      <PageHeader
        title="Analysis"
        lead="Fundamental, technical and sentiment evidence pooled into one composite, weighted by your holding period, with a bull and bear case built from the figures."
      />

      <form onSubmit={(e) => { e.preventDefault(); go(ticker); }} className="border border-aureus-rule bg-aureus-panel">
        <div className="p-5 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <IconSearch className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-aureus-muted pointer-events-none" />
            <Input
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="Ticker, for example AAPL"
              className="pl-9 h-10 font-mono-num uppercase placeholder:normal-case placeholder:font-sans"
              autoCapitalize="characters"
              spellCheck={false}
              aria-label="Ticker"
            />
          </div>
          <Button type="submit" disabled={!ticker.trim()} className="h-10">
            Analyse {ticker.trim().toUpperCase()} <IconArrowRight className="w-3.5 h-3.5" />
          </Button>
        </div>

        <fieldset className="border-t border-aureus-rule">
          <legend className="sr-only">Holding period</legend>
          <div className="grid grid-cols-3">
            {HORIZONS.map((h, i) => {
              const on = h.value === horizon;
              return (
                <button
                  key={h.value}
                  type="button"
                  onClick={() => setHorizon(h.value)}
                  aria-pressed={on}
                  className={cn(
                    "text-left px-4 sm:px-5 py-3.5 transition-colors",
                    i > 0 && "border-l border-aureus-rule",
                    on ? "bg-aureus-panelhigh" : "hover:bg-aureus-panellift",
                  )}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={cn("text-[13.5px]", on ? "text-aureus-gold" : "text-aureus-text")}>{h.label}</span>
                    <span className="hidden sm:inline font-mono-num text-[10.5px] text-aureus-muted">{h.range}</span>
                  </div>
                  <div className="flex gap-3 mt-2 font-mono-num text-[11px] text-aureus-muted">
                    <span>F {h.weights[0]}</span><span>T {h.weights[1]}</span><span>S {h.weights[2]}</span>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="px-5 py-2.5 border-t border-aureus-rule text-[12px] text-aureus-muted">{active.note}</p>
        </fieldset>
      </form>

      {holdings.length > 0 && (
        <section>
          <RuledLabel>Your positions</RuledLabel>
          <div className="mt-2">
            {holdings.map((h, i) => {
              const pct = h.current_price != null && h.average_cost_basis > 0
                ? ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100
                : null;
              return (
                <button
                  key={h.id || h.ticker}
                  onClick={() => go(h.ticker)}
                  className={cn("group w-full grid grid-cols-[5rem_1fr_5rem_auto] items-baseline gap-4 px-2 py-2.5 text-left ledger-row", i > 0 && "border-t border-aureus-rulesoft")}
                >
                  <span className="font-mono-num text-[14px] text-aureus-text">{h.ticker}</span>
                  <Figure tone="muted" className="text-[13px]">{price(h.current_price)}</Figure>
                  <Figure tone={pct == null ? "muted" : pct >= 0 ? "up" : "down"} className="text-[12px] text-right">
                    {pct == null ? "" : `${signed(pct)}%`}
                  </Figure>
                  <span className="text-[12px] text-aureus-muted group-hover:text-aureus-gold">Analyse</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <section>
        <RuledLabel>Frequently analysed</RuledLabel>
        <div className="flex flex-wrap gap-1.5 mt-4">
          {POPULAR.map((t) => (
            <button key={t} onClick={() => go(t)}
                    className="border border-aureus-rule px-2.5 py-1.5 text-[12px] font-mono-num text-aureus-soft hover:border-aureus-gold hover:text-aureus-gold transition-colors">
              {t}
            </button>
          ))}
        </div>
      </section>

      <section>
        <RuledLabel>Method</RuledLabel>
        <dl className="mt-2">
          {METHOD.map(([k, v], i) => (
            <div key={k} className={cn("grid sm:grid-cols-[9rem_1fr] gap-x-6 gap-y-1 py-3", i > 0 && "border-t border-aureus-rulesoft")}>
              <dt className="text-[13px] text-aureus-text">{k}</dt>
              <dd className="text-[13px] text-aureus-muted leading-relaxed">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
