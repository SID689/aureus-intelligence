// app/api/webhooks/stripe/route.ts
//
// Stripe → Aureus webhook receiver.
//
// ─────────────────────────────────────────────────────────────────────
// THE BUG THIS REWRITE FIXES
// ─────────────────────────────────────────────────────────────────────
// The previous version caught every downstream error and returned 200,
// with the comment "Return 200 so Stripe doesn't retry — we log the
// error separately". That is exactly backwards. A 200 tells Stripe the
// event was handled, so it is never redelivered. If the backend was
// briefly down while a `checkout.session.completed` arrived, the
// customer's payment succeeded and their tier was never upgraded — and
// the only trace was a log line nobody reads.
//
// Stripe's retry schedule (roughly 3 days of exponential backoff) exists
// precisely for transient downstream failures. This version returns 500
// on failure so Stripe retries, and 200 only when the work is done.
//
// ─────────────────────────────────────────────────────────────────────
// IDEMPOTENCY
// ─────────────────────────────────────────────────────────────────────
// Retries mean at-least-once delivery, so the same event WILL arrive
// twice. Without dedup, a redelivered checkout.session.completed grants
// a second month of credits for one payment. Every event id is recorded
// in stripe_events before processing; a duplicate short-circuits.
//
// ─────────────────────────────────────────────────────────────────────
// SUBSCRIPTION LIFECYCLE COVERED
// ─────────────────────────────────────────────────────────────────────
//   checkout.session.completed      first purchase
//   customer.subscription.created   subscription made outside checkout
//                                   (dashboard, API, portal plan change)
//   customer.subscription.updated   upgrade / downgrade / status change
//   customer.subscription.deleted   cancellation → downgrade to free
//   invoice.payment_succeeded       RENEWAL — resets the credit period.
//                                   Missing this was why credits were
//                                   granted once and never refreshed.
//   invoice.payment_failed          mark past_due
import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { stripe, tierFromPriceId } from "@/lib/stripe";

const BACKEND = process.env.NEXTAUTH_API_URL || "http://backend:8000";
const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || "";

export async function POST(req: NextRequest) {
  if (!WEBHOOK_SECRET || WEBHOOK_SECRET.includes("...")) {
    // Fail loudly rather than accepting unverified events. An unset
    // secret used to mean every webhook 400'd with a confusing signature
    // error; this says what is actually wrong.
    console.error("STRIPE_WEBHOOK_SECRET is not configured — refusing webhook");
    return NextResponse.json({ error: "Webhook secret not configured" }, { status: 500 });
  }

  const body = await req.text();
  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "No signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, signature, WEBHOOK_SECRET);
  } catch (err) {
    // A bad signature is permanent, not transient — 400 so Stripe stops.
    console.error("Stripe webhook signature verification failed:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  // Dedup before doing any work.
  const already = await claimEvent(event.id, event.type);
  if (already === "duplicate") {
    return NextResponse.json({ received: true, deduplicated: true });
  }

  try {
    await handleEvent(event);
    await markEvent(event.id, "processed", null);
    return NextResponse.json({ received: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`Error handling Stripe event ${event.type} (${event.id}):`, message);
    await markEvent(event.id, "failed", message);
    // 500 so Stripe retries. This is the fix for silently losing upgrades.
    return NextResponse.json({ error: "Handler failed", event: event.id }, { status: 500 });
  }
}

async function handleEvent(event: Stripe.Event): Promise<void> {
  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      const customerId = session.customer as string;
      // Resolve the tier from the SUBSCRIPTION's price, not from
      // session.metadata. Metadata is set by our own checkout helper, so
      // a subscription created any other way carries none and would
      // silently resolve to the free tier.
      let priceId = session.metadata?.priceId ?? "";
      if (session.subscription) {
        const sub = await stripe.subscriptions.retrieve(session.subscription as string);
        priceId = sub.items.data[0]?.price.id ?? priceId;
      }
      await notifyBackend("/api/v1/billing/tier-update", {
        stripe_customer_id: customerId,
        new_tier: tierFromPriceId(priceId),
        subscription_status: "active",
        stripe_subscription_id: (session.subscription as string) ?? "",
      });
      break;
    }

    case "customer.subscription.created":
    case "customer.subscription.updated": {
      const sub = event.data.object as Stripe.Subscription;
      await notifyBackend("/api/v1/billing/tier-update", {
        stripe_customer_id: sub.customer as string,
        new_tier: tierFromPriceId(sub.items.data[0]?.price.id ?? ""),
        subscription_status: sub.status,
        stripe_subscription_id: sub.id,
      });
      break;
    }

    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      await notifyBackend("/api/v1/billing/tier-update", {
        stripe_customer_id: sub.customer as string,
        new_tier: "sovereign",
        subscription_status: "canceled",
        stripe_subscription_id: sub.id,
      });
      break;
    }

    case "invoice.payment_succeeded": {
      // The renewal path. Without it, credits were granted at purchase
      // and never reset, so month two silently had none.
      const invoice = event.data.object as Stripe.Invoice;
      const subId =
        typeof invoice.subscription === "string"
          ? invoice.subscription
          : invoice.subscription?.id;
      if (!subId) break;   // one-off invoice, not a subscription renewal
      const sub = await stripe.subscriptions.retrieve(subId);
      await notifyBackend("/api/v1/billing/tier-update", {
        stripe_customer_id: invoice.customer as string,
        new_tier: tierFromPriceId(sub.items.data[0]?.price.id ?? ""),
        subscription_status: sub.status,
        stripe_subscription_id: sub.id,
      });
      break;
    }

    case "invoice.payment_failed": {
      const invoice = event.data.object as Stripe.Invoice;
      await notifyBackend("/api/v1/billing/payment-failed", {
        stripe_customer_id: invoice.customer as string,
      });
      break;
    }

    default:
      // Unhandled types are a success, not a failure — returning 500
      // would make Stripe retry an event we will never act on.
      break;
  }
}

async function notifyBackend(path: string, payload: object): Promise<void> {
  const secret = process.env.INTERNAL_API_SECRET || "";
  if (!secret) {
    // Refuse rather than call unauthenticated: the backend treats an
    // empty configured secret as "no check required", so sending nothing
    // would work and leave the tier endpoint effectively open.
    throw new Error("INTERNAL_API_SECRET is not set — refusing to call the backend");
  }
  const res = await fetch(`${BACKEND}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Internal-Secret": secret },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Backend ${path} returned ${res.status}: ${await res.text()}`);
  }
  const data = (await res.json()) as { status?: string };
  // The backend returns 200 with {"status":"error"} on a handled failure,
  // which must still be treated as a failure so Stripe retries.
  if (data.status && !["updated", "recorded", "marked_past_due", "not_found"].includes(data.status)) {
    throw new Error(`Backend ${path} reported status='${data.status}'`);
  }
}

/** Records the event id. Returns "duplicate" if it was already seen. */
async function claimEvent(eventId: string, eventType: string): Promise<"new" | "duplicate"> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/billing/event-claim`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Secret": process.env.INTERNAL_API_SECRET || "",
      },
      body: JSON.stringify({ event_id: eventId, event_type: eventType }),
    });
    if (!res.ok) return "new";
    const data = (await res.json()) as { duplicate?: boolean };
    return data.duplicate ? "duplicate" : "new";
  } catch {
    // If dedup is unavailable, process anyway. Processing twice is
    // recoverable; dropping a payment event is not.
    return "new";
  }
}

async function markEvent(eventId: string, status: string, error: string | null): Promise<void> {
  try {
    await fetch(`${BACKEND}/api/v1/billing/event-status`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Secret": process.env.INTERNAL_API_SECRET || "",
      },
      body: JSON.stringify({ event_id: eventId, status, error }),
    });
  } catch {
    /* best-effort bookkeeping */
  }
}
