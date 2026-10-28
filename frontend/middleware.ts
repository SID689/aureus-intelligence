// middleware.ts — auth enforcement + tier-based feature gating
import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import type { JWT } from "next-auth/jwt";

// Routes that require specific tiers
const TIER_GATES: Record<string, string[]> = {
  "/voice":   ["elite", "institutional"],
  // Fast path only. The page re-checks the plan against the database
  // server-side (app/(dashboard)/leaderboard/page.tsx), because the tier in
  // the JWT can lag a plan change.
  "/leaderboard": ["elite", "institutional"],
  "/settings/billing": ["plus", "elite", "institutional"],
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
    // Where a visitor with no session is sent. This is withAuth's own
    // setting, not authOptions' — they are deliberately different.
    // authOptions.pages.signIn stays /sign-in, because that is where
    // signIn() and auth errors belong: someone who asked to sign in
    // wants the form.
    //
    // Arriving at / is not that request. It is a stranger at the front
    // door, and the front door is /welcome: the method, the coverage,
    // the disclosure and the plans, with sign-up and sign-in on it.
    // Dropping that person straight onto a password field asks them to
    // authenticate to something they have not been told about yet.
    //
    // app/(dashboard)/layout.tsx already redirects to /welcome for the
    // same reason, but middleware resolves first, so that line never ran
    // and the landing page was unreachable for everyone who most needed
    // it. The two now agree, and the layout remains the backstop if
    // middleware is ever bypassed.
    pages: { signIn: "/welcome" },

    callbacks: {
      // Allow public pages; protect everything under (dashboard)
      authorized: ({ token, req }) => {
        // /api/v1/auth/* (signup, login, oauth-upsert) must stay public — it's
        // the endpoint an unauthenticated user calls to become authenticated.
        // Without this, signup redirects to /sign-in before ever reaching the
        // backend, since the browser-side signup call has no token yet.
        const publicPaths = ["/welcome", "/sign-in", "/sign-up", "/terms", "/privacy", "/api/auth", "/api/webhooks", "/api/v1/auth"];
        const isPublic    = publicPaths.some((p) => req.nextUrl.pathname.startsWith(p));
        return isPublic || !!token;
      },
    },
  }
);

export const config = {
  matcher: [
    // The trailing extension group is load-bearing, not tidiness. Without
    // it the auth middleware ran on static assets and 307'd them to
    // /sign-in — so the logo on the sign-in page itself failed to load,
    // because fetching it required being signed in. Listing files one by
    // one (as `favicon.ico` was) fixes only the asset you remember;
    // excluding by extension covers every asset added later.
    "/((?!_next/static|_next/image|favicon.ico|welcome|sign-in|sign-up|terms|privacy|sw\.js|api/auth|api/webhooks|.*\\.(?:png|jpg|jpeg|gif|svg|ico|webp|avif|woff|woff2|ttf)$).*)",
  ],
};
