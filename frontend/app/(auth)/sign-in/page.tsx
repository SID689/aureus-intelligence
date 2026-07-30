"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function SignInPage() {
  const router = useRouter();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await signIn("credentials", { email, password, redirect: false });
    setLoading(false);
    if (result?.error) {
      setError("Invalid email or password.");
    } else {
      router.push("/");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <div className="font-display text-aureus-gold text-3xl tracking-wide mb-1" style={{ fontWeight: 600 }}>Aureus</div>
          <p className="text-aureus-muted text-sm">Intelligence Platform</p>
        </div>

        <div className="rounded-xl border border-aureus-border p-6 space-y-4" style={{ background: "var(--surface)" }}>
          <button
            onClick={() => signIn("google", { callbackUrl: "/" })}
            className="w-full py-2 rounded-lg border border-aureus-border text-white text-sm
                       hover:border-aureus-gold transition-colors flex items-center justify-center gap-2"
          >
            <svg width="16" height="16" viewBox="0 0 48 48">
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.6-6 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/>
              <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6 29.5 4 24 4 16.3 4 9.6 8.3 6.3 14.7z"/>
              <path fill="#4CAF50" d="M24 44c5.4 0 10.3-1.8 14.1-5l-6.5-5.5C29.5 35.4 26.9 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.6 5.1C9.5 39.6 16.2 44 24 44z"/>
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.2-4.1 5.6l6.5 5.5C41.6 35.9 44 30.4 44 24c0-1.3-.1-2.7-.4-3.5z"/>
            </svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-2 text-xs text-aureus-muted">
            <div className="flex-1 h-px bg-aureus-border" />
            or
            <div className="flex-1 h-px bg-aureus-border" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <h2 className="sr-only">Sign in</h2>
            {error && (
              <div className="rounded p-2 bg-red-950/40 border border-aureus-red text-aureus-red text-sm">{error}</div>
            )}
            <div className="space-y-1">
              <label className="text-xs text-aureus-muted">Email</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                     className="w-full bg-transparent border border-aureus-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-aureus-gold"
                     placeholder="you@example.com" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-aureus-muted">Password</label>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                     className="w-full bg-transparent border border-aureus-border rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-aureus-gold"
                     placeholder="••••••••" />
            </div>
            <button type="submit" disabled={loading}
                    className="w-full py-2 bg-aureus-gold text-black font-semibold text-sm rounded hover:opacity-90 disabled:opacity-50 transition-opacity">
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-aureus-muted">
          New to Aureus?{" "}
          <Link href="/sign-up" className="text-aureus-gold hover:underline">Create an account</Link>
        </p>
      </div>
    </div>
  );
}
