// lib/stripe.ts
import Stripe from "stripe";
import type { TierName } from "@/types";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2024-06-20",
  typescript: true,
});

// Map Stripe price IDs → tier names. Set these in .env.local
export const PRICE_TO_TIER: Record<string, TierName> = {
  [process.env.STRIPE_PRICE_ELITE         || "price_elite"]:         "elite",
  [process.env.STRIPE_PRICE_INSTITUTIONAL || "price_institutional"]: "institutional",
};

export const TIER_TO_PRICE: Record<TierName, string | null> = {
  sovereign:     null,
  elite:         process.env.STRIPE_PRICE_ELITE         || "",
  institutional: process.env.STRIPE_PRICE_INSTITUTIONAL || "",
};

export function tierFromPriceId(priceId: string): TierName {
  return PRICE_TO_TIER[priceId] ?? "sovereign";
}

// Create a Stripe Checkout Session for a subscription upgrade
export async function createCheckoutSession(
  stripeCustomerId: string,
  priceId: string,
  returnUrl: string,
): Promise<string> {
  const session = await stripe.checkout.sessions.create({
    customer:    stripeCustomerId,
    mode:        "subscription",
    line_items:  [{ price: priceId, quantity: 1 }],
    success_url: `${returnUrl}?upgraded=true`,
    cancel_url:  returnUrl,
    metadata:    { priceId },
  });
  return session.url!;
}

// Create a customer portal session for managing subscriptions
export async function createPortalSession(
  stripeCustomerId: string,
  returnUrl: string,
): Promise<string> {
  const session = await stripe.billingPortal.sessions.create({
    customer:   stripeCustomerId,
    return_url: returnUrl,
  });
  return session.url;
}
