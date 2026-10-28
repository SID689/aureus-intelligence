"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import AuthFrame, { authInput } from "@/components/auth/AuthFrame";
import GoogleSignIn from "@/components/auth/GoogleSignIn";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await signIn("credentials", { email, password, redirect: false });
    setLoading(false);
    if (result?.error) {
      setError("That email and password do not match an account.");
    } else {
      router.push("/");
    }
  }

  return (
    <AuthFrame
      title="Sign in"
      lead="Continue to your research desk."
      below={<>New to Aureus? <Link href="/sign-up" className="text-aureus-gold hover:text-aureus-goldbright">Create an account</Link></>}
    >
      <GoogleSignIn />

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <p role="alert" className="border border-aureus-crimsondim bg-aureus-crimson/10 px-3 py-2.5 text-[13px] text-aureus-crimson">{error}</p>
        )}
        <label className="block">
          <span className="label-caps">Email</span>
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 className={`${authInput} mt-2`} placeholder="you@example.com" />
        </label>
        <label className="block">
          <span className="label-caps">Password</span>
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
                 className={`${authInput} mt-2`} />
        </label>
        <button type="submit" disabled={loading}
                className="w-full h-10 bg-aureus-gold text-aureus-ink font-semibold text-[13.5px] rounded-sm hover:bg-aureus-goldbright disabled:opacity-50 transition-colors">
          {loading ? "Signing in" : "Sign in"}
        </button>
      </form>
    </AuthFrame>
  );
}
