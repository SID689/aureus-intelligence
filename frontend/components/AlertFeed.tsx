"use client";
import { useEffect, useRef, useState } from "react";
import { connectAlertStream } from "@/lib/websocket";
import type { AlertMessage } from "@/lib/websocket";

interface Alert {
  id: string;
  ticker?: string;
  headline?: string;
  message?: string;
  severity?: "low" | "medium" | "high" | "critical";
  sentiment_score?: number;
  beta_volatility_impact?: number;
  created_at?: string;
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
  low:      "bg-gray-950/20",
  medium:   "bg-amber-950/20",
  high:     "bg-orange-950/20",
  critical: "bg-red-950/20",
};

export default function AlertFeed({ userId }: { userId: string }) {
  const [alerts,    setAlerts]    = useState<Alert[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = connectAlertStream(
      userId,
      (msg: AlertMessage) => {
        if (msg.type === "connected") {
          setConnected(true);
          return;
        }
        if (msg.type === "alert" || msg.type === "pending_alerts") {
          if (msg.type === "pending_alerts") {
            const backlog = (msg.alerts as Alert[]) || [];
            setAlerts((prev) => [...backlog.reverse(), ...prev]);
          } else {
            const alert: Alert = {
              id:                   crypto.randomUUID(),
              ticker:               msg.ticker as string,
              headline:             msg.headline as string,
              message:              msg.message as string,
              severity:             (msg.severity as Alert["severity"]) || "low",
              sentiment_score:      msg.sentiment_score as number,
              beta_volatility_impact: msg.beta_volatility_impact as number,
              dispatched_at:        msg.dispatched_at as string,
              type:                 "alert",
            };
            setAlerts((prev) => [alert, ...prev].slice(0, 50));
          }
        }
      },
      () => setConnected(false),
    );
    wsRef.current = ws;
    return () => ws.close();
  }, [userId]);

  return (
    <div className="space-y-3">
      {/* Connection status */}
      <div className="flex items-center gap-2 text-xs text-aureus-muted">
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-aureus-green pulse-gold" : "bg-aureus-muted"}`} />
        {connected ? "Live — receiving portfolio alerts" : "Connecting to alert stream..."}
      </div>

      {/* Alert list */}
      {alerts.length === 0 ? (
        <div className="rounded-lg border border-aureus-border p-12 text-center"
             style={{ background: "var(--surface)" }}>
          <div className="text-4xl mb-3">📡</div>
          <p className="text-aureus-muted text-sm">
            No alerts yet. The system monitors news in real-time and will notify you
            when events affect your portfolio holdings.
          </p>
        </div>
      ) : (
        alerts.map((alert) => {
          const severity = alert.severity || "low";
          return (
            <div key={alert.id}
                 className={`rounded-lg border p-4 space-y-2 ${SEVERITY_COLORS[severity]} ${SEVERITY_BG[severity]}`}>
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded border ${SEVERITY_COLORS[severity]}`}>
                    {severity}
                  </span>
                  {alert.ticker && (
                    <span className="text-white font-bold">{alert.ticker}</span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-aureus-muted">
                  {alert.sentiment_score !== undefined && (
                    <span className={alert.sentiment_score >= 0 ? "text-aureus-green" : "text-aureus-red"}>
                      Sentiment {alert.sentiment_score >= 0 ? "+" : ""}{alert.sentiment_score?.toFixed(2)}
                    </span>
                  )}
                  {alert.beta_volatility_impact !== undefined && (
                    <span className={alert.beta_volatility_impact >= 0 ? "text-aureus-green" : "text-aureus-red"}>
                      Impact {alert.beta_volatility_impact >= 0 ? "+" : ""}
                      {(alert.beta_volatility_impact * 100).toFixed(2)}%
                    </span>
                  )}
                </div>
              </div>

              {/* Headline */}
              {alert.headline && (
                <p className="text-white text-sm font-medium">{alert.headline}</p>
              )}

              {/* Message */}
              {alert.message && (
                <p className="text-aureus-muted text-xs leading-relaxed">
                  {alert.message}
                </p>
              )}

              {/* Timestamp */}
              {alert.dispatched_at && (
                <p className="text-aureus-muted text-xs">
                  {new Date(alert.dispatched_at).toLocaleString()}
                </p>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
