"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";

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
    const result = await signIn("credentials", {
      email, password, redirect: false,
    });
    setLoading(false);
    if (result?.error) {
      setError("Invalid email or password.");
    } else {
      router.push("/");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center"
         style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="text-center">
          <div className="text-aureus-gold text-3xl font-bold tracking-wide mb-1">◆ AUREUS</div>
          <p className="text-aureus-muted text-sm">Intelligence Platform</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}
              className="rounded-xl border border-aureus-border p-6 space-y-4"
              style={{ background: "var(--surface)" }}>
          <h2 className="text-white font-semibold text-lg">Sign in</h2>

          {error && (
            <div className="rounded p-2 bg-red-950/40 border border-aureus-red text-aureus-red text-sm">
              {error}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs text-aureus-muted">Email</label>
            <input
              type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-transparent border border-aureus-border rounded px-3 py-2
                         text-white text-sm focus:outline-none focus:border-aureus-gold"
              placeholder="you@example.com"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-aureus-muted">Password</label>
            <input
              type="password" required value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-transparent border border-aureus-border rounded px-3 py-2
                         text-white text-sm focus:outline-none focus:border-aureus-gold"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit" disabled={loading}
            className="w-full py-2 bg-aureus-gold text-black font-semibold text-sm rounded
                       hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-xs text-aureus-muted">
          For institutional access, contact your administrator.
        </p>
      </div>
    </div>
  );
}
