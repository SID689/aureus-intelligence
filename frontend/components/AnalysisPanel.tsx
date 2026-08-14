"use client";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { runQuickAnalysis } from "@/lib/api";
import type { AnalysisResult } from "@/lib/api";

const HORIZONS = [
  { value: "short_term",  label: "Short Term"  },
  { value: "medium_term", label: "Medium Term" },
  { value: "long_term",   label: "Long Term"   },
] as const;

const SIGNAL_STYLE = {
  BUY:  { bg: "bg-green-950/40",  border: "border-aureus-green", text: "text-aureus-green"  },
  HOLD: { bg: "bg-amber-950/30",  border: "border-aureus-gold",  text: "text-aureus-gold"   },
  SELL: { bg: "bg-red-950/30",    border: "border-aureus-red",   text: "text-aureus-red"    },
};

export default function AnalysisPanel() {
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const [ticker,   setTicker]   = useState("AAPL");
  const [horizon,  setHorizon]  = useState<"short_term" | "medium_term" | "long_term">("medium_term");
  const [loading,  setLoading]  = useState(false);
  const [result,   setResult]   = useState<AnalysisResult | null>(null);
  const [error,    setError]    = useState<string | null>(null);

  const handleAnalyse = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runQuickAnalysis(ticker.toUpperCase(), userId, horizon);
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const r = result?.result;
  const signal = r?.signal;
  const ss = signal ? SIGNAL_STYLE[signal] : null;
  const weights = r?.module_weights_used || {};
  const weightsAreStandard =
    Math.abs((weights.fundamental ?? 0.35) - 0.35) < 0.02 &&
    Math.abs((weights.technical ?? 0.35) - 0.35) < 0.02;

  return (
    <div className="space-y-4">
      {/* Input form */}
      <div className="rounded-lg border border-aureus-border p-4 flex flex-wrap gap-3 items-end"
           style={{ background: "var(--surface)" }}>
        <div className="flex-1 min-w-32">
          <label className="text-xs text-aureus-muted mb-1 block">Ticker</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyse()}
            placeholder="AAPL"
            maxLength={10}
            className="w-full bg-transparent border border-aureus-border rounded px-3 py-2
                       text-white text-sm focus:outline-none focus:border-aureus-gold transition-colors"
          />
        </div>
        <div>
          <label className="text-xs text-aureus-muted mb-1 block">Horizon</label>
          <select
            value={horizon}
            onChange={(e) => setHorizon(e.target.value as typeof horizon)}
            className="bg-transparent border border-aureus-border rounded px-3 py-2
                       text-white text-sm focus:outline-none focus:border-aureus-gold"
            style={{ background: "var(--bg)" }}
          >
            {HORIZONS.map((h) => (
              <option key={h.value} value={h.value}>{h.label}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleAnalyse}
          disabled={loading}
          className="px-5 py-2 bg-aureus-gold text-black font-semibold text-sm rounded
                     hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? "Analysing..." : "Analyse"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-aureus-red bg-red-950/20 p-3 text-aureus-red text-sm">
          {error}
        </div>
      )}

      {/* Result */}
      {r && ss && (
        <div className={`rounded-lg border ${ss.border} ${ss.bg} p-5 space-y-5`}>
          {/* Signal header */}
          <div className="flex items-center justify-between">
            <div>
              <span className="text-aureus-muted text-sm">{r.ticker} · {horizon.replace("_", " ")}</span>
              <div className="flex items-center gap-3 mt-1">
                <span className={`text-3xl font-bold ${ss.text}`}>{signal}</span>
                <span className={`text-sm font-medium ${ss.text} opacity-70`}>{r.signal_strength}</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-aureus-muted mb-1">Confidence Index</div>
              <div className={`text-2xl font-bold ${ss.text}`}>
                {r.confidence_index.toFixed(1)}
                <span className="text-sm font-normal text-aureus-muted">/100</span>
              </div>
            </div>
          </div>

          {/* Confidence bar */}
          <div>
            <div className="w-full bg-aureus-border rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${
                  signal === "BUY" ? "bg-aureus-green" :
                  signal === "SELL" ? "bg-aureus-red" : "bg-aureus-gold"
                }`}
                style={{ width: `${r.confidence_index}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-aureus-muted mt-1">
              <span>SELL (0)</span>
              <span>HOLD (35-65)</span>
              <span>BUY (100)</span>
            </div>
          </div>

          {/* Reasoning — the direct fix for "scores need explanations" */}
          {r.reasoning && (
            <div className="rounded-lg border border-aureus-border p-4" style={{ background: "var(--bg)" }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-aureus-gold uppercase tracking-wide">
                  Why this score
                </span>
                <span className="text-xs text-aureus-muted">
                  {r.reasoning_source === "llm_polished" ? "AI-composed" : "Rule-based"}
                </span>
              </div>
              <p className="text-sm text-gray-300 leading-relaxed">{r.reasoning}</p>
            </div>
          )}

          {/* Module scores with weighting transparency */}
          <div>
            {!weightsAreStandard && (
              <p className="text-xs text-aureus-muted mb-2">
                ⚠ Module weights adjusted from this horizon&apos;s standard split because some
                data sources didn&apos;t return complete figures for this ticker — see percentages below.
              </p>
            )}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Fundamental",  score: r.fundamental_score,  weight: weights.fundamental,  completeness: result?.result?.overall_data_completeness },
                { label: "Technical",    score: r.technical_score,    weight: weights.technical },
                { label: "Sentiment",    score: r.sentiment_score,    weight: weights.sentiment },
              ].map(({ label, score, weight }) => (
                <div key={label} className="rounded border border-aureus-border p-3 text-center"
                     style={{ background: "var(--bg)" }}>
                  <div className="text-xs text-aureus-muted mb-1">{label}</div>
                  <div className="text-xl font-bold text-white">{score.toFixed(1)}</div>
                  {weight !== undefined && (
                    <div className="text-xs text-aureus-muted mt-1">{(weight * 100).toFixed(0)}% weight</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Disclaimer */}
          <p className="text-xs text-aureus-muted border-t border-aureus-border pt-3 leading-relaxed">
            {r.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
