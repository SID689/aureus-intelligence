import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
