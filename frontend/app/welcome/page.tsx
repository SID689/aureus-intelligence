import Link from "next/link";
import { ArrowRight, Brain, LineChart, Mic, ShieldCheck, Zap } from "lucide-react";

export default function WelcomePage() {
  return (
    <div className="min-h-screen relative overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* Ambient background glow */}
      <div className="pointer-events-none absolute inset-0 opacity-40"
           style={{
             background: "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(212,168,67,0.15), transparent)",
           }} />
      <div className="pointer-events-none absolute -top-40 -right-40 w-96 h-96 rounded-full blur-3xl opacity-20"
           style={{ background: "radial-gradient(circle, #d4a843, transparent)" }} />

      <div className="relative z-10">
        {/* Nav */}
        <nav className="flex items-center justify-between px-8 py-6 max-w-6xl mx-auto">
          <div className="font-display text-aureus-gold text-lg tracking-wide" style={{ fontWeight: 600 }}>Aureus</div>
          <div className="flex items-center gap-4">
            <Link href="/sign-in" className="text-sm text-aureus-muted hover:text-white transition-colors">Sign in</Link>
            <Link href="/sign-up"
                  className="text-sm bg-aureus-gold text-black font-semibold px-4 py-2 rounded-lg hover:opacity-90 transition-opacity">
              Get started
            </Link>
          </div>
        </nav>

        {/* Hero */}
        <div className="max-w-4xl mx-auto px-8 pt-20 pb-16 text-center">
          <div className="inline-flex items-center gap-2 text-xs text-aureus-gold border border-aureus-gold/30 rounded-full px-3 py-1 mb-6"
               style={{ background: "rgba(212,168,67,0.08)" }}>
            <Zap className="w-3 h-3" /> Fundamental · Technical · Quantitative — unified
          </div>
          <h1 className="font-display text-5xl text-white tracking-tight leading-tight mb-6" style={{ fontWeight: 600 }}>
            Analysis that shows its work,<br />
            <span className="text-aureus-gold">not just a number</span>
          </h1>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto leading-relaxed mb-10">
            Aureus blends three distinct analytical disciplines into every score — and when one
            lacks reliable data for a stock, it's mathematically de-weighted instead of quietly
            dragging your signal toward a false middle ground. Every score comes with the reasoning
            behind it.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link href="/sign-up"
                  className="flex items-center gap-2 bg-aureus-gold text-black font-semibold px-6 py-3 rounded-lg hover:opacity-90 transition-opacity">
              Start free <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="/sign-in"
                  className="px-6 py-3 rounded-lg border border-aureus-border text-white hover:border-aureus-gold transition-colors">
              I have an account
            </Link>
          </div>
        </div>

        {/* Feature grid */}
        <div className="max-w-5xl mx-auto px-8 py-16 grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              icon: Brain,
              title: "Ensemble Analysis",
              desc: "DCF valuation, RSI/MACD momentum, and statistical ML signals combined with data-aware reweighting — never a blind average.",
            },
            {
              icon: LineChart,
              title: "Live Market Data",
              desc: "Real-time pricing via a Polygon-first fallback chain, with support/resistance and volume profile overlays on every chart.",
            },
            {
              icon: Mic,
              title: "Voice-First Interface",
              desc: "Discuss your portfolio and refine strategies conversationally, with full context carried across the session.",
            },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="rounded-xl border border-aureus-border p-6 space-y-3 hover:border-aureus-gold/30 transition-colors"
                 style={{ background: "var(--surface)" }}>
              <div className="w-10 h-10 rounded-lg bg-aureus-gold/10 border border-aureus-gold/30 flex items-center justify-center">
                <Icon className="w-5 h-5 text-aureus-gold" />
              </div>
              <h3 className="text-white font-semibold">{title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

        {/* Trust bar */}
        <div className="max-w-3xl mx-auto px-8 pb-20 text-center">
          <div className="flex items-center justify-center gap-2 text-xs text-aureus-muted">
            <ShieldCheck className="w-4 h-4" />
            Informational analysis only. Not financial advice. Past performance is not indicative of future results.
          </div>
        </div>
      </div>
    </div>
  );
}
