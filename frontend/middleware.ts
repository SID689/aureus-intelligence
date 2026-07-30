// middleware.ts — auth enforcement + tier-based feature gating
import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import type { JWT } from "next-auth/jwt";

// Routes that require specific tiers
const TIER_GATES: Record<string, string[]> = {
  "/voice":   ["elite", "institutional"],
  "/orders":  ["elite", "institutional"],
  "/settings/billing": ["elite", "institutional"],
};

export default withAuth(
  function middleware(req: NextRequest & { nextauth: { token: JWT | null } }) {
    const token = req.nextauth.token;
    const tier  = (token?.tier as string) ?? "sovereign";
    const path  = req.nextUrl.pathname;

    // Check tier gates
    for (const [protectedPath, allowedTiers] of Object.entries(TIER_GATES)) {
      if (path.startsWith(protectedPath) && !allowedTiers.includes(tier)) {
        const upgradeUrl = new URL("/upgrade", req.url);
        upgradeUrl.searchParams.set("feature", protectedPath.replace("/", ""));
        upgradeUrl.searchParams.set("required_tier", allowedTiers[0]);
        return NextResponse.redirect(upgradeUrl);
      }
    }

    // Add tier to request headers so server components can read it
    const requestHeaders = new Headers(req.headers);
    requestHeaders.set("x-aureus-tier",    tier);
    requestHeaders.set("x-aureus-user-id", (token?.id as string) ?? "");

    return NextResponse.next({ request: { headers: requestHeaders } });
  },
  {
    callbacks: {
      // Allow public pages; protect everything under (dashboard)
      authorized: ({ token, req }) => {
        const publicPaths = ["/welcome", "/sign-in", "/sign-up", "/api/auth", "/api/webhooks"];
        const isPublic    = publicPaths.some((p) => req.nextUrl.pathname.startsWith(p));
        return isPublic || !!token;
      },
    },
  }
);

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|welcome|sign-in|sign-up|api/auth|api/webhooks).*)",
  ],
};
