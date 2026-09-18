import type { NextConfig } from "next";

/**
 * Where FastAPI lives, from the Next server's point of view.
 *
 * This used to be the literal `http://backend:8000`, which is the compose
 * service name and resolves nowhere else. Any deployment that does not run
 * both halves in the same Docker network — Vercel in front of a backend on
 * Render, a tunnel, a staging host — proxied every /api/v1 call into a
 * hostname that does not exist, and the whole app returned 500s that looked
 * like backend failures. It is the same variable the auth and layout code
 * already use for server-side calls, so one setting moves all of them.
 */
const API_ORIGIN = process.env.NEXTAUTH_API_URL || "http://backend:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  // Emits a self-contained server bundle with only the node_modules the
  // app actually imports, so the production image ships ~150MB instead of
  // the ~1GB a full dev install occupies. Affects `next build` only — the
  // dev server is untouched.
  output: "standalone",
  async rewrites() {
    // Only proxy /api/v1/* to FastAPI.
    // /api/auth/* must stay in Next.js (NextAuth).
    // /api/webhooks/* must stay in Next.js (Stripe handler).
    return [
      {
        source:      "/api/v1/:path*",
        destination: `${API_ORIGIN}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
