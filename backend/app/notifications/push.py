"""
app/notifications/push.py
---------------------------
Web Push: RFC 8030 delivery, RFC 8291 payload encryption, RFC 8292 VAPID,
via pywebpush.

SERVER-SIDE REQUEST FORGERY
A push subscription's endpoint is a URL the BROWSER hands us, which the
worker later POSTs to. Accepted as given, that is an SSRF primitive: a
user could register http://backend:8000/api/v1/... or a cloud metadata
address and have the worker call it with our VAPID signature attached.
Endpoints are therefore restricted to HTTPS on the push services the major
browsers actually use, checked when subscribing and again before sending.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from sqlalchemy import text

from app.core.config import get_settings
from app.scanner.db import engine

logger = logging.getLogger("aureus.notifications.push")

# Chrome/Opera/Samsung → FCM, Firefox → Mozilla autopush, Edge → WNS, Safari → Apple.
ALLOWED_HOST_SUFFIXES = ("fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com", "push.apple.com")
MAX_SUBSCRIPTIONS_PER_USER = 10
MAX_CONSECUTIVE_FAILURES = 5
_SEND_WORKERS = 8
_TTL_SECONDS = 12 * 3600      # an alert more than half a day old is history, not news


def endpoint_allowed(endpoint: str) -> bool:
    try:
        u = urlsplit(endpoint)
        port = u.port
    except ValueError:
        return False
    if u.scheme != "https" or u.username or u.password or port not in (None, 443):
        return False
    host = (u.hostname or "").lower().rstrip(".")
    return any(host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES)


def configured() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def subscribe(user_id: str, endpoint: str, p256dh: str, auth: str, user_agent: str | None) -> None:
    with engine().begin() as conn:
        # ON CONFLICT rebinds the endpoint: one browser signed into a second
        # account must stop receiving the first account's alerts.
        conn.execute(text("""
            INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)
            VALUES (CAST(:u AS uuid), :e, :p, :a, :ua)
            ON CONFLICT (endpoint) DO UPDATE SET user_id = EXCLUDED.user_id, p256dh = EXCLUDED.p256dh,
                   auth = EXCLUDED.auth, user_agent = EXCLUDED.user_agent, failure_count = 0
        """), {"u": user_id, "e": endpoint, "p": p256dh, "a": auth, "ua": user_agent})
        conn.execute(text("""
            DELETE FROM push_subscriptions WHERE user_id = CAST(:u AS uuid) AND id NOT IN (
                SELECT id FROM push_subscriptions WHERE user_id = CAST(:u AS uuid)
                 ORDER BY created_at DESC LIMIT :max)
        """), {"u": user_id, "max": MAX_SUBSCRIPTIONS_PER_USER})


def unsubscribe(user_id: str, endpoint: str) -> int:
    with engine().begin() as conn:
        return conn.execute(text("DELETE FROM push_subscriptions WHERE user_id = CAST(:u AS uuid) AND endpoint = :e"),
                            {"u": user_id, "e": endpoint}).rowcount


def subscription_count(user_id: str) -> int:
    with engine().connect() as conn:
        return conn.execute(text("SELECT count(*) FROM push_subscriptions WHERE user_id = CAST(:u AS uuid)"),
                            {"u": user_id}).scalar_one()


def _send(sub: dict, payload: dict) -> str:
    """'ok', 'gone' (subscription is dead and should be deleted) or 'failed' (try again later)."""
    from pywebpush import WebPushException, webpush

    if not endpoint_allowed(sub["endpoint"]):
        return "gone"
    s = get_settings()
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=json.dumps(payload),
            vapid_private_key=s.vapid_private_key,
            vapid_claims={"sub": s.vapid_claim_sub},   # a fresh dict: pywebpush writes aud/exp into it
            ttl=_TTL_SECONDS,
            timeout=10,
            headers={"Urgency": "high"},
        )
        return "ok"
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return "gone"
        logger.info("Push delivery failed", extra={"status": status, "error": str(exc)[:200]})
        return "failed"
    except Exception as exc:  # noqa: BLE001
        logger.info("Push delivery error", extra={"error": str(exc)[:200]})
        return "failed"


def payload_for(alert: dict, notification_id: str | None) -> dict:
    """Small on purpose: push services cap payloads at ~4KB after encryption."""
    return {
        "title": alert["title"],
        "body": alert["body"],
        "url": f"/leaderboard?horizon={alert['horizon']}",
        "tag": f"strong-buy:{alert['ticker']}",
        "ticker": alert["ticker"],
        "notification_id": notification_id,
    }


def deliver(targets: list[tuple[str, str]], alert: dict) -> int:
    """
    Push one alert to (notification_id, user_id) pairs. Returns how many
    notifications reached at least one of their user's devices, and marks
    those delivered.
    """
    if not targets or not configured():
        return 0
    users = sorted({u for _, u in targets})
    with engine().connect() as conn:
        subs = conn.execute(text("""
            SELECT id, user_id, endpoint, p256dh, auth FROM push_subscriptions
             WHERE user_id = ANY(CAST(:u AS uuid[]))
        """), {"u": users}).mappings().all()
    by_user: dict[str, list[dict]] = {}
    for s in subs:
        by_user.setdefault(str(s["user_id"]), []).append({**s, "id": str(s["id"])})

    jobs = [(nid, sub) for nid, uid in targets for sub in by_user.get(uid, [])]
    if not jobs:
        return 0
    with ThreadPoolExecutor(max_workers=_SEND_WORKERS) as pool:
        results = list(pool.map(lambda j: _send(j[1], payload_for(alert, j[0])), jobs))

    ok, failed, gone, delivered = set(), set(), set(), set()
    for (nid, sub), r in zip(jobs, results):
        {"ok": ok, "failed": failed, "gone": gone}[r].add(sub["id"])
        if r == "ok":
            delivered.add(nid)

    with engine().begin() as conn:
        if ok:
            conn.execute(text("UPDATE push_subscriptions SET last_success_at = now(), failure_count = 0 "
                              "WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": sorted(ok)})
        if failed:
            conn.execute(text("UPDATE push_subscriptions SET failure_count = failure_count + 1 "
                              "WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": sorted(failed)})
        if gone or failed:
            conn.execute(text("""
                DELETE FROM push_subscriptions
                 WHERE id = ANY(CAST(:gone AS uuid[]))
                    OR (id = ANY(CAST(:failed AS uuid[])) AND failure_count >= :max)
            """), {"gone": sorted(gone), "failed": sorted(failed), "max": MAX_CONSECUTIVE_FAILURES})
        if delivered:
            conn.execute(text("UPDATE user_notifications SET delivered_push_at = now() "
                              "WHERE id = ANY(CAST(:ids AS uuid[])) AND delivered_push_at IS NULL"),
                         {"ids": sorted(delivered)})
    logger.info("Push fan-out", extra={"targets": len(targets), "devices": len(jobs), "ok": len(ok),
                                       "failed": len(failed), "gone": len(gone)})
    return len(delivered)


def send_test(user_id: str) -> dict:
    """A test notification to the caller's own devices. Touches no notification rows."""
    if not configured():
        return {"configured": False, "devices": 0, "delivered": 0}
    with engine().connect() as conn:
        subs = [{**s, "id": str(s["id"])} for s in conn.execute(text(
            "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = CAST(:u AS uuid)"),
            {"u": user_id}).mappings()]
    payload = {"title": "Aureus alerts are on",
               "body": "This device will be notified when a stock enters the Strong Buy board.",
               "url": "/leaderboard", "tag": "aureus-test", "notification_id": None}
    results = [_send(s, payload) for s in subs]
    gone = [s["id"] for s, r in zip(subs, results) if r == "gone"]
    if gone:
        with engine().begin() as conn:
            conn.execute(text("DELETE FROM push_subscriptions WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": gone})
    return {"configured": True, "devices": len(subs), "delivered": results.count("ok"), "removed": len(gone)}
