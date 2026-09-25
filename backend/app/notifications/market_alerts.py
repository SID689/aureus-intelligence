"""
app/notifications/market_alerts.py
------------------------------------
Strong Buy alerts: who receives them, and how they arrive.

GATING
Recipients are chosen in SQL, from the subscription tables, at the moment
of fan-out: users with an active or trialing subscription on a plan whose
leaderboard_enabled flag is set. Not from a cache, not from the session,
not from anything a client sent. A notification row is only ever written
for an entitled user, and both delivery channels read from those rows, so
there is no path on which a free user is sent an alert and filtered later.

DELIVERY
    in the app      WebSocket. The socket keeps a presence key alive every
                    25 seconds while it is open.
    not in the app  Web Push to every registered device.
    socket died     A crashed tab leaves presence alive for up to 75s, so an
    ungracefully    alert can be published to nobody. A second pass 20
                    seconds later pushes every notification the socket did
                    not confirm delivering.

Whatever either channel misses stays in the notification history behind
the bell.
"""

import json
import logging
from datetime import date

from sqlalchemy import text

from app.core.redis_client import get_redis_client
from app.notifications import push
from app.scanner import HORIZON_LABELS
from app.scanner.db import engine

logger = logging.getLogger("aureus.notifications.market_alerts")

CHANNEL_PREFIX = "market_alerts:"
PRESENCE_KEY = "market_ws:presence:{}"
PRESENCE_TTL = 75
WS_GRACE_SECONDS = 20

_DRIVER_WORDS = {"fundamental": "fundamentals", "technical": "price action", "sentiment": "sentiment"}

_ENTITLED_RECIPIENTS = text("""
    INSERT INTO user_notifications (user_id, alert_id)
    SELECT DISTINCT u.id, CAST(:id AS uuid)
      FROM users u
      JOIN active_user_subscriptions us ON us.user_id = u.id
      JOIN subscription_tiers st ON st.id = us.tier_id
     WHERE st.leaderboard_enabled
       AND u.is_active
       AND u.deleted_at IS NULL
    ON CONFLICT (user_id, alert_id) DO NOTHING
""")


def _fmt_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def create_alert(conn, *, horizon: str, entry: dict, primary: dict | None) -> str:
    """Write the alert inside the leaderboard's own transaction, so an entry and its alert commit together."""
    t = entry["ticker"]
    body = (f"{entry.get('company_name') or t} entered the {HORIZON_LABELS[horizon].lower()} board "
            f"at a composite of {entry['composite']:.1f}")
    if entry.get("driver_pillar"):
        body += f", led by {_DRIVER_WORDS.get(entry['driver_pillar'], entry['driver_pillar'])}"
    body += "."
    if primary and primary.get("date"):
        body += (f" {'Next' if primary.get('relation') == 'upcoming' else 'Recent'}: "
                 f"{primary['title']}, {_fmt_day(primary['date'])}.")
    return str(conn.execute(text("""
        INSERT INTO market_alerts (kind, horizon, ticker, company_name, composite, conviction, price,
                                   driver_pillar, primary_catalyst, title, body)
        VALUES ('strong_buy_entry', :h, :t, :name, :c, :cv, :p, :d, CAST(:pc AS jsonb), :title, :body)
        RETURNING id
    """), {"h": horizon, "t": t, "name": entry.get("company_name"), "c": entry["composite"],
           "cv": entry.get("conviction"), "p": entry.get("price"), "d": entry.get("driver_pillar"),
           "pc": json.dumps(primary), "title": f"Strong Buy: {t}", "body": body}).scalar_one())


def alert_payload(a) -> dict:
    return {
        "alert_id": str(a["id"]), "kind": a["kind"], "horizon": a["horizon"],
        "horizon_label": HORIZON_LABELS.get(a["horizon"], a["horizon"]),
        "ticker": a["ticker"], "company_name": a["company_name"], "composite": a["composite"],
        "conviction": a["conviction"], "price": a["price"], "driver_pillar": a["driver_pillar"],
        "primary_catalyst": a["primary_catalyst"], "title": a["title"], "body": a["body"],
        "created_at": a["created_at"].isoformat(),
    }


def _pending(conn, alert_id: str, older_than_seconds: int = 0) -> list[tuple[str, str]]:
    rows = conn.execute(text("""
        SELECT id, user_id FROM user_notifications
         WHERE alert_id = CAST(:id AS uuid) AND delivered_ws_at IS NULL AND delivered_push_at IS NULL
           AND created_at <= now() - make_interval(secs => :age)
    """), {"id": alert_id, "age": older_than_seconds}).all()
    return [(str(n), str(u)) for n, u in rows]


def fan_out(alert_id: str) -> dict:
    """Select recipients, then deliver live or by push. Idempotent: safe to retry."""
    with engine().begin() as conn:
        alert = conn.execute(text("SELECT * FROM market_alerts WHERE id = CAST(:id AS uuid)"),
                             {"id": alert_id}).mappings().first()
        if alert is None:
            return {"status": "missing"}
        conn.execute(_ENTITLED_RECIPIENTS, {"id": alert_id})
        recipients = conn.execute(text("""
            UPDATE market_alerts SET recipients = (SELECT count(*) FROM user_notifications WHERE alert_id = CAST(:id AS uuid))
             WHERE id = CAST(:id AS uuid) RETURNING recipients
        """), {"id": alert_id}).scalar_one()
        pending = _pending(conn, alert_id)

    payload = alert_payload(alert)
    redis = get_redis_client()
    live, offline = 0, []
    for nid, uid in pending:
        if redis.exists(PRESENCE_KEY.format(uid)):
            redis.publish(CHANNEL_PREFIX + uid, json.dumps({**payload, "notification_id": nid}))
            live += 1
        else:
            offline.append((nid, uid))
    pushed = push.deliver(offline, payload)
    result = {"status": "ok", "ticker": alert["ticker"], "recipients": recipients,
              "published_live": live, "push_targets": len(offline), "push_delivered": pushed}
    logger.info("Market alert fanned out", extra=result)
    return result


def push_undelivered(alert_id: str) -> dict:
    """The second pass: push anything the socket did not confirm within the grace period."""
    with engine().connect() as conn:
        alert = conn.execute(text("SELECT * FROM market_alerts WHERE id = CAST(:id AS uuid)"),
                             {"id": alert_id}).mappings().first()
        if alert is None:
            return {"status": "missing"}
        pending = _pending(conn, alert_id, older_than_seconds=WS_GRACE_SECONDS - 5)
    delivered = push.deliver(pending, alert_payload(alert))
    return {"status": "ok", "unconfirmed": len(pending), "push_delivered": delivered}


# ── Presence and socket bookkeeping ───────────────────────────────────────

def touch_presence(user_id: str) -> None:
    get_redis_client().setex(PRESENCE_KEY.format(user_id), PRESENCE_TTL, "1")


def clear_presence(user_id: str) -> None:
    get_redis_client().delete(PRESENCE_KEY.format(user_id))


def mark_ws_delivered(notification_id: str, user_id: str) -> None:
    with engine().begin() as conn:
        conn.execute(text("""
            UPDATE user_notifications SET delivered_ws_at = now()
             WHERE id = CAST(:n AS uuid) AND user_id = CAST(:u AS uuid) AND delivered_ws_at IS NULL
        """), {"n": notification_id, "u": user_id})


# ── History ───────────────────────────────────────────────────────────────

def unread_count(user_id: str) -> int:
    with engine().connect() as conn:
        return conn.execute(text("SELECT count(*) FROM user_notifications WHERE user_id = CAST(:u AS uuid) "
                                 "AND read_at IS NULL"), {"u": user_id}).scalar_one()


def feed(user_id: str, limit: int = 30, before: str | None = None) -> dict:
    with engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT un.id AS notification_id, un.created_at AS notified_at, un.read_at, ma.*
              FROM user_notifications un JOIN market_alerts ma ON ma.id = un.alert_id
             WHERE un.user_id = CAST(:u AS uuid)
               AND (CAST(:before AS timestamptz) IS NULL OR un.created_at < CAST(:before AS timestamptz))
             ORDER BY un.created_at DESC LIMIT :limit
        """), {"u": user_id, "before": before, "limit": limit}).mappings().all()
    items = [{
        **alert_payload(r),
        "notification_id": str(r["notification_id"]),
        "notified_at": r["notified_at"].isoformat(),
        "read_at": r["read_at"].isoformat() if r["read_at"] else None,
    } for r in rows]
    return {"items": items, "unread": unread_count(user_id),
            "next_before": items[-1]["notified_at"] if len(items) == limit else None}


def mark_read(user_id: str, ids: list[str] | None, all_: bool) -> int:
    if not all_ and not ids:
        return 0
    with engine().begin() as conn:
        return conn.execute(text("""
            UPDATE user_notifications SET read_at = now()
             WHERE user_id = CAST(:u AS uuid) AND read_at IS NULL
               AND (:all OR id = ANY(CAST(:ids AS uuid[])))
        """), {"u": user_id, "all": all_, "ids": ids or []}).rowcount
