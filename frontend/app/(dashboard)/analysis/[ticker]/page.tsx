"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import PillarCard from "@/components/analysis/PillarCard";
import ThesisCard from "@/components/analysis/ThesisCard";
import SectorComparisonCard from "@/components/analysis/SectorComparisonCard";
import SentimentCard from "@/components/analysis/SentimentCard";
import PriceChart from "@/components/charts/PriceChart";
import { getFullAnalysis } from "@/lib/api";
import type { FullAnalysis } from "@/lib/api";

type Horizon = "short_term" | "medium_term" | "long_term";

const HORIZONS: { value: Horizon; label: string; sub: string }[] = [
  { value: "short_term", label: "Short-Term", sub: "1d – 1m" },
  { value: "medium_term", label: "Medium-Term", sub: "1m – 6m" },
  { value: "long_term", label: "Long-Term", sub: "1y+" },
];

/** STRONG BUY / BUY / HOLD / SELL / STRONG SELL from signal + strength. */
function verdict(a: FullAnalysis): { label: string; cls: string } {
  const strong = a.signal_strength === "STRONG";
  if (a.signal === "BUY")
    return strong
      ? { label: "STRONG BUY", cls: "bg-aureus-verdigris text-aureus-ink" }
      : { label: "BUY", cls: "bg-aureus-verdigris/10 text-aureus-verdigris border border-aureus-verdigrisdim/40" };
  if (a.signal === "SELL")
    return strong
      ? { label: "STRONG SELL", cls: "bg-aureus-oxblood text-aureus-text" }
      : { label: "SELL", cls: "bg-aureus-oxblood/10 text-aureus-oxblood border border-aureus-oxblooddim/40" };
  return { label: "HOLD", cls: "bg-aureus-rule/40 text-aureus-gold border border-aureus-gold/40" };
}

const fmtPct = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(d)}%`;
const fmtNum = (v: number | null | undefined, d = 2, suffix = "") =>
  v == null ? "—" : `${v.toFixed(d)}${suffix}`;

function MetricTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
      <div className="text-[10px] uppercase tracking-wider text-aureus-muted">{label}</div>
      <div className="text-base font-semibold text-aureus-text mt-0.5 font-mono">{value}</div>
      {hint && <div className="text-[10px] text-aureus-muted mt-0.5">{hint}</div>}
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

  // The horizon lives in the URL, not in component state.
  //
  // As component state it was silently discarded on every navigation:
  // moving from /analysis/AAPL to /analysis/NVDA remounts this component,
  // useState re-runs its initialiser, and the horizon you picked reverted
  // to medium_term. In the URL it survives navigation, survives a reload,
  // and makes "NVDA on a short-term view" a link you can send someone.
  const urlHorizon = searchParams.get("horizon");
  const horizon: Horizon = HORIZONS.some((h) => h.value === urlHorizon)
    ? (urlHorizon as Horizon)
    : "medium_term";

  const setHorizon = (h: Horizon) =>
    router.replace(`/analysis/${ticker}?horizon=${h}`, { scroll: false });
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
      if (!res.result) throw new Error(res.error || "No analysis returned");
      setData(res.result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [ticker, horizon, userId]);

  useEffect(() => { load(); }, [load]);

  const v = data ? verdict(data) : null;
  const f = data?.fundamental;
  const t = data?.technical;
  const sn = data?.sentiment;

  return (
    <div className="space-y-6">
      {/* ── Executive header ───────────────────────────────────── */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold text-aureus-text tracking-tight">{ticker}</h1>
                {v && <span className={`rounded px-2.5 py-1 text-xs font-bold tracking-wider ${v.cls}`}>{v.label}</span>}
              </div>
              {data && (
                <p className="text-xs text-aureus-muted mt-1">
                  {data.time_horizon} · market data via {data.market_data_provider} · fundamentals via{" "}
                  {data.fundamental_data_provider}
                </p>
              )}
            </div>

            {/* Ticker switcher */}
            <form
              onSubmit={(e) => { e.preventDefault(); if (search.trim()) router.push(`/analysis/${search.trim().toUpperCase()}?horizon=${horizon}`); }}
              className="flex gap-2"
            >
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-aureus-muted" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Another ticker"
                  className="w-40 rounded-md border border-aureus-rule pl-8 pr-3 py-1.5 text-sm text-aureus-text
                             placeholder:text-aureus-muted/50 focus:outline-none focus:border-aureus-gold"
                  style={{ background: "var(--bg)" }}
                />
              </div>
              <Button type="submit" size="sm" variant="outline">Go</Button>
            </form>
          </div>

          {/* Direction and conviction, reported separately.
              A single number cannot distinguish "all three pillars agree
              this is fairly valued" from "the three are at war" — both
              land near 50, and they mean opposite things to someone
              deciding what to do. */}
          {data && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-aureus-muted uppercase tracking-wider">Confidence index</span>
                  <span className="font-mono-num text-aureus-text">{data.confidence_index.toFixed(1)} / 100</span>
                </div>
                <div className="h-2 rounded-full bg-aureus-panelhigh overflow-hidden relative">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.max(0, Math.min(100, data.confidence_index))}%`,
                      background: data.confidence_index >= 65 ? "var(--verdigris)"
                                : data.confidence_index < 35 ? "var(--oxblood)" : "var(--gold)",
                    }}
                  />
                </div>
              </div>

              {data.conviction != null && (
                <div className="grid sm:grid-cols-3 gap-x-6 gap-y-3 pt-1">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Conviction</div>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="font-mono-num text-lg text-aureus-text">{data.conviction.toFixed(0)}</span>
                      <span className="text-[11px] text-aureus-muted">
                        {data.conviction >= 60 ? "high" : data.conviction >= 30 ? "moderate" : "low"}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Pillar agreement</div>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="font-mono-num text-lg text-aureus-text">
                        {((data.agreement ?? 0) * 100).toFixed(0)}%
                      </span>
                      <span className="text-[11px] text-aureus-muted">
                        {(data.agreement ?? 0) >= 0.8 ? "aligned"
                          : (data.agreement ?? 0) >= 0.4 ? "partly split" : "conflicting"}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-aureus-muted">Data completeness</div>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="font-mono-num text-lg text-aureus-text">
                        {(data.overall_data_completeness * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Name the actual cause. "The pillars disagree" printed
                  next to an agreement reading of 100% is worse than no
                  explanation — the three inputs to conviction fail
                  independently and the reader needs to know which one did. */}
              <p className="text-[11px] text-aureus-muted leading-relaxed">
                {(() => {
                  const conv = data.conviction ?? 0;
                  const agree = data.agreement ?? 0;
                  const complete = data.overall_data_completeness;
                  if (conv >= 30) {
                    return "Conviction combines how far the evidence leans, whether the three pillars agree, and how much data backed the run.";
                  }
                  if (agree < 0.4) {
                    return "Low conviction: the three pillars point in different directions, so the composite is near neutral by cancellation rather than by consensus.";
                  }
                  if (complete < 0.6) {
                    return "Low conviction: too little data backed this run. Pillars with missing inputs had their weight redistributed to the ones that computed.";
                  }
                  return "Low conviction: the pillars agree on direction, but the lean is mild. Consistent weak evidence is still weak evidence — treat the direction as loosely held.";
                })()}
              </p>
            </div>
          )}

          {/* Horizon tabs */}
          <div className="flex gap-1.5">
            {HORIZONS.map((h) => (
              <button
                key={h.value}
                onClick={() => setHorizon(h.value)}
                className={`flex-1 rounded-md border px-3 py-2 text-left transition-colors ${
                  horizon === h.value
                    ? "border-aureus-gold bg-aureus-gold/10"
                    : "border-aureus-rule hover:border-aureus-muted"
                }`}
              >
                <div className={`text-xs font-medium ${horizon === h.value ? "text-aureus-gold" : "text-aureus-text"}`}>
                  {h.label}
                </div>
                <div className="text-[10px] text-aureus-muted">{h.sub}</div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {loading && (
        <Card><CardContent className="p-16 text-center text-aureus-muted text-sm">
          Running ensemble analysis for {ticker}…
        </CardContent></Card>
      )}

      {error && !loading && (
        <Card><CardContent className="p-8 text-center space-y-3">
          <p className="text-aureus-oxblood text-sm">{error}</p>
          <Button variant="outline" size="sm" onClick={load}>Retry</Button>
        </CardContent></Card>
      )}

      {data && !loading && (
        <>
          {/* ── Pillar scores ─────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <PillarCard title="Fundamental" score={data.fundamental_score}
                        weight={data.module_weights_used.fundamental ?? 0}
                        completeness={f?.data_completeness ?? 0}
                        signals={f?.signal_breakdown ?? []} />
            <PillarCard title="Technical" score={data.technical_score}
                        weight={data.module_weights_used.technical ?? 0}
                        completeness={t?.data_completeness ?? 0}
                        signals={t?.signal_breakdown ?? []} />
            <PillarCard title="Sentiment" score={data.sentiment_score}
                        weight={data.module_weights_used.sentiment ?? 0}
                        completeness={sn?.data_completeness ?? 0}
                        signals={sn?.signal_breakdown ?? []} />
          </div>

          {/* ── Sentiment detail ──────────────────────────────── */}
          {sn && <SentimentCard sentiment={sn} />}

          {/* ── Bull vs Bear ──────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            <ThesisCard thesis={data.bull_case} />
            <ThesisCard thesis={data.bear_case} />
          </div>

          {data.sector_comparison?.sector && (
            <SectorComparisonCard data={data.sector_comparison} />
          )}

          {/* ── Key metrics grid ──────────────────────────────── */}
          <Card>
            <CardHeader><CardTitle>Key Metrics</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricTile label="P/E" value={fmtNum(f?.pe_ratio, 1, "x")} hint="Trailing" />
                <MetricTile label="P/B" value={fmtNum(f?.pb_ratio as number | null, 1, "x")} />
                <MetricTile label="Gross Margin" value={fmtPct(f?.gross_margin)} />
                <MetricTile label="ROE" value={fmtPct(f?.roe)} />

                <MetricTile label="Debt / Equity" value={fmtNum(f?.debt_to_equity)} />
                <MetricTile
                  label="Free Cash Flow"
                  value={f?.free_cash_flow == null ? "—" : `$${(f.free_cash_flow / 1e9).toFixed(1)}B`}
                  hint="Trailing twelve months"
                />
                <MetricTile
                  label="DCF Intrinsic"
                  value={f?.dcf_detail ? `$${f.dcf_detail.intrinsic_value_per_share.toFixed(2)}` : "—"}
                  hint={f?.dcf_detail
                    ? f.dcf_detail.margin_of_safety >= 0
                      ? `${(f.dcf_detail.margin_of_safety * 100).toFixed(0)}% margin of safety`
                      : `${(Math.abs(f.dcf_detail.margin_of_safety) * 100).toFixed(0)}% premium to model`
                    : "Not computed"}
                />
                <MetricTile label="RSI (14)" value={fmtNum(t?.rsi_14, 0)} />

                <MetricTile label="Operating Margin" value={fmtPct(f?.operating_margin)} />
                <MetricTile label="Revenue Growth" value={fmtPct(f?.revenue_growth_yoy)} hint="Year over year" />
                <MetricTile label="News Sentiment"
                            value={sn?.news_computed ? `${sn.news_score.toFixed(0)}/100` : "—"}
                            hint={sn?.news_computed ? `${sn.news_document_count} articles` : "Not measured"} />
                <MetricTile label="Sentiment Velocity"
                            value={sn ? `${sn.polarity_velocity >= 0 ? "+" : ""}${sn.polarity_velocity.toFixed(2)}` : "—"}
                            hint={sn?.velocity_label} />
              </div>

              {/* Beta, alpha, Sharpe and volatility moved to the Quant Lab —
                  they are research statistics, not a third opinion to average
                  against a DCF. Point users at where they now live. */}
              <p className="text-[11px] text-aureus-muted mt-3 leading-relaxed">
                Looking for beta, alpha, Sharpe or volatility? Factor exposures, Monte Carlo and
                VaR now live in the{" "}
                <a href={`/quant-lab?ticker=${ticker}`} className="text-aureus-gold hover:underline">
                  Quant Lab
                </a>.
              </p>

              {f?.dcf_skip_reason && !f.dcf_detail && (
                <p className="text-[11px] text-aureus-muted mt-3 leading-relaxed">
                  <span className="text-aureus-gold">DCF not run:</span> {f.dcf_skip_reason}
                </p>
              )}
            </CardContent>
          </Card>

          {/* ── Chart ─────────────────────────────────────────── */}
          <Card>
            <CardHeader><CardTitle>Price &amp; Signal</CardTitle></CardHeader>
            <CardContent>
              <PriceChart ticker={ticker} horizon={horizon}
                          days={horizon === "short_term" ? 90 : horizon === "long_term" ? 730 : 365} />
            </CardContent>
          </Card>

          {/* ── Narrative ─────────────────────────────────────── */}
          <Card>
            <CardHeader><CardTitle>Why This Score</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-aureus-text leading-relaxed">{data.reasoning}</p>
              <p className="text-[11px] text-aureus-muted">
                Generated {data.reasoning_source === "llm_polished" ? "deterministically, then polished by an LLM under compliance guardrails" : "deterministically from the computed metrics"} ·
                Informational only, not financial advice.
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

/**
 * useSearchParams() opts this subtree into client-side rendering, and
 * Next fails the production build unless it sits under a Suspense
 * boundary.
 */
export default function TickerAnalysisPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-sm text-aureus-muted">Loading analysis…</div>}>
      <TickerAnalysisView />
    </Suspense>
  );
}
