"use client";
import { useEffect, useRef, useState } from "react";
import { connectAlertStream } from "@/lib/websocket";
import type { AlertMessage } from "@/lib/websocket";
import { getRecentNews, refreshNews } from "@/lib/api";
import type { NewsArticle } from "@/lib/api";

interface Alert {
  id: string;
  ticker?: string;
  headline?: string;
  message?: string;
  severity?: "low" | "medium" | "high" | "critical";
  sentiment_score?: number;
  beta_volatility_impact?: number;
  dispatched_at?: string;
  type: string;
}

const SEVERITY_COLORS = {
  low:      "border-aureus-muted   text-aureus-muted",
  medium:   "border-aureus-gold    text-aureus-gold",
  high:     "border-orange-500     text-orange-400",
  critical: "border-aureus-red     text-aureus-red",
};
const SEVERITY_BG = {
  low: "bg-gray-950/20", medium: "bg-amber-950/20", high: "bg-orange-950/20", critical: "bg-red-950/20",
};

function sentimentColor(score: number): string {
  if (score > 0.15) return "text-aureus-green";
  if (score < -0.15) return "text-aureus-red";
  return "text-aureus-muted";
}

export default function AlertFeed({ userId }: { userId: string }) {
  const [tab, setTab] = useState<"portfolio" | "market">("portfolio");
  const [alerts,      setAlerts]      = useState<Alert[]>([]);
  const [marketNews,  setMarketNews]  = useState<NewsArticle[]>([]);
  const [connected,   setConnected]   = useState(false);
  const [newsLoading, setNewsLoading] = useState(true);
  const [refreshing,  setRefreshing]  = useState(false);
  const [newsError,   setNewsError]   = useState<string | null>(null);
  const [lastRefreshInfo, setLastRefreshInfo] = useState<string | null>(null);

  // Personal portfolio alerts — live WebSocket
  useEffect(() => {
    if (!userId) return;
    const ws = connectAlertStream(
      userId,
      (msg: AlertMessage) => {
        if (msg.type === "connected") { setConnected(true); return; }
        if (msg.type === "alert" || msg.type === "pending_alerts") {
          if (msg.type === "pending_alerts") {
            const backlog = (msg.alerts as Alert[]) || [];
            setAlerts((prev) => [...backlog.reverse(), ...prev]);
          } else {
            const alert: Alert = {
              id: crypto.randomUUID(),
              ticker: msg.ticker as string,
              headline: msg.headline as string,
              message: msg.message as string,
              severity: (msg.severity as Alert["severity"]) || "low",
              sentiment_score: msg.sentiment_score as number,
              beta_volatility_impact: msg.beta_volatility_impact as number,
              dispatched_at: msg.dispatched_at as string,
              type: "alert",
            };
            setAlerts((prev) => [alert, ...prev].slice(0, 50));
          }
        }
      },
      () => setConnected(false),
    );
    return () => ws.close();
  }, [userId]);

  // General market news — REST, powers the "market" tab so there's always
  // something visible even if you hold no matching tickers yet.
  const loadMarketNews = async () => {
    setNewsLoading(true);
    setNewsError(null);
    try {
      const res = await getRecentNews(30, userId || undefined);
      setMarketNews(res.articles);
    } catch (e: unknown) {
      setNewsError(e instanceof Error ? e.message : "Could not load market news");
    } finally {
      setNewsLoading(false);
    }
  };

  useEffect(() => { loadMarketNews(); }, []);

  const handleManualRefresh = async () => {
    setRefreshing(true);
    setNewsError(null);
    setLastRefreshInfo(null);
    try {
      const result = await refreshNews();
      const stages = result.stages as Record<string, unknown>;
      const finnhub = (stages.finnhub_ingested as number) ?? 0;
      const rss = (stages.rss_ingested as number) ?? 0;
      const forwarded = (stages.preprocessed_forwarded as number) ?? 0;
      setLastRefreshInfo(
        `Found ${finnhub + rss} new article${finnhub + rss === 1 ? "" : "s"} ` +
        `(${finnhub} Finnhub, ${rss} RSS) — ${forwarded} passed the sentiment filter and ` +
        `queued for analysis. If this shows 0, sources may have already been checked recently, ` +
        `or feeds may be unreachable — check backend logs for RSS/Finnhub errors.`
      );
      await new Promise((r) => setTimeout(r, 1500)); // give preprocessing a beat to land in DB
      await loadMarketNews();
    } catch (e: unknown) {
      setNewsError(e instanceof Error ? e.message : "Refresh failed — check that the backend is reachable");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 text-xs">
          {(["portfolio", "market"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
                    className={`px-3 py-1 rounded-full transition-colors ${
                      tab === t ? "bg-aureus-gold text-black font-semibold" : "text-aureus-muted hover:text-white"
                    }`}>
              {t === "portfolio" ? "My Portfolio" : "Market News"}
            </button>
          ))}
        </div>
        {tab === "market" && (
          <button onClick={handleManualRefresh} disabled={refreshing}
                  className="text-xs text-aureus-muted hover:text-white transition-colors disabled:opacity-50">
            {refreshing ? "Refreshing..." : "↻ Refresh"}
          </button>
        )}
      </div>

      {tab === "portfolio" && (
        <>
          <div className="flex items-center gap-2 text-xs text-aureus-muted">
            <div className={`w-2 h-2 rounded-full ${connected ? "bg-aureus-green pulse-gold" : "bg-aureus-muted"}`} />
            {connected ? "Live — receiving portfolio alerts" : "Connecting to alert stream..."}
          </div>

          {alerts.length === 0 ? (
            <div className="rounded-lg border border-aureus-border p-10 text-center" style={{ background: "var(--surface)" }}>
              <div className="text-3xl mb-2">📡</div>
              <p className="text-aureus-muted text-sm">
                No alerts yet for your holdings. Check the Market News tab to see everything
                the system is currently picking up, or add positions so we know what to watch.
              </p>
            </div>
          ) : (
            alerts.map((alert) => {
              const severity = alert.severity || "low";
              return (
                <div key={alert.id} className={`rounded-lg border p-4 space-y-2 ${SEVERITY_COLORS[severity]} ${SEVERITY_BG[severity]}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded border ${SEVERITY_COLORS[severity]}`}>{severity}</span>
                      {alert.ticker && <span className="text-white font-bold">{alert.ticker}</span>}
                    </div>
                    {alert.sentiment_score !== undefined && (
                      <span className={sentimentColor(alert.sentiment_score)}>
                        Sentiment {alert.sentiment_score >= 0 ? "+" : ""}{alert.sentiment_score.toFixed(2)}
                      </span>
                    )}
                  </div>
                  {alert.headline && <p className="text-white text-sm font-medium">{alert.headline}</p>}
                  {alert.message && <p className="text-aureus-muted text-xs leading-relaxed">{alert.message}</p>}
                  {alert.dispatched_at && <p className="text-aureus-muted text-xs">{new Date(alert.dispatched_at).toLocaleString()}</p>}
                </div>
              );
            })
          )}
        </>
      )}

      {tab === "market" && (
        <>
          {newsError && (
            <div className="rounded-lg border border-aureus-red bg-red-950/20 p-3 text-aureus-red text-xs">
              {newsError}
            </div>
          )}
          {lastRefreshInfo && !newsError && (
            <div className="rounded-lg border border-aureus-border bg-white/[0.02] p-3 text-aureus-muted text-xs leading-relaxed">
              {lastRefreshInfo}
            </div>
          )}
          {newsLoading ? (
            <div className="text-center py-8 text-aureus-muted text-sm">Loading recent market news...</div>
          ) : marketNews.length === 0 ? (
            <div className="rounded-lg border border-aureus-border p-10 text-center" style={{ background: "var(--surface)" }}>
              <div className="text-3xl mb-2">📰</div>
              <p className="text-aureus-muted text-sm mb-3">
                No processed articles yet. The pipeline polls sources on a schedule —
                click refresh to run one cycle immediately.
              </p>
              <button onClick={handleManualRefresh} disabled={refreshing}
                      className="text-xs bg-aureus-gold text-black font-semibold px-3 py-1.5 rounded disabled:opacity-50">
                {refreshing ? "Refreshing..." : "Refresh Now"}
              </button>
            </div>
          ) : (
            marketNews.map((article) => (
              <a key={article.id} href={article.source_url} target="_blank" rel="noopener noreferrer"
                 className="block rounded-lg border border-aureus-border p-4 space-y-1.5 hover:border-aureus-gold/50 transition-colors"
                 style={{ background: "var(--surface)" }}>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-aureus-gold font-semibold">{article.ticker}</span>
                  <span className={`text-xs ${sentimentColor(article.sentiment_score)}`}>
                    {article.sentiment_score >= 0 ? "+" : ""}{article.sentiment_score.toFixed(2)}
                  </span>
                </div>
                <p className="text-white text-sm font-medium leading-snug">{article.headline}</p>
                {article.summary && <p className="text-aureus-muted text-xs leading-relaxed line-clamp-2">{article.summary}</p>}
                <div className="flex items-center justify-between text-xs text-aureus-muted pt-1">
                  <span>{article.source}</span>
                  <span>{article.published_at ? new Date(article.published_at).toLocaleString() : ""}</span>
                </div>
              </a>
            ))
          )}
        </>
      )}
    </div>
  );
}
