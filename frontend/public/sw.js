/*
 * Aureus service worker — Web Push for Strong Buy alerts, and nothing else.
 *
 * Deliberately no fetch handler and no caching. A service worker that
 * intercepts requests can serve a stale app long after a deploy, and
 * offline support is not something this product needs to buy that risk.
 */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_) {
    data = { title: "Aureus Intelligence", body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Aureus Intelligence", {
      body: data.body || "",
      tag: data.tag || "aureus",
      renotify: true,
      icon: "/favicon.ico",
      data: { url: data.url || "/leaderboard", notification_id: data.notification_id || null },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/leaderboard", self.location.origin);
  // Never navigate off-site on the strength of a payload.
  if (target.origin !== self.location.origin) return;

  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of windows) {
      if (new URL(client.url).origin === target.origin && "focus" in client) {
        await client.focus();
        if ("navigate" in client) {
          try { await client.navigate(target.href); } catch (_) { /* uncontrolled client */ }
        }
        return;
      }
    }
    await self.clients.openWindow(target.href);
  })());
});

// Browsers rotate subscriptions. Without this the server keeps pushing to a
// dead endpoint, deletes it on the 410, and the user silently stops
// receiving alerts they believe are switched on.
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil((async () => {
    try {
      const tokenRes = await fetch("/api/realtime/token", { credentials: "same-origin" });
      if (!tokenRes.ok) return;
      const { token } = await tokenRes.json();
      const { key } = await (await fetch("/api/v1/push/vapid-public-key")).json();
      if (!key) return;
      const sub = await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      });
      const json = sub.toJSON();
      await fetch("/api/v1/push/subscriptions", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys, user_agent: "resubscribed by service worker" }),
      });
    } catch (_) { /* the next visit's enablePush() re-registers */ }
  })());
});

function urlBase64ToUint8Array(b64) {
  const padded = (b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}
