"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
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
      : { label: "BUY", cls: "bg-green-950/60 text-aureus-green border border-aureus-green/40" };
  if (a.signal === "SELL")
    return strong
      ? { label: "STRONG SELL", cls: "bg-aureus-oxblood text-white" }
      : { label: "SELL", cls: "bg-red-950/60 text-aureus-red border border-aureus-red/40" };
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
      <div className="text-base font-semibold text-white mt-0.5 font-mono">{value}</div>
      {hint && <div className="text-[10px] text-aureus-muted mt-0.5">{hint}</div>}
    </div>
  );
}

export default function TickerAnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const ticker = String(params?.ticker ?? "").toUpperCase();

  const [horizon, setHorizon] = useState<Horizon>("medium_term");
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
                <h1 className="text-3xl font-bold text-white tracking-tight">{ticker}</h1>
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
              onSubmit={(e) => { e.preventDefault(); if (search.trim()) router.push(`/analysis/${search.trim().toUpperCase()}`); }}
              className="flex gap-2"
            >
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-aureus-muted" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Another ticker"
                  className="w-40 rounded-md border border-aureus-border pl-8 pr-3 py-1.5 text-sm text-white
                             placeholder:text-aureus-muted/50 focus:outline-none focus:border-aureus-gold"
                  style={{ background: "var(--bg)" }}
                />
              </div>
              <Button type="submit" size="sm" variant="outline">Go</Button>
            </form>
          </div>

          {/* Confidence meter */}
          {data && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-aureus-muted uppercase tracking-wider">Confidence Index</span>
                <span className="font-mono text-white">{data.confidence_index.toFixed(1)} / 100</span>
              </div>
              <div className="h-2 rounded-full bg-aureus-rule overflow-hidden relative">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max(0, Math.min(100, data.confidence_index))}%`,
                    background: data.confidence_index >= 65 ? "#22c55e"
                              : data.confidence_index < 35 ? "#ef4444" : "#d4a843",
                  }}
                />
              </div>
              <p className="text-[11px] text-aureus-muted">
                Overall data completeness {(data.overall_data_completeness * 100).toFixed(0)}% — pillars
                with missing inputs have their weight redistributed, so a low figure here means the
                score rests on fewer signals than usual.
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
                    : "border-aureus-border hover:border-aureus-muted"
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
          <p className="text-aureus-red text-sm">{error}</p>
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
