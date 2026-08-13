"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const POPULAR = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM"];

/**
 * Ticker picker. The analysis itself lives at /analysis/[ticker] so a given
 * stock's dashboard is a shareable, bookmarkable URL rather than transient
 * component state.
 */
export default function AnalysisIndexPage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");

  const go = (t: string) => {
    const clean = t.trim().toUpperCase();
    if (clean) router.push(`/analysis/${clean}`);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Deep Analysis</h1>
        <p className="text-aureus-muted text-sm mt-0.5">
          Fundamental · Technical · Quantitative ensemble scoring, re-weighted by time horizon,
          with a metric-backed bull and bear case.
        </p>
      </div>

      <Card>
        <CardContent className="p-5 space-y-4">
          <form onSubmit={(e) => { e.preventDefault(); go(ticker); }} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-aureus-muted" />
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="Enter a ticker — e.g. AAPL"
                className="w-full rounded-md border border-aureus-border pl-9 pr-3 py-2.5 text-sm text-white
                           placeholder:text-aureus-muted/50 focus:outline-none focus:border-aureus-gold"
                style={{ background: "var(--bg)" }}
              />
            </div>
            <Button type="submit" disabled={!ticker.trim()}>Analyse</Button>
          </form>

          <div>
            <p className="text-[10px] uppercase tracking-wider text-aureus-muted mb-2">Frequently analysed</p>
            <div className="flex flex-wrap gap-1.5">
              {POPULAR.map((t) => (
                <button
                  key={t}
                  onClick={() => go(t)}
                  className="rounded-md border border-aureus-border px-2.5 py-1 text-xs font-mono
                             text-aureus-text hover:border-aureus-gold hover:text-aureus-gold transition-colors"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
