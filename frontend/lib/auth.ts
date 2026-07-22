// lib/auth.ts
import type { NextAuthOptions, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";

const API = process.env.NEXTAUTH_API_URL || "http://backend:8000";

// Extend NextAuth types to include our custom fields
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
          // Call our FastAPI backend to validate credentials
          const res = await fetch(`${API}/api/v1/auth/login`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({
              email:    credentials.email,
              password: credentials.password,
            }),
          });

          if (!res.ok) return null;

          const data = await res.json();
          return {
            id:               data.user_id,
            email:            data.email,
            name:             data.display_name,
            tier:             data.tier,
            stripeCustomerId: data.stripe_customer_id,
          } as User;
        } catch {
          return null;
        }
      },
    }),
  ],

  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id               = user.id;
        token.tier             = user.tier;
        token.stripeCustomerId = user.stripeCustomerId;
      }
      return token;
    },

    async session({ session, token }) {
      if (session.user) {
        session.user.id               = token.id;
        session.user.tier             = token.tier;
        session.user.stripeCustomerId = token.stripeCustomerId;
      }
      return session;
    },
  },

  secret: process.env.NEXTAUTH_SECRET,
};
