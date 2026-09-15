// app/api/billing/checkout/route.ts
// Fixes a real gap from Phase 5: UpgradeModal.tsx called this endpoint
// but it was never implemented. Creates a Stripe Checkout session for
// the signed-in user and returns the redirect URL.
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { createCheckoutSession, TIER_TO_PRICE } from "@/lib/stripe";
import type { TierName } from "@/types";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const { tier } = (await req.json()) as { tier: TierName };
  const priceId = TIER_TO_PRICE[tier];
  if (!priceId) {
    return NextResponse.json({ error: `No Stripe price configured for tier '${tier}'` }, { status: 400 });
  }

  const stripeCustomerId = session.user.stripeCustomerId;
  if (!stripeCustomerId) {
    return NextResponse.json(
      { error: "No Stripe customer on file for this account, contact support." },
      { status: 400 }
    );
  }

  try {
    const origin = req.headers.get("origin") || process.env.NEXTAUTH_URL || "http://localhost:3000";
    const url = await createCheckoutSession(stripeCustomerId, priceId, `${origin}/settings`);
    return NextResponse.json({ url });
  } catch (err) {
    console.error("Checkout session creation failed:", err);
    return NextResponse.json({ error: "Could not start checkout" }, { status: 500 });
  }
}
