"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Search } from "lucide-react";
import { usePortfolio } from "@/components/dashboard/PortfolioProvider";
import { Button } from "@/components/ui/button";
import {
  CapsLabel, Figure, Input, PageHeader, RuledLabel, Sheet,
} from "@/components/ui/primitives";
import { price, signed } from "@/lib/format";

const POPULAR = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM"];

type Horizon = "short_term" | "medium_term" | "long_term";

// The horizon is chosen HERE, before the analysis runs, and travels in the
// URL. Previously it was component state on the results page, so it reset
// to medium_term on every navigation and there was no way to ask for a
// short-term read up front.
const HORIZONS: { value: Horizon; label: string; sub: string; note: string }[] = [
  { value: "short_term",  label: "Short",  sub: "1d – 1m",
    note: "Price action and news lead; a DCF cannot explain a move this fast." },
  { value: "medium_term", label: "Medium", sub: "1m – 6m",
    note: "The three pillars weighted near evenly." },
  { value: "long_term",   label: "Long",   sub: "1y+",
    note: "Business quality leads; this quarter's mood is noise at this range." },
];

/**
 * Ticker picker. The analysis itself lives at /analysis/[ticker] so a given
 * stock's dashboard is a shareable, bookmarkable URL rather than transient
 * component state.
 *
 * Your own holdings come first. Someone arriving here almost always wants
 * to analyse something they already own, and making them retype a ticker
 * the platform already knows about is a small insult repeated daily.
 */
export default function AnalysisIndexPage() {
  const router = useRouter();
  const { holdings } = usePortfolio();
  const [ticker, setTicker] = useState("");
  const [horizon, setHorizon] = useState<Horizon>("medium_term");

  const go = (t: string) => {
    const clean = t.trim().toUpperCase();
    if (clean) router.push(`/analysis/${clean}?horizon=${horizon}`);
  };

  return (
    <div className="space-y-7 max-w-4xl">
      <PageHeader
        title="Deep analysis"
        lead="Fundamental, technical and sentiment scores combined into one ensemble, re-weighted by
              your time horizon, with a metric-backed bull and bear case for each side of the trade."
      />

      <Sheet lift accent className="p-5 space-y-4">
        <form onSubmit={(e) => { e.preventDefault(); go(ticker); }} className="space-y-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-aureus-muted pointer-events-none" />
            <Input
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="Enter a ticker — e.g. AAPL"
              className="pl-9 py-2.5"
              autoCapitalize="characters"
              spellCheck={false}
            />
          </div>

          <div>
            <CapsLabel>Holding period</CapsLabel>
            <div className="grid sm:grid-cols-3 gap-2 mt-2">
              {HORIZONS.map((h) => (
                <button
                  key={h.value}
                  type="button"
                  onClick={() => setHorizon(h.value)}
                  aria-pressed={horizon === h.value}
                  className={`rounded-md border px-3 py-2.5 text-left transition-colors ${
                    horizon === h.value
                      ? "border-aureus-gold bg-aureus-gold/[0.08]"
                      : "border-aureus-rule hover:border-aureus-rulestrong hover:bg-aureus-panellift"
                  }`}
                >
                  <div className={`text-[13px] font-medium ${horizon === h.value ? "text-aureus-gold" : "text-aureus-text"}`}>
                    {h.label}
                  </div>
                  <Figure tone="muted" className="text-[11px]">{h.sub}</Figure>
                </button>
              ))}
            </div>
            <p className="text-[11px] text-aureus-muted mt-2 leading-relaxed">
              {HORIZONS.find((h) => h.value === horizon)?.note}
            </p>
          </div>

          <Button type="submit" disabled={!ticker.trim()} className="w-full sm:w-auto">
            Analyse {ticker.trim().toUpperCase() || ""} <ArrowRight className="w-4 h-4" />
          </Button>
        </form>
      </Sheet>

      {holdings.length > 0 && (
        <div>
          <RuledLabel>Your positions</RuledLabel>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
            {holdings.map((h) => {
              const pct = h.current_price != null && h.average_cost_basis > 0
                ? ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100
                : null;
              return (
                <button
                  key={h.id || h.ticker}
                  onClick={() => go(h.ticker)}
                  className="group text-left rounded-[10px] border border-aureus-rule bg-aureus-panel px-4 py-3.5
                             hover:border-aureus-gold hover:bg-aureus-panellift transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-aureus-text">{h.ticker}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-aureus-muted group-hover:text-aureus-gold transition-colors" />
                  </div>
                  <div className="flex items-baseline gap-2.5 mt-1.5">
                    <Figure tone="muted" className="text-[13px]">{price(h.current_price)}</Figure>
                    {pct != null && (
                      <Figure tone={pct >= 0 ? "up" : "down"} className="text-[11px]">{signed(pct)}%</Figure>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <RuledLabel>Frequently analysed</RuledLabel>
        <div className="flex flex-wrap gap-1.5 mt-4">
          {POPULAR.map((t) => (
            <button
              key={t}
              onClick={() => go(t)}
              className="rounded-md border border-aureus-rule px-2.5 py-1.5 text-xs font-mono-num
                         text-aureus-soft hover:border-aureus-gold hover:text-aureus-gold transition-colors"
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="pt-1">
        <CapsLabel>What you get</CapsLabel>
        <div className="grid sm:grid-cols-3 gap-x-8 gap-y-4 mt-3">
          {[
            { k: "Fundamental", v: "Valuation, growth, profitability and balance-sheet strength from filed financials." },
            { k: "Technical", v: "Trend, momentum, volatility and support levels computed from real OHLCV bars." },
            { k: "Sentiment", v: "Aspect-based scoring across news wires, SEC filings and social, weighted by source authority." },
          ].map((c) => (
            <div key={c.k} className="border-t border-aureus-rule pt-3">
              <div className="text-[13px] text-aureus-soft font-medium">{c.k}</div>
              <p className="text-[12px] text-aureus-muted mt-1 leading-relaxed">{c.v}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
