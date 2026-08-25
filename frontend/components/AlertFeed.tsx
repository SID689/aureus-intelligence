"use client";
import { useEffect, useState } from "react";
import { Radio, RefreshCw, Rss } from "lucide-react";
import { connectAlertStream } from "@/lib/websocket";
import type { AlertMessage } from "@/lib/websocket";
import { getRecentNews, refreshNews } from "@/lib/api";
import type { NewsArticle } from "@/lib/api";
import { EmptyState, Figure, Segmented, StatusDot, Wire } from "@/components/ui/primitives";
import type { WireItem } from "@/components/ui/primitives";
import { clockTime, sentimentTone, signed } from "@/lib/format";

interface Alert {
  id: string;
  ticker?: string;
  headline?: string;
  message?: string;
  severity?: "low" | "medium" | "high" | "critical";
  sentiment_score?: number;
  dispatched_at?: string;
  type: string;
}

/**
 * Severity is the one place a fourth colour is justified: an alert has a
 * magnitude that is orthogonal to direction, so it can't borrow the
 * up/down pair. Amber sits between muted and oxblood.
 */
const SEVERITY: Record<NonNullable<Alert["severity"]>, { label: string; cls: string }> = {
  low:      { label: "low",      cls: "text-aureus-muted   border-aureus-rule" },
  medium:   { label: "medium",   cls: "text-aureus-gold    border-aureus-gold/40" },
  high:     { label: "high",     cls: "text-aureus-amber   border-aureus-amber/40" },
  critical: { label: "critical", cls: "text-aureus-oxblood border-aureus-oxblood/50" },
};

export default function AlertFeed({ userId }: { userId: string }) {
  const [tab, setTab] = useState<"portfolio" | "market">("portfolio");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [marketNews, setMarketNews] = useState<NewsArticle[]>([]);
  const [connected, setConnected] = useState(false);
  const [newsLoading, setNewsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [refreshNote, setRefreshNote] = useState<string | null>(null);

  // Personal portfolio alerts — live WebSocket
  useEffect(() => {
    if (!userId) return;
    const ws = connectAlertStream(
      userId,
      (msg: AlertMessage) => {
        if (msg.type === "connected") { setConnected(true); return; }
        if (msg.type === "pending_alerts") {
          const backlog = (msg.alerts as Alert[]) || [];
          setAlerts((prev) => [...backlog.reverse(), ...prev]);
          return;
        }
        if (msg.type === "alert") {
          setAlerts((prev) => [{
            id: crypto.randomUUID(),
            ticker: msg.ticker as string,
            headline: msg.headline as string,
            message: msg.message as string,
            severity: (msg.severity as Alert["severity"]) || "low",
            sentiment_score: msg.sentiment_score as number,
            dispatched_at: msg.dispatched_at as string,
            type: "alert",
          }, ...prev].slice(0, 50));
        }
      },
      () => setConnected(false),
    );
    return () => ws.close();
  }, [userId]);

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
    setRefreshNote(null);
    try {
      const result = await refreshNews();
      const stages = result.stages as Record<string, unknown>;
      const finnhub = (stages.finnhub_ingested as number) ?? 0;
      const rss = (stages.rss_ingested as number) ?? 0;
      const forwarded = (stages.preprocessed_forwarded as number) ?? 0;
      const found = finnhub + rss;
      setRefreshNote(
        found === 0
          ? "No new articles. Sources may have been polled recently, or a feed is unreachable — check the backend logs."
          : `${found} new article${found === 1 ? "" : "s"} (${finnhub} Finnhub, ${rss} RSS); ${forwarded} passed the sentiment filter.`
      );
      await new Promise((r) => setTimeout(r, 1500)); // let preprocessing land in the DB
      await loadMarketNews();
    } catch (e: unknown) {
      setNewsError(e instanceof Error ? e.message : "Refresh failed — is the backend reachable?");
    } finally {
      setRefreshing(false);
    }
  };

  const newsItems: WireItem[] = marketNews.map((a) => ({
    id: a.id,
    ticker: a.ticker,
    headline: a.headline,
    source: a.source,
    href: a.source_url,
    at: a.published_at,
    score: a.sentiment_score,
    tone: sentimentTone(a.sentiment_score),
  }));

  return (
    <div className="py-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Segmented
          value={tab}
          onChange={setTab}
          options={[{ value: "portfolio", label: "Mine" }, { value: "market", label: "Market" }]}
        />
        {tab === "market" ? (
          <button onClick={handleManualRefresh} disabled={refreshing}
                  className="flex items-center gap-1.5 text-[11px] text-aureus-muted hover:text-aureus-text transition-colors disabled:opacity-50">
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Refreshing" : "Refresh"}
          </button>
        ) : (
          <span className="flex items-center gap-1.5 text-[11px] text-aureus-muted">
            <StatusDot on={connected} />
            {connected ? "Live" : "Connecting"}
          </span>
        )}
      </div>

      {tab === "portfolio" && (
        alerts.length === 0 ? (
          <EmptyState icon={Radio} title="Nothing on your positions yet">
            When the pipeline finds news that touches something you hold, it lands here.
            The Market tab shows everything it is currently picking up.
          </EmptyState>
        ) : (
          <div>
            {alerts.map((a, i) => {
              const sev = SEVERITY[a.severity || "low"];
              return (
                <div key={a.id} className={`py-3 ${i > 0 ? "border-t border-aureus-rulesoft" : ""}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[9px] font-mono font-semibold uppercase tracking-[0.1em] border rounded px-1.5 py-0.5 ${sev.cls}`}>
                      {sev.label}
                    </span>
                    {a.ticker && <Figure className="text-[11px] text-aureus-gold">{a.ticker}</Figure>}
                    {a.sentiment_score !== undefined && (
                      <Figure tone={sentimentTone(a.sentiment_score)} className="text-[11px]">
                        {signed(a.sentiment_score)}
                      </Figure>
                    )}
                    <Figure tone="muted" className="text-[10px] ml-auto">{clockTime(a.dispatched_at)}</Figure>
                  </div>
                  {a.headline && <p className="text-[13px] text-aureus-text leading-snug">{a.headline}</p>}
                  {a.message && <p className="text-[12px] text-aureus-muted leading-relaxed mt-1">{a.message}</p>}
                </div>
              );
            })}
          </div>
        )
      )}

      {tab === "market" && (
        <>
          {newsError && (
            <div className="rounded-md border border-aureus-oxblooddim bg-aureus-oxblood/10 px-3 py-2 text-[12px] text-aureus-oxblood">
              {newsError}
            </div>
          )}
          {refreshNote && !newsError && (
            <div className="rounded-md border border-aureus-rule bg-aureus-panellift px-3 py-2 text-[12px] text-aureus-muted leading-relaxed">
              {refreshNote}
            </div>
          )}
          {newsLoading ? (
            <p className="py-8 text-center text-[13px] text-aureus-muted">Loading recent coverage…</p>
          ) : (
            <Wire
              items={newsItems}
              empty={
                <EmptyState icon={Rss} title="No processed articles yet"
                            action={
                              <button onClick={handleManualRefresh} disabled={refreshing}
                                      className="text-[11px] bg-aureus-gold text-aureus-ink font-semibold px-3 py-1.5 rounded disabled:opacity-50">
                                {refreshing ? "Refreshing…" : "Run one cycle now"}
                              </button>
                            }>
                  The pipeline polls sources on a schedule. Refresh to run a cycle immediately.
                </EmptyState>
              }
            />
          )}
        </>
      )}
    </div>
  );
}
