import type { NextConfig } from "next";

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
        destination: "http://backend:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
