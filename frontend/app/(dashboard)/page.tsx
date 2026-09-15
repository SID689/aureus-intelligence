"use client";
/**
 * Portfolio dashboard.
 *
 * Built on the Tape idiom: one dominant figure with its own sparkline,
 * supporting numbers in hairline-divided columns rather than a row of
 * identical stat cards, allocation as a single segmented bar rather than
 * a donut with a legend, and the wire as hanging timestamps rather than
 * one bordered card per headline.
 */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { IconArrowRight, IconPlus } from "@/components/ui/icons";
import { Skeleton, SkeletonTable } from "@/components/ui/Skeleton";
import { usePortfolio } from "@/components/dashboard/PortfolioProvider";
import AddPositionModal from "@/components/dashboard/AddPositionModal";
import DailyLesson from "@/components/dashboard/DailyLesson";
import PriceChart from "@/components/charts/PriceChart";
import AlertFeed from "@/components/AlertFeed";
import { PositionTable } from "@/components/dashboard/DashboardWidgets";
import { Button } from "@/components/ui/button";
import {
  CapsLabel, EmptyState, Figure, RuledLabel, Segmented, SegmentedBar,
  Sheet, Sparkline, StatColumns,
} from "@/components/ui/primitives";
import { getBars } from "@/lib/api";
import type { PriceBar, Holding as ApiHolding } from "@/lib/api";
import { money, signed, signedMoney } from "@/lib/format";
import type { Holding } from "@/types";

const FALLBACK_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"];

export default function DashboardPage() {
  const { userId, portfolioId, holdings, apiHoldings, totals, loading, error, reload } = usePortfolio();

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<ApiHolding | null>(null);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [spark, setSpark] = useState<PriceBar[]>([]);

  const tickers = holdings.length ? holdings.map((h) => h.ticker).slice(0, 6) : FALLBACK_TICKERS;

  // Open on the largest position rather than a hardcoded AAPL the user may
  // not even hold. Only seeds once — after that the choice is the user's.
  useEffect(() => {
    if (activeTicker || !holdings.length) return;
    const largest = [...holdings].sort((a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0))[0];
    setActiveTicker(largest.ticker);
  }, [holdings, activeTicker]);

  const charted = activeTicker ?? tickers[0];

  // Sparkline for the hero figure. Separate from the main chart's own
  // fetch because it should not blank out while the user flips tickers.
  useEffect(() => {
    if (!charted) return;
    let cancelled = false;
    getBars(charted, 90, "1d")
      .then((r) => { if (!cancelled) setSpark(r.bars); })
      .catch(() => { /* the sparkline is ornamental — never block on it */ });
    return () => { cancelled = true; };
  }, [charted]);

  const sparkStats = useMemo(() => {
    if (spark.length < 2) return null;
    const closes = spark.map((b) => b.close);
    const changePct = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;
    return { closes, changePct };
  }, [spark]);

  const allocation = useMemo(
    () =>
      holdings
        .filter((h) => (h.current_weight ?? 0) > 0)
        .sort((a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0))
        .slice(0, 8)
        .map((h) => ({ label: h.ticker, value: h.current_weight ?? 0 })),
    [holdings]
  );

  const up = totals.pnl >= 0;
  const priced = holdings.filter((h) => h.current_price != null).length;

  const onEdit = (h: Holding) => setEditing(apiHoldings.find((a) => a.id === h.id) ?? null);

  return (
    <div className="space-y-7">
      {showAdd && portfolioId && (
        <AddPositionModal portfolioId={portfolioId} userId={userId}
                          onClose={() => setShowAdd(false)} onAdded={reload} />
      )}
      {editing && portfolioId && (
        <AddPositionModal portfolioId={portfolioId} userId={userId} editingHolding={editing}
                          onClose={() => setEditing(null)} onAdded={reload} />
      )}

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[28px] leading-none">Portfolio</h1>
          <p className="text-[13px] text-aureus-muted mt-2">
            {loading
              ? <Skeleton className="inline-block align-middle h-3 w-40" />
              : holdings.length === 0
                ? "No positions on file yet."
                : `${holdings.length} position${holdings.length === 1 ? "" : "s"} · ${priced} priced`}
          </p>
        </div>
        <Button onClick={() => setShowAdd(true)} disabled={!portfolioId}>
          <IconPlus className="w-3.5 h-3.5" strokeWidth={1.75} /> Add position
        </Button>
      </div>

      {error && (
        <Sheet className="px-5 py-3.5 border-aureus-crimsondim">
          <p className="text-[13px] text-aureus-crimson">{error}</p>
        </Sheet>
      )}

      {/* ── Hero figure + composition ──────────────────────────────── */}
      <Sheet lift className="overflow-hidden">
        <div className="grid lg:grid-cols-[1.35fr_2fr]">
          <div className="p-6 flex flex-col min-w-0 border-b lg:border-b-0 lg:border-r border-aureus-rule">
            <CapsLabel>Portfolio value</CapsLabel>
            <Figure className="mt-2.5 leading-none" style={{ fontSize: "clamp(2.25rem,4.5vw,3.25rem)", letterSpacing: "-0.03em" }}>
              {loading ? <Skeleton className="h-11 w-56" /> : money(totals.totalValue)}
            </Figure>
            <div className="flex items-center gap-3 mt-3">
              <Figure tone={up ? "up" : "down"} className="text-lg">
                {loading ? <Skeleton className="h-5 w-28" /> : signedMoney(totals.pnl)}
              </Figure>
              {!loading && (
                <span className={`font-mono-num text-[12px] px-1.5 py-0.5 rounded ${
                  up ? "bg-aureus-emerald/15 text-aureus-emerald" : "bg-aureus-crimson/15 text-aureus-crimson"
                }`}>
                  {signed(totals.pnlPct)}%
                </span>
              )}
            </div>

            {sparkStats && charted && (
              <div className="mt-auto pt-5 border-t border-aureus-rulesoft">
                {/* The sparkline tracks the CHARTED TICKER, not the
                    portfolio — there is no portfolio-level time series in
                    the API yet, and drawing one from nothing would put a
                    fabricated curve next to real money. Hence the label. */}
                <CapsLabel>{charted} · 90 sessions</CapsLabel>
                <div className="flex items-end gap-3 mt-2">
                  <Sparkline values={sparkStats.closes} tone={sparkStats.changePct >= 0 ? "up" : "down"} width={150} height={36} />
                  <Figure tone={sparkStats.changePct >= 0 ? "up" : "down"} className="text-xs pb-0.5">
                    {signed(sparkStats.changePct)}%
                  </Figure>
                </div>
              </div>
            )}
          </div>

          <div>
            <StatColumns
              className="border-b border-aureus-rule"
              items={[
                { label: "Invested", value: loading ? <Skeleton className="h-5 w-24" /> : money(totals.cost), sub: "cost basis" },
                { label: "Positions", value: loading ? <Skeleton className="h-5 w-10" /> : String(holdings.length), sub: `${priced} priced` },
                {
                  label: "Return on cost",
                  value: loading ? <Skeleton className="h-5 w-16" /> : `${signed(totals.pnlPct)}%`,
                  sub: "all-time",
                  tone: up ? "up" : "down",
                },
              ]}
            />
            <div className="p-5">
              <CapsLabel>Allocation</CapsLabel>
              <div className="mt-3">
                {allocation.length > 0 ? (
                  <SegmentedBar segments={allocation} />
                ) : (
                  <p className="text-[13px] text-aureus-muted py-2">
                    Add a position to see how your capital is distributed.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </Sheet>

      {/* ── Chart + wire ───────────────────────────────────────────── */}
      <div className="grid lg:grid-cols-[1.55fr_1fr] gap-5">
        <Sheet className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-aureus-rule">
            <CapsLabel>Price &amp; signals</CapsLabel>
            <Segmented
              value={charted ?? ""}
              onChange={setActiveTicker}
              options={tickers.map((t) => ({ value: t, label: t }))}
            />
          </div>
          <div className="p-4">
            {charted && <PriceChart ticker={charted} horizon="medium_term" />}
          </div>
        </Sheet>

        <Sheet className="min-w-0 flex flex-col">
          <div className="px-5 py-3 border-b border-aureus-rule">
            <CapsLabel>The wire</CapsLabel>
          </div>
          <div className="flex-1 overflow-y-auto px-5" style={{ maxHeight: 420 }}>
            <AlertFeed userId={userId} />
          </div>
        </Sheet>
      </div>

      {/* ── Positions ──────────────────────────────────────────────── */}
      <Sheet className="overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-aureus-rule">
          <CapsLabel>Positions</CapsLabel>
          {holdings.length > 0 && (
            <span className="text-[10px] text-aureus-muted">Click a row to edit or remove</span>
          )}
        </div>
        {loading ? (
          <SkeletonTable rows={4} columns={[2, 1, 1, 1, 2, 2, 3, 1]} />
        ) : holdings.length === 0 ? (
          <EmptyState
            title="No holdings yet"
            action={<Button size="sm" onClick={() => setShowAdd(true)} disabled={!portfolioId}>Add your first position</Button>}
          >
            Add what you own and the platform starts pricing it, watching the wire for
            news that touches it, and scoring it across all three pillars.
          </EmptyState>
        ) : (
          <PositionTable holdings={holdings} onEditHolding={onEdit} />
        )}
      </Sheet>

      {/* ── Lesson ─────────────────────────────────────────────────── */}
      <DailyLesson userId={userId} />

      <RuledLabel
        right={
          <Link href="/analysis" className="flex items-center gap-1.5 text-[11px] text-aureus-muted hover:text-aureus-gold transition-colors">
            Run a full analysis <IconArrowRight className="w-3 h-3" />
          </Link>
        }
      >
        Informational only · not financial advice
      </RuledLabel>
    </div>
  );
}
