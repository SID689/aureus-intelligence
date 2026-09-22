// lib/auth.ts  (Phase 6 — adds Google OAuth alongside credentials)
import type { NextAuthOptions, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

const API = process.env.NEXTAUTH_API_URL || "http://backend:8000";
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET || "";
const TIER_REFRESH_MS = 5 * 60 * 1000;

declare module "next-auth" {
  interface User {
    id: string;
    email: string;
    tier: string;
    stripeCustomerId?: string;
  }
  interface Session {
    user: User & { tier: string };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    tier: string;
    tierCheckedAt?: number;
    stripeCustomerId?: string;
  }
}

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },

  pages: {
    signIn: "/sign-in",
    error:  "/sign-in",
  },

  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email:    { label: "Email",    type: "email"    },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        try {
          const res = await fetch(`${API}/api/v1/auth/login`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ email: credentials.email, password: credentials.password }),
          });
          if (!res.ok) return null;
          const data = await res.json();
          return {
            id: data.user_id, email: data.email, name: data.display_name,
            tier: data.tier, stripeCustomerId: data.stripe_customer_id,
          } as User;
        } catch {
          return null;
        }
      },
    }),

    // Google OAuth — fixes "no way to sign up / log in with Google".
    // Requires GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env.local
    // (see setup instructions). If unset, this provider silently has
    // no effect and only the credentials form is shown.
    ...(process.env.GOOGLE_CLIENT_ID
      ? [GoogleProvider({
          clientId: process.env.GOOGLE_CLIENT_ID,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
        })]
      : []),
  ],

  callbacks: {
    // For Google sign-ins, upsert the user in our own database (via the
    // backend) BEFORE the JWT is issued, so we always have a real user_id,
    // tier, and Stripe customer for the session — not just Google's profile.
    async signIn({ user, account }) {
      if (account?.provider === "google") {
        try {
          const res = await fetch(`${API}/api/v1/auth/oauth-upsert`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Secret": INTERNAL_SECRET,
            },
            body: JSON.stringify({
              email: user.email,
              display_name: user.name || "",
              provider: "google",
              external_id: account.providerAccountId,
            }),
          });
          if (!res.ok) return false;
          const data = await res.json();
          // Stash backend fields onto the `user` object so the jwt()
          // callback below can read them.
          user.id = data.user_id;
          user.tier = data.tier;
          user.stripeCustomerId = data.stripe_customer_id;
        } catch (err) {
          console.error("OAuth upsert failed:", err);
          return false;
        }
      }
      return true;
    },

    async jwt({ token, user }) {
      if (user) {
        token.id               = user.id;
        token.tier              = user.tier;
        token.stripeCustomerId = user.stripeCustomerId;
        token.tierCheckedAt    = Date.now();
        return token;
      }
      // Without this the tier is frozen at sign-in: an upgrade never reaches
      // the sidebar or the middleware gates until the user signs out and
      // back in, and a downgrade keeps the old badges. Re-read it at most
      // every five minutes, whenever the session is read. Display and fast
      // paths only — the backend checks the plan itself on every request.
      if (token.id && Date.now() - (token.tierCheckedAt ?? 0) > TIER_REFRESH_MS) {
        token.tierCheckedAt = Date.now();
        try {
          const res = await fetch(`${API}/api/v1/account/entitlements?user_id=${encodeURIComponent(token.id)}`, {
            cache: "no-store",
          });
          if (res.ok) {
            const data = await res.json();
            if (typeof data.tier === "string") token.tier = data.tier;
          }
        } catch {
          // Keep the previous tier; the next read retries.
        }
      }
      return token;
    },

    async session({ session, token }) {
      if (session.user) {
        session.user.id               = token.id;
        session.user.tier              = token.tier;
        session.user.stripeCustomerId = token.stripeCustomerId;
      }
      return session;
    },
  },

  secret: process.env.NEXTAUTH_SECRET,
};
