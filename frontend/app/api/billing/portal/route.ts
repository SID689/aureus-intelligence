// app/api/billing/portal/route.ts
// Fixes the second missing piece: Settings page called this to open the
// Stripe customer portal, but the route handler didn't exist.
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { createPortalSession } from "@/lib/stripe";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const stripeCustomerId = session.user.stripeCustomerId;
  if (!stripeCustomerId) {
    return NextResponse.json(
      { error: "No Stripe customer on file for this account." },
      { status: 400 }
    );
  }

  try {
    const origin = req.headers.get("origin") || process.env.NEXTAUTH_URL || "http://localhost:3000";
    const url = await createPortalSession(stripeCustomerId, `${origin}/settings`);
    return NextResponse.json({ url });
  } catch (err) {
    console.error("Portal session creation failed:", err);
    return NextResponse.json({ error: "Could not open billing portal" }, { status: 500 });
  }
}
