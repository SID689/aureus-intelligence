"use client";
/**
 * The bell in the status rail: every Strong Buy alert the user has been
 * sent, including the ones that arrived while they were away.
 *
 * Plan access is checked against the backend rather than the session's
 * tier, which is only as fresh as the last sign-in. A plan without alerts
 * sees a locked bell that explains what it would do; it never sees alerts.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, Check, Lock, X } from "lucide-react";
import { Figure } from "@/components/ui/primitives";
import PushToggle from "./PushToggle";
import { cn } from "@/lib/utils";
import { relativeTime } from "@/lib/format";
import {
  getLeaderboardAccess, getNotifications, markNotificationsRead, subscribeMarketAlerts,
} from "@/lib/realtime";
import type { MarketAlert } from "@/lib/realtime";

export default function NotificationBell() {
  const router = useRouter();
  const [access, setAccess] = useState<"unknown" | "enabled" | "locked">("unknown");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<MarketAlert[]>([]);
  const [unread, setUnread] = useState(0);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<MarketAlert | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    getLeaderboardAccess()
      .then((a) => { if (!cancelled) setAccess(a.enabled ? "enabled" : "locked"); })
      .catch(() => { /* backend unreachable: show nothing rather than a wrong lock */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (access !== "enabled") return;
    return subscribeMarketAlerts({
      onUnread: setUnread,
      onAlert: (a) => {
        setUnread((n) => n + 1);
        setItems((prev) => [a, ...prev.filter((p) => p.notification_id !== a.notification_id)]);
        setToast(a);
      },
    });
  }, [access]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 9000);
    return () => clearTimeout(id);
  }, [toast]);

  const load = useCallback(async (before?: string | null) => {
    setLoading(true);
    try {
      const feed = await getNotifications(before, 15);
      setItems((prev) => (before ? [...prev, ...feed.items] : feed.items));
      setUnread(feed.unread);
      setNextBefore(feed.next_before);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load alerts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (open) void load(); }, [open, load]);

  // Close on outside click and Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!rootRef.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const markAll = async () => {
    try {
      const r = await markNotificationsRead({ all: true });
      setUnread(r.unread);
      const now = new Date().toISOString();
      setItems((prev) => prev.map((i) => ({ ...i, read_at: i.read_at ?? now })));
    } catch { /* leave the badge as it was */ }
  };

  const openAlert = (a: MarketAlert) => {
    if (!a.read_at) {
      markNotificationsRead({ ids: [a.notification_id] }).then((r) => setUnread(r.unread)).catch(() => {});
      setItems((prev) => prev.map((i) => (i.notification_id === a.notification_id ? { ...i, read_at: new Date().toISOString() } : i)));
    }
    setOpen(false);
    setToast(null);
    router.push(`/analysis/${a.ticker}?horizon=${a.horizon}`);
  };

  if (access === "unknown") return null;

  if (access === "locked") {
    return (
      <Link
        href="/upgrade?feature=notifications&required_tier=elite"
        className="relative shrink-0 p-1 text-aureus-muted hover:text-aureus-gold transition-colors"
        title="Strong Buy alerts are part of the Elite plan"
        aria-label="Strong Buy alerts (Elite plan)"
      >
        <Bell className="w-4 h-4" strokeWidth={1.75} />
        <Lock className="w-2.5 h-2.5 absolute -bottom-0.5 -right-0.5 text-aureus-golddim" />
      </Link>
    );
  }

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className={cn("relative p-1 transition-colors", open ? "text-aureus-gold" : "text-aureus-muted hover:text-aureus-text")}
        aria-label={unread > 0 ? `Strong Buy alerts, ${unread} unread` : "Strong Buy alerts"}
        aria-expanded={open}
      >
        <Bell className="w-4 h-4" strokeWidth={1.75} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1.5 min-w-[15px] h-[15px] px-1 rounded-full bg-aureus-verdigris text-aureus-ink
                           font-mono-num text-[9px] font-semibold leading-[15px] text-center shadow-[0_0_10px_rgba(131,189,162,0.55)]">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2.5 w-[min(23rem,calc(100vw-2rem))] z-40 rounded-[10px] border border-aureus-rule
                        border-t-aureus-golddim bg-aureus-panel shadow-lift rise-in">
          <div className="flex items-center justify-between px-4 py-3 border-b border-aureus-rule">
            <div>
              <div className="text-[13px] text-aureus-text">Strong Buy alerts</div>
              <div className="text-[11px] text-aureus-muted">{unread > 0 ? `${unread} unread` : "All caught up"}</div>
            </div>
            {unread > 0 && (
              <button onClick={markAll} className="flex items-center gap-1 text-[11.5px] text-aureus-gold hover:text-aureus-goldbright">
                <Check className="w-3 h-3" /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[min(26rem,60vh)] overflow-y-auto">
            {error && <p className="px-4 py-4 text-[12px] text-aureus-oxblood">{error}</p>}
            {!error && items.length === 0 && !loading && (
              <div className="px-4 py-8 text-center">
                <p className="text-[13px] text-aureus-soft">No alerts yet</p>
                <p className="text-[12px] text-aureus-muted mt-1 leading-relaxed">
                  You will be alerted the moment a stock enters the Strong Buy board. Most days, none does.
                </p>
              </div>
            )}
            {items.map((a) => (
              <button
                key={a.notification_id}
                onClick={() => openAlert(a)}
                className="w-full text-left flex gap-3 px-4 py-3 border-b border-aureus-rulesoft hover:bg-aureus-panellift transition-colors"
              >
                <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", a.read_at ? "bg-transparent" : "bg-aureus-verdigris")} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="text-[13px] text-aureus-text">
                      <span className="font-mono-num">{a.ticker}</span>
                      <span className="text-aureus-muted"> · {a.horizon_label}</span>
                    </span>
                    <span className="text-[10.5px] text-aureus-muted shrink-0">{relativeTime(a.notified_at ?? a.created_at)}</span>
                  </span>
                  <span className="block text-[12px] text-aureus-soft leading-relaxed mt-0.5">{a.body}</span>
                  <span className="block mt-1 text-[11px] text-aureus-muted">
                    Composite <Figure className="text-[11px] text-aureus-verdigris">{a.composite.toFixed(1)}</Figure>
                  </span>
                </span>
              </button>
            ))}
            {nextBefore && (
              <button onClick={() => load(nextBefore)} disabled={loading}
                      className="w-full py-2.5 text-[12px] text-aureus-gold hover:text-aureus-goldbright">
                {loading ? "Loading…" : "Older alerts"}
              </button>
            )}
          </div>

          <div className="px-4 py-3 border-t border-aureus-rule space-y-3">
            <PushToggle compact />
            <Link href="/leaderboard" onClick={() => setOpen(false)} className="block text-[12px] text-aureus-gold hover:text-aureus-goldbright">
              Open the leaderboard →
            </Link>
          </div>
        </div>
      )}

      {toast && !open && (
        <div role="status" className="fixed right-4 top-[4.5rem] z-50 w-[min(22rem,calc(100vw-2rem))] rounded-[10px] border border-aureus-verdigris/40
                                      bg-aureus-panel shadow-lift px-4 py-3.5 rise-in">
          <div className="flex items-start gap-3">
            <span className="mt-1 w-2 h-2 rounded-full bg-aureus-verdigris shrink-0 pulse-gold" />
            <div className="min-w-0 flex-1">
              <div className="text-[13px] text-aureus-text">{toast.title}</div>
              <p className="text-[12px] text-aureus-soft leading-relaxed mt-0.5">{toast.body}</p>
              <button onClick={() => openAlert(toast)} className="text-[12px] text-aureus-gold hover:text-aureus-goldbright mt-1.5">
                View analysis →
              </button>
            </div>
            <button onClick={() => setToast(null)} className="text-aureus-muted hover:text-aureus-text" aria-label="Dismiss">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
