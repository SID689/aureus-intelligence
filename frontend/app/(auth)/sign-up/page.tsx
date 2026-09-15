"use client";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signup } from "@/lib/api";
import AuthFrame, { GoogleMark, authInput } from "@/components/auth/AuthFrame";

export default function SignUpPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Use at least 8 characters for your password.");
      return;
    }
    setLoading(true);
    try {
      await signup({ email, password, display_name: name });
      const result = await signIn("credentials", { email, password, redirect: false });
      if (result?.error) {
        setError("Your account is ready. Sign in to continue.");
        router.push("/sign-in");
      } else {
        router.push("/");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The account could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthFrame
      title="Create your account"
      lead="The free plan includes fifteen full analyses a day, the complete curriculum and backtesting. No card required."
      below={<>Already have an account? <Link href="/sign-in" className="text-aureus-gold hover:text-aureus-goldbright">Sign in</Link></>}
    >
      <button
        type="button"
        onClick={() => signIn("google", { callbackUrl: "/" })}
        className="w-full h-10 border border-aureus-rulestrong rounded-sm text-[13.5px] text-aureus-text hover:border-aureus-gold transition-colors flex items-center justify-center gap-2.5"
      >
        <GoogleMark /> Continue with Google
      </button>

      <div className="flex items-center gap-3 my-6 label-caps">
        <span className="flex-1 h-px bg-aureus-rule" />or with email<span className="flex-1 h-px bg-aureus-rule" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <p role="alert" className="border border-aureus-crimsondim bg-aureus-crimson/10 px-3 py-2.5 text-[13px] text-aureus-crimson">{error}</p>
        )}
        <label className="block">
          <span className="label-caps">Name</span>
          <input value={name} autoComplete="name" onChange={(e) => setName(e.target.value)} className={`${authInput} mt-2`} />
        </label>
        <label className="block">
          <span className="label-caps">Email</span>
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 className={`${authInput} mt-2`} placeholder="you@example.com" />
        </label>
        <label className="block">
          <span className="label-caps">Password</span>
          <input type="password" required autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)}
                 className={`${authInput} mt-2`} placeholder="At least 8 characters" />
        </label>
        <p className="text-[12px] text-aureus-muted leading-relaxed">
          By creating an account you confirm you are 18 or older, agree to the{" "}
          <Link href="/terms" className="text-aureus-soft underline underline-offset-2 hover:text-aureus-gold">Terms of Service</Link>, and
          acknowledge the <Link href="/privacy" className="text-aureus-soft underline underline-offset-2 hover:text-aureus-gold">Privacy Policy</Link>.
        </p>
        <button type="submit" disabled={loading}
                className="w-full h-10 bg-aureus-gold text-aureus-ink font-semibold text-[13.5px] rounded-sm hover:bg-aureus-goldbright disabled:opacity-50 transition-colors">
          {loading ? "Creating account" : "Create account"}
        </button>
      </form>
    </AuthFrame>
  );
}
