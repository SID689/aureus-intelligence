"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CapsLabel, ErrorNote, Figure, Segmented, StatColumns } from "@/components/ui/primitives";
import { IconSearch } from "@/components/ui/icons";
import {
  LoadingRegion, Skeleton, SkeletonChart, SkeletonLines, SkeletonSheet, SkeletonStatColumns, SkeletonTable,
} from "@/components/ui/Skeleton";
import PillarLedger from "@/components/analysis/PillarLedger";
import ThesisCard from "@/components/analysis/ThesisCard";
import SectorComparisonCard from "@/components/analysis/SectorComparisonCard";
import SentimentCard from "@/components/analysis/SentimentCard";
import CatalystTimeline from "@/components/analysis/CatalystTimeline";
import PriceChart from "@/components/charts/PriceChart";
import { cn } from "@/lib/utils";
import { getFullAnalysis } from "@/lib/api";
import type { FullAnalysis } from "@/lib/api";

type Horizon = "short_term" | "medium_term" | "long_term";

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: "short_term", label: "Short · 1d to 1m" },
  { value: "medium_term", label: "Medium · 1m to 6m" },
  { value: "long_term", label: "Long · 1y+" },
];

function verdict(a: FullAnalysis): { label: string; cls: string } {
  const strong = a.signal_strength === "STRONG";
  if (a.signal === "BUY") {
    return strong
      ? { label: "Strong Buy", cls: "bg-aureus-emerald text-aureus-ink border border-aureus-emerald" }
      : { label: "Buy", cls: "text-aureus-emerald border border-aureus-emerald/60" };
  }
  if (a.signal === "SELL") {
    return strong
      ? { label: "Strong Sell", cls: "bg-aureus-crimson text-aureus-ink border border-aureus-crimson" }
      : { label: "Sell", cls: "text-aureus-crimson border border-aureus-crimson/60" };
  }
  return { label: "Hold", cls: "text-aureus-gold border border-aureus-gold/60" };
}

const fmtPct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const fmtNum = (v: number | null | undefined, d = 2, suffix = "") => (v == null ? "—" : `${v.toFixed(d)}${suffix}`);

function convictionNote(data: FullAnalysis): string {
  const conv = data.conviction ?? 0;
  const agree = data.agreement ?? 0;
  if (conv >= 30) return "Conviction combines how far the evidence leans, whether the three pillars agree, and how much data backed the run.";
  if (agree < 0.4) return "Low conviction: the pillars point in different directions, so the composite sits near neutral by cancellation, not consensus.";
  if (data.overall_data_completeness < 0.6) return "Low conviction: too little data backed this run. Pillars with missing inputs had their weight moved to the ones that computed.";
  return "Low conviction: the pillars agree on direction but the lean is mild. Treat the direction as loosely held.";
}

function AnalysisSkeleton({ ticker }: { ticker: string }) {
  return (
    <LoadingRegion label={`Running the analysis for ${ticker}`} className="space-y-6">
      <SkeletonSheet title={false}><SkeletonTable rows={3} columns={[2, 5, 1, 1, 4]} /></SkeletonSheet>
      <div className="grid lg:grid-cols-2 gap-5">
        <SkeletonSheet><SkeletonLines lines={7} /></SkeletonSheet>
        <SkeletonSheet><SkeletonLines lines={7} /></SkeletonSheet>
      </div>
      <SkeletonSheet><SkeletonChart height={280} /></SkeletonSheet>
    </LoadingRegion>
  );
}

function MetricCell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border-r border-b border-aureus-rule px-4 py-3.5 min-w-0">
      <CapsLabel>{label}</CapsLabel>
      <Figure className="block text-[17px] mt-1.5 truncate">{value}</Figure>
      {hint && <div className="text-[11px] text-aureus-muted mt-0.5 truncate">{hint}</div>}
    </div>
  );
}

function TickerAnalysisView() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const ticker = String(params?.ticker ?? "").toUpperCase();

  // The horizon lives in the URL, so it survives navigation and reloads and
  // "NVDA on a short-term view" is a link you can send someone.
  const urlHorizon = searchParams.get("horizon");
  const horizon: Horizon = HORIZONS.some((h) => h.value === urlHorizon) ? (urlHorizon as Horizon) : "medium_term";
  const setHorizon = (h: Horizon) => router.replace(`/analysis/${ticker}?horizon=${h}`, { scroll: false });

  const [data, setData] = useState<FullAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!ticker || !userId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getFullAnalysis(ticker, userId, horizon);
      if (!res.result) throw new Error(res.error || "No analysis was returned");
      setData(res.result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The analysis failed");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [ticker, horizon, userId]);

  useEffect(() => { void load(); }, [load]);

  const v = data && !loading ? verdict(data) : null;
  const f = data?.fundamental;
  const t = data?.technical;
  const sn = data?.sentiment;
  const ready = data && !loading;
  const ci = data?.confidence_index ?? 0;

  return (
    <div className="space-y-6">
      <header className="border border-aureus-rule bg-aureus-panel">
        <div className="px-5 pt-5 pb-4 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <h1 className="font-mono-num text-[32px] leading-none text-aureus-text">{ticker}</h1>
              {v && <span className={cn("px-2 py-1 font-mono-num text-[10.5px] uppercase tracking-[0.14em]", v.cls)}>{v.label}</span>}
            </div>
            {ready ? (
              <p className="text-[12px] text-aureus-muted mt-2.5">
                {data.time_horizon} · prices via {data.market_data_provider} · fundamentals via {data.fundamental_data_provider}
              </p>
            ) : loading ? <Skeleton className="h-3 w-72 mt-3" /> : null}
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); if (search.trim()) router.push(`/analysis/${search.trim().toUpperCase()}?horizon=${horizon}`); }}
            className="flex gap-2"
          >
            <div className="relative">
              <IconSearch className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-aureus-muted pointer-events-none" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Another ticker"
                aria-label="Analyse another ticker"
                className="w-40 h-8 bg-aureus-ink border border-aureus-rule rounded-sm pl-8 pr-3 text-[13px] font-mono-num uppercase text-aureus-text placeholder:normal-case placeholder:font-sans placeholder:text-aureus-muted/60 focus:outline-none focus:border-aureus-gold"
              />
            </div>
            <Button type="submit" size="sm" variant="outline" className="h-8">Go</Button>
          </form>
        </div>

        <div className="px-5 pb-4">
          <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} size="md" />
        </div>

        {ready ? (
          <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] border-t border-aureus-rule">
            <div className="px-5 py-4 border-b lg:border-b-0 lg:border-r border-aureus-rule">
              <CapsLabel>Composite</CapsLabel>
              <div className="flex items-baseline gap-2 mt-1.5">
                <Figure tone={ci >= 65 ? "up" : ci < 35 ? "down" : "flat"} className={cn("text-[40px] leading-none", ci >= 35 && ci < 65 && "text-aureus-gold")}>
                  {ci.toFixed(1)}
                </Figure>
                <span className="font-mono-num text-[12px] text-aureus-muted">/ 100</span>
              </div>
              <div className="relative h-1.5 bg-aureus-panelhigh mt-4" aria-hidden>
                <div className={cn("absolute inset-y-0 left-0", ci >= 65 ? "bg-aureus-emerald" : ci < 35 ? "bg-aureus-crimson" : "bg-aureus-gold")}
                     style={{ width: `${Math.max(0, Math.min(100, ci))}%` }} />
                <span className="absolute -top-1 -bottom-1 w-px bg-aureus-rulestrong" style={{ left: "35%" }} />
                <span className="absolute -top-1 -bottom-1 w-px bg-aureus-rulestrong" style={{ left: "65%" }} />
              </div>
              <div className="relative h-4 mt-1.5 font-mono-num text-[10px] text-aureus-muted" aria-hidden>
                <span className="absolute -translate-x-1/2" style={{ left: "35%" }}>35 sell</span>
                <span className="absolute -translate-x-1/2" style={{ left: "65%" }}>65 buy</span>
              </div>
            </div>
            <div className="min-w-0">
              {data.conviction != null && (
                <StatColumns
                  items={[
                    { label: "Conviction", value: data.conviction.toFixed(0), sub: data.conviction >= 60 ? "high" : data.conviction >= 30 ? "moderate" : "low" },
                    {
                      label: "Pillar agreement", value: `${((data.agreement ?? 0) * 100).toFixed(0)}%`,
                      sub: (data.agreement ?? 0) >= 0.8 ? "aligned" : (data.agreement ?? 0) >= 0.4 ? "partly split" : "conflicting",
                    },
                    { label: "Data completeness", value: `${(data.overall_data_completeness * 100).toFixed(0)}%`, sub: "of inputs computed" },
                  ]}
                />
              )}
              <p className="px-5 py-3 border-t border-aureus-rule text-[12px] text-aureus-muted leading-relaxed">{convictionNote(data)}</p>
            </div>
          </div>
        ) : loading ? (
          <div className="border-t border-aureus-rule"><SkeletonStatColumns columns={4} /></div>
        ) : null}
      </header>

      {loading && <AnalysisSkeleton ticker={ticker} />}

      {error && !loading && (
        <div className="max-w-xl space-y-3">
          <ErrorNote>{error}</ErrorNote>
          <Button variant="outline" size="sm" onClick={() => load()}>Retry</Button>
        </div>
      )}

      {ready && (
        <>
          <PillarLedger
            pillars={[
              { key: "fundamental", title: "Fundamental", score: data.fundamental_score, weight: data.module_weights_used.fundamental ?? 0, completeness: f?.data_completeness ?? 0, signals: f?.signal_breakdown ?? [] },
              { key: "technical", title: "Technical", score: data.technical_score, weight: data.module_weights_used.technical ?? 0, completeness: t?.data_completeness ?? 0, signals: t?.signal_breakdown ?? [] },
              { key: "sentiment", title: "Sentiment", score: data.sentiment_score, weight: data.module_weights_used.sentiment ?? 0, completeness: sn?.data_completeness ?? 0, signals: sn?.signal_breakdown ?? [] },
            ]}
          />

          {sn && <SentimentCard sentiment={sn} />}

          {/* Above the theses on purpose: the cases below cite these events. */}
          <CatalystTimeline ticker={ticker} horizon={horizon} userId={userId} initial={data.catalysts} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
            <ThesisCard thesis={data.bull_case} />
            <ThesisCard thesis={data.bear_case} />
          </div>

          {data.sector_comparison?.sector && <SectorComparisonCard data={data.sector_comparison} />}

          <Card flat>
            <CardHeader><CardTitle>Key figures</CardTitle></CardHeader>
            <div className="grid grid-cols-2 md:grid-cols-4 border-l border-aureus-rule -ml-px">
              <MetricCell label="P/E" value={fmtNum(f?.pe_ratio, 1, "x")} hint="Trailing" />
              <MetricCell label="P/B" value={fmtNum(f?.pb_ratio as number | null, 1, "x")} />
              <MetricCell label="Gross margin" value={fmtPct(f?.gross_margin)} />
              <MetricCell label="ROE" value={fmtPct(f?.roe)} />
              <MetricCell label="Debt / equity" value={fmtNum(f?.debt_to_equity)} />
              <MetricCell label="Free cash flow" value={f?.free_cash_flow == null ? "—" : `$${(f.free_cash_flow / 1e9).toFixed(1)}B`} hint="Trailing twelve months" />
              <MetricCell
                label="DCF intrinsic"
                value={f?.dcf_detail ? `$${f.dcf_detail.intrinsic_value_per_share.toFixed(2)}` : "—"}
                hint={f?.dcf_detail
                  ? f.dcf_detail.margin_of_safety >= 0
                    ? `${(f.dcf_detail.margin_of_safety * 100).toFixed(0)}% margin of safety`
                    : `${(Math.abs(f.dcf_detail.margin_of_safety) * 100).toFixed(0)}% premium to model`
                  : "Not computed"}
              />
              <MetricCell label="RSI (14)" value={fmtNum(t?.rsi_14, 0)} />
              <MetricCell label="Operating margin" value={fmtPct(f?.operating_margin)} />
              <MetricCell label="Revenue growth" value={fmtPct(f?.revenue_growth_yoy)} hint="Year over year" />
              <MetricCell label="News sentiment" value={sn?.news_computed ? `${sn.news_score.toFixed(0)}/100` : "—"} hint={sn?.news_computed ? `${sn.news_document_count} articles` : "Not measured"} />
              <MetricCell label="Sentiment velocity" value={sn ? `${sn.polarity_velocity >= 0 ? "+" : ""}${sn.polarity_velocity.toFixed(2)}` : "—"} hint={sn?.velocity_label} />
            </div>
            <CardContent className="pt-4 space-y-2">
              <p className="text-[12px] text-aureus-muted leading-relaxed">
                Beta, alpha, Sharpe ratio and volatility are research statistics, and they live with factor exposures, Monte
                Carlo and VaR in the{" "}
                <a href={`/quant-lab?ticker=${ticker}`} className="text-aureus-gold hover:underline">Quant Lab</a>.
              </p>
              {f?.dcf_skip_reason && !f.dcf_detail && (
                <p className="text-[12px] text-aureus-muted leading-relaxed">
                  <span className="text-aureus-gold">DCF not run.</span> {f.dcf_skip_reason}
                </p>
              )}
            </CardContent>
          </Card>

          <Card flat>
            <CardHeader><CardTitle>Price and signal</CardTitle></CardHeader>
            <CardContent>
              <PriceChart ticker={ticker} horizon={horizon} days={horizon === "short_term" ? 90 : horizon === "long_term" ? 730 : 365} />
            </CardContent>
          </Card>

          <Card flat>
            <CardHeader><CardTitle>Why this score</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <p className="text-[14px] text-aureus-soft leading-relaxed max-w-[75ch]">{data.reasoning}</p>
              <p className="text-[11.5px] text-aureus-muted">
                {data.reasoning_source === "llm_polished"
                  ? "Generated from the computed metrics, then edited by a language model under compliance rules."
                  : "Generated from the computed metrics."}{" "}
                Informational only, not financial advice.
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

/** useSearchParams needs a Suspense boundary for the production build. */
export default function TickerAnalysisPage() {
  return (
    <Suspense fallback={<AnalysisSkeleton ticker="" />}>
      <TickerAnalysisView />
    </Suspense>
  );
}
