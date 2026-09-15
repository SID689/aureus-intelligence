// app/(dashboard)/leaderboard/page.tsx
//
// Server-side gate. middleware.ts turns away most free users early, but it
// reads the tier baked into the session JWT, which lags a plan change. The
// authoritative check is here: the backend resolves the plan from the
// database, using a token this server mints for the session's own user.
import { Suspense } from "react";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";
import { mintRealtimeToken } from "@/lib/realtime-server";
import LeaderboardView from "@/components/leaderboard/LeaderboardView";
import { LoadingRegion, SkeletonPageHeader, SkeletonSheet, SkeletonTable } from "@/components/ui/Skeleton";

export const dynamic = "force-dynamic";

const API = process.env.NEXTAUTH_API_URL || "http://backend:8000";

async function checkAccess(userId: string): Promise<"allowed" | "denied" | "unavailable"> {
  try {
    const { token } = mintRealtimeToken(userId, 60);
    const res = await fetch(`${API}/api/v1/leaderboard/access`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return "unavailable";
    const data = (await res.json()) as { enabled: boolean };
    return data.enabled ? "allowed" : "denied";
  } catch {
    return "unavailable";
  }
}

export default async function LeaderboardPage() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) redirect("/welcome");

  const access = await checkAccess(session.user.id);
  // Outside any try/catch: redirect() works by throwing.
  if (access === "denied") redirect("/upgrade?feature=leaderboard&required_tier=elite");

  if (access === "unavailable") {
    // Fail closed, but do not send a paying customer to a paywall because
    // the backend blinked.
    return (
      <div className="max-w-md mx-auto py-20 text-center space-y-2">
        <p className="text-aureus-soft text-sm">The leaderboard could not confirm your plan just now.</p>
        <p className="text-aureus-muted text-[13px]">Reload in a moment. If it persists, the analysis service may be down.</p>
      </div>
    );
  }

  return (
    <Suspense fallback={
      <LoadingRegion label="Loading the board" className="space-y-6">
        <SkeletonPageHeader />
        <SkeletonSheet><SkeletonTable rows={7} columns={[1, 4, 2, 3, 4, 2]} /></SkeletonSheet>
      </LoadingRegion>
    }>
      <LeaderboardView />
    </Suspense>
  );
}
