// app/api/realtime/token/route.ts
//
// Exchanges the NextAuth session cookie for a five-minute realtime token.
// The browser never holds the signing secret, so it cannot mint a token for
// anyone but the user its session belongs to — which is the whole point:
// the premium endpoints stop trusting a user id the client merely asserts.
//
// The token carries identity only. The backend resolves the plan from the
// database on every use (see realtime_auth.py).
import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { mintRealtimeToken } from "@/lib/realtime-server";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await getServerSession(authOptions);
  const userId = session?.user?.id;
  if (!userId) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  try {
    const { token, expiresAt } = mintRealtimeToken(userId);
    return NextResponse.json(
      { token, expires_at: expiresAt },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (err) {
    console.error("Realtime token mint failed:", err);
    return NextResponse.json({ error: "Realtime access is not configured" }, { status: 503 });
  }
}
