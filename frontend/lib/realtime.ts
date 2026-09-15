"use client";
// lib/realtime.ts — client side of the premium real-time surfaces.
//
// Everything here authenticates with a short-lived signed token from
// /api/realtime/token instead of a user id in the URL. See
// backend/app/core/realtime_auth.py for why that distinction is the gate.

export type Horizon = "short_term" | "medium_term" | "long_term";
export type Pillar = "fundamental" | "technical" | "sentiment";

export interface BoardCatalyst {
  title: string;
  type: string;
  type_label: string;
  group: "earnings" | "deals" | "regulatory" | "corporate" | "macro";
  date: string;
  time: string | null;
  impact: "high" | "medium" | "low";
  direction: "positive" | "negative" | "neutral" | "unknown";
  relation: "upcoming" | "recent";
  source_url: string | null;
  days_until?: number;
}

export interface PillarScores { fundamental: number | null; technical: number | null; sentiment: number | null }

export interface LeaderboardMember {
  ticker: string;
  company_name: string | null;
  sector: string | null;
  price: number | null;
  composite: number;
  conviction: number | null;
  agreement: number | null;
  data_completeness: number | null;
  driver_pillar: Pillar | null;
  pillars: PillarScores;
  primary_catalyst: BoardCatalyst | null;
  entered_at: string;
  last_verified_at: string;
  peak_composite: number | null;
}

export interface LeaderboardCandidate {
  ticker: string;
  company_name: string | null;
  sector: string | null;
  price: number | null;
  composite: number;
  conviction: number | null;
  agreement: number | null;
  data_completeness: number | null;
  pillars: PillarScores;
  verified_at: string;
  primary_catalyst: BoardCatalyst | null;
  blocked_by: string;
}

export interface LeaderboardRules {
  entry: { composite: number; agreement: number; data_completeness: number };
  exit: { composite: number; agreement: number; data_completeness: number; stale_hours: number };
  alert_cooldown_hours: number;
  candidate_floor: number;
}

export interface LeaderboardBoard {
  horizon: Horizon;
  horizon_label: string;
  generated_at: string;
  last_scan: {
    id: string; status: string; market_phase: string | null;
    started_at: string; finished_at: string | null; verified: number; entries: number; exits: number;
  } | null;
  members: LeaderboardMember[];
  candidates: LeaderboardCandidate[];
  coverage: { scored: number; verified_24h: number; fundamentals_fresh: number; sentiment_fresh: number; universe: number };
  rules: LeaderboardRules;
}

export interface LeaderboardEvent {
  id: string;
  horizon: Horizon;
  ticker: string;
  event: "entered" | "exited";
  composite: number | null;
  conviction: number | null;
  reason: string | null;
  created_at: string;
  company_name: string | null;
}

export interface MarketAlert {
  alert_id: string;
  notification_id: string;
  kind: "strong_buy_entry";
  horizon: Horizon;
  horizon_label: string;
  ticker: string;
  company_name: string | null;
  composite: number;
  conviction: number | null;
  price: number | null;
  driver_pillar: Pillar | null;
  primary_catalyst: BoardCatalyst | null;
  title: string;
  body: string;
  created_at: string;
  notified_at?: string;
  read_at?: string | null;
}

export interface NotificationFeed { items: MarketAlert[]; unread: number; next_before: string | null }

export interface ScannerRun {
  id: string; status: "running" | "completed" | "skipped" | "failed"; market_phase: string | null;
  started_at: string; finished_at: string | null; universe_size: number | null;
  budget_units: number | null; units_spent: number;
  refreshed_fundamental: number; refreshed_technical: number; refreshed_sentiment: number;
  estimated: number; verified: number; entries: number; exits: number; errors: number; note: string | null;
}

export interface ScannerStatus {
  market_phase: string;
  cadence_minutes: number;
  runs: ScannerRun[];
  universe: { active: number; updated_at: string | null; source: string | null };
  budget: { finnhub_per_minute: number; stocktwits_per_hour: number; per_run: Record<string, Record<string, number>> };
  rules: LeaderboardRules;
}

/** The plan does not include the feature. Carries the backend's own message. */
export class PlanRequiredError extends Error {
  requiredTier: string;
  constructor(message: string, requiredTier = "elite") {
    super(message);
    this.name = "PlanRequiredError";
    this.requiredTier = requiredTier;
  }
}

// ── Token ───────────────────────────────────────────────────────────────

let tokenState: { token: string; expiresAt: number } | null = null;
let tokenInflight: Promise<string> | null = null;

export async function getRealtimeToken(force = false): Promise<string> {
  const now = Date.now() / 1000;
  if (!force && tokenState && tokenState.expiresAt - now > 60) return tokenState.token;
  // One request for however many components ask at once.
  if (tokenInflight) return tokenInflight;
  tokenInflight = (async () => {
    const res = await fetch("/api/realtime/token", { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) {
      throw new Error(res.status === 401 ? "Your session has expired. Sign in again." : "Real-time access is unavailable");
    }
    const data = (await res.json()) as { token: string; expires_at: number };
    tokenState = { token: data.token, expiresAt: data.expires_at };
    return data.token;
  })();
  try {
    return await tokenInflight;
  } finally {
    tokenInflight = null;
  }
}

async function realtimeFetch<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const token = await getRealtimeToken();
  const res = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (res.status === 401 && !retried) {
    tokenState = null;
    return realtimeFetch<T>(path, init, true);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    if (res.status === 402) {
      throw new PlanRequiredError(detail?.message || "This requires the Elite plan or above", detail?.required_tier);
    }
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

// ── REST ────────────────────────────────────────────────────────────────

let accessCache: { at: number; value: Promise<{ enabled: boolean; tier: string; plan: string }> } | null = null;

/** Whether the caller's plan includes the leaderboard. Shared and cached for a minute. */
export function getLeaderboardAccess(force = false) {
  if (!force && accessCache && Date.now() - accessCache.at < 60_000) return accessCache.value;
  const value = realtimeFetch<{ enabled: boolean; tier: string; plan: string }>("/api/v1/leaderboard/access");
  accessCache = { at: Date.now(), value };
  value.catch(() => { accessCache = null; });
  return value;
}

export const getLeaderboard = (horizon: Horizon) =>
  realtimeFetch<LeaderboardBoard>(`/api/v1/leaderboard?horizon=${horizon}`);

export const getLeaderboardEvents = (horizon?: Horizon, limit = 40) =>
  realtimeFetch<{ events: LeaderboardEvent[] }>(
    `/api/v1/leaderboard/events?limit=${limit}${horizon ? `&horizon=${horizon}` : ""}`,
  );

export const getScannerStatus = () => realtimeFetch<ScannerStatus>("/api/v1/scanner/status");

export const getNotifications = (before?: string | null, limit = 20) =>
  realtimeFetch<NotificationFeed>(
    `/api/v1/notifications?limit=${limit}${before ? `&before=${encodeURIComponent(before)}` : ""}`,
  );

export const markNotificationsRead = (opts: { ids?: string[]; all?: boolean }) =>
  realtimeFetch<{ updated: number; unread: number }>("/api/v1/notifications/read", {
    method: "POST",
    body: JSON.stringify({ ids: opts.ids ?? null, all: !!opts.all }),
  });

export const sendTestPush = () =>
  realtimeFetch<{ configured: boolean; devices: number; delivered: number }>("/api/v1/push/test", { method: "POST" });

// ── Live socket ─────────────────────────────────────────────────────────
// One socket per tab, shared by every component that listens (the bell and
// the leaderboard both do). Opened by the first subscriber, closed shortly
// after the last one leaves.

export type SocketStatus = "idle" | "connecting" | "live" | "reconnecting" | "denied";

export interface MarketAlertListener {
  onAlert?: (alert: MarketAlert) => void;
  onStatus?: (status: SocketStatus) => void;
  onUnread?: (unread: number) => void;
}

const listeners = new Set<MarketAlertListener>();
const seenAlerts = new Set<string>();
let socket: WebSocket | null = null;
let socketStatus: SocketStatus = "idle";
let attempt = 0;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let closeTimer: ReturnType<typeof setTimeout> | null = null;
let deniedAt = 0;

function wsBase(): string {
  const env = process.env.NEXT_PUBLIC_WS_URL;
  if (env) return env.replace(/\/$/, "");
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
}

function setStatus(s: SocketStatus) {
  socketStatus = s;
  listeners.forEach((l) => l.onStatus?.(s));
}

/** A tab that is open but not visible still deserves a visible alert. */
async function surfaceIfHidden(alert: MarketAlert) {
  if (typeof document === "undefined" || document.visibilityState !== "hidden") return;
  if (!("Notification" in window) || Notification.permission !== "granted" || !("serviceWorker" in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    await reg?.showNotification(alert.title, {
      body: alert.body,
      tag: `strong-buy:${alert.ticker}`,
      icon: "/favicon.ico",
      data: { url: `/leaderboard?horizon=${alert.horizon}`, notification_id: alert.notification_id },
    });
  } catch { /* the bell still has it */ }
}

function scheduleReconnect() {
  if (retryTimer || listeners.size === 0) return;
  attempt += 1;
  const delay = Math.min(30_000, 1000 * 2 ** Math.min(attempt, 5)) * (0.75 + Math.random() * 0.5);
  setStatus("reconnecting");
  retryTimer = setTimeout(() => { retryTimer = null; void openSocket(); }, delay);
}

async function openSocket() {
  if (socket || listeners.size === 0) return;
  // A plan without the feature will not gain it by retrying every few seconds.
  if (socketStatus === "denied" && Date.now() - deniedAt < 5 * 60_000) return;
  setStatus(attempt === 0 ? "connecting" : "reconnecting");

  let token: string;
  try {
    token = await getRealtimeToken(attempt > 0);
  } catch {
    scheduleReconnect();
    return;
  }
  if (listeners.size === 0 || socket) return;

  const ws = new WebSocket(`${wsBase()}/api/v1/ws/market?token=${encodeURIComponent(token)}`);
  socket = ws;

  ws.onmessage = (ev) => {
    let msg: { type?: string; unread?: number } & Partial<MarketAlert>;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === "connected") {
      attempt = 0;
      setStatus("live");
      listeners.forEach((l) => l.onUnread?.(msg.unread ?? 0));
    } else if (msg.type === "market_alert") {
      const alert = msg as MarketAlert;
      const key = alert.notification_id || alert.alert_id;
      if (seenAlerts.has(key)) return;      // fan-out retries can repeat a publish
      seenAlerts.add(key);
      listeners.forEach((l) => l.onAlert?.(alert));
      void surfaceIfHidden(alert);
    }
  };

  ws.onclose = (ev) => {
    if (socket === ws) socket = null;
    if (listeners.size === 0) { setStatus("idle"); return; }
    if (ev.code === 4403) { deniedAt = Date.now(); setStatus("denied"); return; }
    if (ev.code === 4401) tokenState = null;
    scheduleReconnect();
  };
}

export function subscribeMarketAlerts(listener: MarketAlertListener): () => void {
  listeners.add(listener);
  if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
  listener.onStatus?.(socketStatus);
  if (!socket && !retryTimer) void openSocket();

  return () => {
    listeners.delete(listener);
    if (listeners.size > 0) return;
    // Deferred, so a remount (React strict mode, a route change between two
    // pages that both listen) reuses the socket instead of tearing it down.
    closeTimer = setTimeout(() => {
      closeTimer = null;
      if (listeners.size > 0) return;
      if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
      socket?.close(1000);
      socket = null;
      attempt = 0;
      socketStatus = "idle";
    }, 1500);
  };
}

// ── Web Push ────────────────────────────────────────────────────────────

export type PushState = "unsupported" | "blocked" | "on" | "off";

export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function urlBase64ToBytes(b64: string): BufferSource {
  const padded = (b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function bytesToUrlBase64(buf: ArrayBuffer): string {
  let s = "";
  new Uint8Array(buf).forEach((b) => { s += String.fromCharCode(b); });
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function getPushState(): Promise<PushState> {
  if (!pushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = await reg?.pushManager.getSubscription();
  return sub && Notification.permission === "granted" ? "on" : "off";
}

export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error("This browser does not support push notifications");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(permission === "denied"
      ? "Notifications are blocked for this site. Allow them in your browser's site settings."
      : "Notification permission was not granted");
  }
  const { key, configured } = (await (await fetch("/api/v1/push/vapid-public-key")).json()) as
    { key: string | null; configured: boolean };
  if (!configured || !key) throw new Error("Push notifications are not configured on this server");

  const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  // A subscription made under a previous server key can never be delivered to.
  const existingKey = sub?.options.applicationServerKey;
  if (sub && existingKey && bytesToUrlBase64(existingKey) !== key) {
    await sub.unsubscribe();
    sub = null;
  }
  if (!sub) {
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToBytes(key) });
  }
  const json = sub.toJSON();
  await realtimeFetch("/api/v1/push/subscriptions", {
    method: "POST",
    body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys, user_agent: navigator.userAgent.slice(0, 300) }),
  });
}

export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = await reg?.pushManager.getSubscription();
  if (!sub) return;
  try {
    await realtimeFetch("/api/v1/push/subscriptions", { method: "DELETE", body: JSON.stringify({ endpoint: sub.endpoint }) });
  } finally {
    await sub.unsubscribe();
  }
}
