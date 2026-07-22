// app/api/webhooks/stripe/route.ts
import { NextRequest, NextResponse } from "next/server";
import { stripe, tierFromPriceId } from "@/lib/stripe";
import Stripe from "stripe";

const BACKEND = process.env.NEXTAUTH_API_URL || "http://backend:8000";
const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET!;

export async function POST(req: NextRequest) {
  const body      = await req.text();
  const signature = req.headers.get("stripe-signature");

  if (!signature) {
    return NextResponse.json({ error: "No signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, signature, WEBHOOK_SECRET);
  } catch (err) {
    console.error("Stripe webhook signature verification failed:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  try {
    switch (event.type) {
      case "customer.subscription.updated": {
        const sub    = event.data.object as Stripe.Subscription;
        const priceId = sub.items.data[0]?.price.id ?? "";
        const tier    = tierFromPriceId(priceId);
        const customerId = sub.customer as string;

        // Tell the backend to update the user's tier
        await notifyBackend("/api/v1/billing/tier-update", {
          stripe_customer_id: customerId,
          new_tier:           tier,
          subscription_status: sub.status,
          stripe_subscription_id: sub.id,
        });
        break;
      }

      case "customer.subscription.deleted": {
        const sub        = event.data.object as Stripe.Subscription;
        const customerId = sub.customer as string;

        // Downgrade to sovereign and pause all active agents
        await notifyBackend("/api/v1/billing/tier-update", {
          stripe_customer_id:     customerId,
          new_tier:               "sovereign",
          subscription_status:    "canceled",
          stripe_subscription_id: sub.id,
        });
        break;
      }

      case "invoice.payment_failed": {
        const invoice    = event.data.object as Stripe.Invoice;
        const customerId = invoice.customer as string;

        await notifyBackend("/api/v1/billing/payment-failed", {
          stripe_customer_id: customerId,
        });
        break;
      }

      case "checkout.session.completed": {
        const session    = event.data.object as Stripe.Checkout.Session;
        const customerId = session.customer as string;
        const priceId    = session.metadata?.priceId ?? "";
        const tier       = tierFromPriceId(priceId);

        await notifyBackend("/api/v1/billing/tier-update", {
          stripe_customer_id:     customerId,
          new_tier:               tier,
          subscription_status:    "active",
          stripe_subscription_id: session.subscription as string,
        });
        break;
      }
    }
  } catch (err) {
    console.error(`Error handling Stripe event ${event.type}:`, err);
    // Return 200 so Stripe doesn't retry — we log the error separately
  }

  return NextResponse.json({ received: true });
}

async function notifyBackend(path: string, payload: object): Promise<void> {
  const res = await fetch(`${BACKEND}${path}`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      // Internal service-to-service auth header
      "X-Internal-Secret": process.env.INTERNAL_API_SECRET || "",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend ${path} returned ${res.status}: ${text}`);
  }
}
