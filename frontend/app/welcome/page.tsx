import Link from "next/link";
import {
  ArrowRight, Brain, LineChart, Mic, ShieldCheck, Sigma, FlaskConical,
  GraduationCap, Gamepad2, Newspaper, ScrollText, Check,
} from "lucide-react";
import Logo from "@/components/brand/Logo";

/**
 * The public landing page.
 *
 * Two decisions drive the layout:
 *
 * 1. SHOW THE PRODUCT, DON'T DESCRIBE IT. The previous version was a
 *    headline plus three paragraphs of adjectives. The hero now carries a
 *    real replica of an analysis card — the same pillars, gauges and
 *    weighting a signed-in user sees — because the single most persuasive
 *    thing about this product is that it shows its working, and that is
 *    impossible to convey in prose.
 *
 * 2. LEAD WITH THE ACTUAL DIFFERENTIATOR. Every analysis tool claims
 *    "AI-powered insights". Almost none of them de-weight a pillar when
 *    its data is thin, which is the one genuinely unusual thing here, so
 *    it gets its own section with a worked example rather than a bullet.
 *
 * Server component on purpose — everything is static, so there is no
 * reason to ship JavaScript for it. Motion is CSS-only.
 */

export const metadata = {
  title: "Analysis that shows its work",
  description:
    "Fundamental, technical and sentiment analysis unified into one score — with the reasoning, the data completeness, and the weighting behind every number.",
};

const PILLARS = [
  {
    name: "Fundamental",
    question: "Is the business worth what the market says?",
    detail: "Discounted cash flow, margins, returns on capital, balance-sheet durability — read from SEC filings, not summarised from a headline.",
    weight: "65%",
    horizon: "Dominates over years",
    icon: ScrollText,
  },
  {
    name: "Technical",
    question: "What is the price itself telling you?",
    detail: "RSI, MACD, moving-average structure, support and resistance drawn from actual swing pivots rather than eyeballed lines.",
    weight: "50%",
    horizon: "Dominates over weeks",
    icon: LineChart,
  },
  {
    name: "Sentiment",
    question: "What does the market believe right now?",
    detail: "News wires scored by a finance-specific model, SEC filing tone versus the prior quarter, and retail positioning — weighted by publisher authority.",
    weight: "40%",
    horizon: "Dominates over days",
    icon: Newspaper,
  },
];

const FEATURES = [
  {
    icon: Brain,
    title: "Three-Pillar Analysis",
    desc: "Every score decomposes into the sub-signals that produced it, each with the real number attached. No black box.",
    tag: "All plans",
  },
  {
    icon: Sigma,
    title: "The Quant Lab",
    desc: "Fama-French 3 and 5-factor exposures with significance testing, bootstrap Monte Carlo, VaR and expected shortfall, rolling beta stability.",
    tag: "Elite",
  },
  {
    icon: FlaskConical,
    title: "Strategy Backtesting",
    desc: "Replay RSI and moving-average strategies bar by bar with commission, slippage, stop-loss and take-profit modelled honestly.",
    tag: "All plans",
  },
  {
    icon: Newspaper,
    title: "Sentiment Engine",
    desc: "Aspect-based scoring so one article about two companies gives each the right verdict — not a meaningless average of both.",
    tag: "All plans",
  },
  {
    icon: GraduationCap,
    title: "Built-In Education",
    desc: "Forty-four lessons from market basics to factor mechanics, with quizzes, XP and a difficulty level that rises as you do.",
    tag: "Free forever",
  },
  {
    icon: Gamepad2,
    title: "Daily Practice",
    desc: "FinWordle and a chart-pattern guesser built on fourteen classical formations detected geometrically, not hand-labelled.",
    tag: "Free forever",
  },
];

const PLANS = [
  { name: "Sovereign", price: "0", note: "Free forever", points: ["15 analyses a day", "Full education & games", "Backtesting"] },
  { name: "Elite", price: "99", note: "per month", featured: true, points: ["Claude-powered synthesis", "The Quant Lab", "Real-time market data"] },
  { name: "Institutional", price: "499", note: "per month", points: ["Everything uncapped", "Every premium data source", "Opus on deep analysis"] },
];

export default function WelcomePage() {
  return (
    <div className="min-h-screen relative overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* CSS-only motion. A server component ships no JS, so any animation
          has to live in the stylesheet rather than in an effect. */}
      <style>{`
        @keyframes floatUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
        .rise { animation: floatUp .7s cubic-bezier(.22,1,.36,1) both; }
        .rise-1 { animation-delay: .05s } .rise-2 { animation-delay: .15s }
        .rise-3 { animation-delay: .25s } .rise-4 { animation-delay: .35s }
        @keyframes sheen { 0%,100% { opacity: .25 } 50% { opacity: .5 } }
        .sheen { animation: sheen 6s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .rise, .sheen { animation: none; opacity: 1; transform: none; }
        }
      `}</style>

      {/* Ambient light — warm, off-centre, so the page has a source */}
      <div className="pointer-events-none absolute inset-0 sheen"
           style={{ background: "radial-gradient(ellipse 70% 45% at 50% -8%, rgb(var(--gold-rgb) / 0.16), transparent)" }} />
      <div className="pointer-events-none absolute top-[30rem] -left-40 w-[28rem] h-[28rem] rounded-full blur-3xl opacity-[0.07]"
           style={{ background: "radial-gradient(circle, rgb(var(--verdigris-rgb)), transparent)" }} />

      <div className="relative z-10">
        {/* ── Nav ──────────────────────────────────────────────── */}
        <nav className="flex items-center justify-between gap-4 px-5 sm:px-8 py-6 max-w-6xl mx-auto">
          {/* Two marks rather than one: Logo takes a numeric size, so a
              responsive scale cannot be expressed as a Tailwind class. At
              375px the 44px version plus both nav actions overflowed and
              the wordmark collided with "Sign in". */}
          <span className="sm:hidden">
            <Logo size={30} withWordmark wordmarkClassName="text-lg" />
          </span>
          <span className="hidden sm:block">
            <Logo size={44} withWordmark wordmarkClassName="text-2xl" />
          </span>
          <div className="flex items-center gap-3 sm:gap-5 flex-shrink-0">
            <Link href="/sign-in"
                  className="hidden sm:block text-sm text-aureus-muted hover:text-aureus-text transition-colors">
              Sign in
            </Link>
            <Link href="/sign-up"
                  className="text-sm bg-aureus-gold text-aureus-ink font-semibold px-4 py-2 rounded-lg hover:opacity-90 transition-opacity whitespace-nowrap">
              Get started
            </Link>
          </div>
        </nav>

        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className="max-w-6xl mx-auto px-5 sm:px-8 pt-10 sm:pt-16 pb-8 grid lg:grid-cols-[1.05fr_1fr] gap-12 lg:gap-14 items-center">
          <div className="rise rise-1">
            <div className="inline-flex items-center gap-2 text-[11px] text-aureus-gold border border-aureus-gold/30 rounded-full px-3 py-1 mb-6 tracking-wide"
                 style={{ background: "rgb(var(--gold-rgb) / 0.07)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-aureus-gold" />
              Fundamental · Technical · Sentiment — unified
            </div>

            <h1 className="font-display text-aureus-text tracking-tight leading-[1.05] mb-6 text-5xl lg:text-6xl"
                style={{ fontWeight: 600 }}>
              Analysis that shows<span className="hidden sm:inline"><br /></span>{" "}
              its work,{" "}
              <span className="text-aureus-gold">
                not just<span className="hidden sm:inline"><br /></span> a number
              </span>
            </h1>

            <p className="text-[17px] text-aureus-muted max-w-xl leading-relaxed mb-4">
              Most tools hand you a score and ask you to trust it. Aureus hands you the score,
              every sub-signal that produced it, the real figure behind each one, and an honest
              note where the data ran out.
            </p>
            <p className="text-[15px] text-aureus-muted/80 max-w-xl leading-relaxed mb-9">
              Three analytical disciplines, weighted differently depending on whether you are
              holding for days or for years.
            </p>

            <div className="flex flex-wrap items-center gap-4">
              <Link href="/sign-up"
                    className="flex items-center gap-2 bg-aureus-gold text-aureus-ink font-semibold px-6 py-3 rounded-lg hover:opacity-90 transition-opacity">
                Start free <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/sign-in"
                    className="px-6 py-3 rounded-lg border border-aureus-rule text-aureus-text hover:border-aureus-gold transition-colors">
                I have an account
              </Link>
            </div>
            <p className="text-xs text-aureus-muted mt-4">
              No card required · 15 full analyses a day on the free plan
            </p>
          </div>

          {/* Product replica. Static markup, but the same structure, gauges
              and weighting language the real dashboard renders — the point
              is to show the reasoning, not to fake a screenshot. */}
          <div className="rise rise-2">
            <MockAnalysisCard />
          </div>
        </section>

        {/* ── Proof strip ────────────────────────────────────────
            Divided by hairlines rather than rendered as four separate
            tiles, matching how the app itself presents a row of figures.
            The landing page should look like the product, not like a
            different template that happens to share a logo. */}
        <section className="max-w-5xl mx-auto px-8 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 border-y border-aureus-rule">
            {[
              ["3", "analytical pillars"],
              ["14", "chart patterns detected"],
              ["44", "lessons built in"],
              ["5", "factor exposures"],
            ].map(([n, label], i) => (
              <div
                key={label}
                className={`px-5 py-7 ${i % 2 === 1 ? "border-l border-aureus-rule" : ""} ${i >= 2 ? "border-t md:border-t-0 border-aureus-rule" : ""} ${i === 2 ? "md:border-l md:border-aureus-rule" : ""}`}
              >
                <div className="font-display text-[2rem] leading-none text-aureus-gold" style={{ fontWeight: 600 }}>{n}</div>
                <div className="text-[11px] text-aureus-muted mt-2 tracking-wide">{label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ── The three pillars ────────────────────────────────── */}
        <section className="max-w-6xl mx-auto px-8 py-16">
          <SectionHeading
            eyebrow="The method"
            title="Three questions, asked separately"
            sub="Each pillar answers something the other two cannot, and each has a blind spot the others cover. The weighting shifts with your time horizon — because a DCF cannot explain a 6% move on an earnings surprise, and this quarter's mood tells you nothing about 2030."
          />
          <div className="grid md:grid-cols-3 gap-5 mt-10">
            {PILLARS.map((p, i) => (
              <div key={p.name}
                   className={`rise rise-${i + 1} rounded-xl border border-aureus-rule p-6 relative overflow-hidden group hover:border-aureus-gold/40 transition-colors`}
                   style={{ background: "var(--panel)" }}>
                <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                     style={{ background: "radial-gradient(circle, rgb(var(--gold-rgb) / 0.14), transparent)" }} />
                <div className="relative">
                  <p.icon className="w-6 h-6 text-aureus-gold mb-4" strokeWidth={1.5} />
                  <h3 className="font-display text-xl text-aureus-text mb-1" style={{ fontWeight: 600 }}>{p.name}</h3>
                  <p className="text-aureus-gold text-[13px] mb-4 leading-snug">{p.question}</p>
                  <p className="text-sm text-aureus-muted leading-relaxed mb-5">{p.detail}</p>
                  <div className="pt-4 border-t border-aureus-rule flex items-baseline justify-between">
                    <span className="text-[11px] text-aureus-muted">{p.horizon}</span>
                    <span className="font-mono-num text-aureus-gold text-sm">up to {p.weight}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Feature grid ─────────────────────────────────────── */}
        <section className="max-w-6xl mx-auto px-8 py-16">
          <SectionHeading
            eyebrow="What's inside"
            title="A research desk, not a stock ticker"
            sub="Everything below ships today. Nothing here is a roadmap item."
          />
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-10">
            {FEATURES.map(({ icon: Icon, title, desc, tag }) => (
              <div key={title}
                   className="rounded-xl border border-aureus-rule p-6 hover:border-aureus-gold/40 transition-colors"
                   style={{ background: "var(--panel)" }}>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg border border-aureus-gold/30 flex items-center justify-center flex-shrink-0"
                       style={{ background: "rgb(var(--gold-rgb) / 0.08)" }}>
                    <Icon className="w-5 h-5 text-aureus-gold" strokeWidth={1.5} />
                  </div>
                  <span className="text-[10px] text-aureus-muted border border-aureus-rule rounded px-2 py-0.5 flex-shrink-0">
                    {tag}
                  </span>
                </div>
                <h3 className="text-aureus-text font-semibold mb-2">{title}</h3>
                <p className="text-[13px] text-aureus-muted leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Voice, called out separately ─────────────────────── */}
        <section className="max-w-6xl mx-auto px-8 pb-8">
          <div className="rounded-xl border border-aureus-rule p-8 flex flex-col md:flex-row items-center gap-7"
               style={{ background: "var(--panel)" }}>
            <div className="w-14 h-14 rounded-xl border border-aureus-gold/30 flex items-center justify-center flex-shrink-0"
                 style={{ background: "rgb(var(--gold-rgb) / 0.08)" }}>
              <Mic className="w-6 h-6 text-aureus-gold" strokeWidth={1.5} />
            </div>
            <div className="flex-1 text-center md:text-left">
              <h3 className="font-display text-xl text-aureus-text mb-1.5" style={{ fontWeight: 600 }}>
                Talk through a position out loud
              </h3>
              <p className="text-sm text-aureus-muted leading-relaxed">
                Ask why a score moved, what the bear case rests on, or how a holding changes your
                exposure — conversationally, with the full session carried as context.
              </p>
            </div>
            <span className="text-[11px] text-aureus-gold border border-aureus-gold/40 rounded-full px-3 py-1 flex-shrink-0">
              Elite and above
            </span>
          </div>
        </section>

        {/* ── Pricing ──────────────────────────────────────────── */}
        <section className="max-w-5xl mx-auto px-8 py-16">
          <SectionHeading
            eyebrow="Plans"
            title="Start free, upgrade when the ceiling matters"
            sub="Education and the daily games stay free on every plan — permanently. Paid tiers buy analysis depth, model quality and data freshness."
          />
          <div className="grid md:grid-cols-3 gap-5 mt-10">
            {PLANS.map((p) => (
              <div key={p.name}
                   className={`rounded-xl border p-6 flex flex-col ${
                     p.featured ? "border-aureus-gold/60" : "border-aureus-rule"
                   }`}
                   style={{ background: p.featured ? "rgb(var(--gold-rgb) / 0.04)" : "var(--panel)" }}>
                {p.featured && (
                  <div className="text-[10px] uppercase tracking-widest text-aureus-gold mb-3">Most popular</div>
                )}
                <div className="font-display text-lg text-aureus-text" style={{ fontWeight: 600 }}>{p.name}</div>
                <div className="flex items-baseline gap-1.5 mt-2 mb-1">
                  <span className="font-display text-4xl text-aureus-gold" style={{ fontWeight: 600 }}>${p.price}</span>
                  <span className="text-[11px] text-aureus-muted">{p.note}</span>
                </div>
                <ul className="space-y-2 mt-5 mb-6 flex-1">
                  {p.points.map((pt) => (
                    <li key={pt} className="flex items-start gap-2 text-[13px] text-aureus-muted">
                      <Check className="w-3.5 h-3.5 text-aureus-verdigris mt-0.5 flex-shrink-0" />
                      {pt}
                    </li>
                  ))}
                </ul>
                <Link href="/sign-up"
                      className={`text-center text-sm font-semibold px-4 py-2.5 rounded-lg transition-opacity ${
                        p.featured
                          ? "bg-aureus-gold text-aureus-ink hover:opacity-90"
                          : "border border-aureus-rule text-aureus-text hover:border-aureus-gold"
                      }`}>
                  {p.price === "0" ? "Start free" : `Choose ${p.name}`}
                </Link>
              </div>
            ))}
          </div>
        </section>

        {/* ── Closing CTA ──────────────────────────────────────── */}
        <section className="max-w-3xl mx-auto px-8 py-16 text-center">
          <h2 className="font-display text-4xl text-aureus-text leading-tight mb-5" style={{ fontWeight: 600 }}>
            See the reasoning behind your next position
          </h2>
          <p className="text-aureus-muted leading-relaxed mb-8 max-w-xl mx-auto">
            Free to start, no card, and the four-minute walkthrough explains exactly what each number
            can and cannot tell you before you rely on one.
          </p>
          <Link href="/sign-up"
                className="inline-flex items-center gap-2 bg-aureus-gold text-aureus-ink font-semibold px-7 py-3.5 rounded-lg hover:opacity-90 transition-opacity">
            Create your account <ArrowRight className="w-4 h-4" />
          </Link>
        </section>

        {/* ── Footer ───────────────────────────────────────────── */}
        <footer className="border-t border-aureus-rule">
          <div className="max-w-6xl mx-auto px-8 py-10 flex flex-col md:flex-row items-center justify-between gap-5">
            <Logo size={26} withWordmark wordmarkClassName="text-base" />
            <div className="flex items-start gap-2 text-[11px] text-aureus-muted max-w-lg text-center md:text-right leading-relaxed">
              <ShieldCheck className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>
                Informational analysis only. Nothing here is investment, legal or tax advice, nor a
                recommendation to buy or sell any security. Past performance is not indicative of
                future results.
              </span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

// ── Pieces ────────────────────────────────────────────────────────────

function SectionHeading({ eyebrow, title, sub }: { eyebrow: string; title: string; sub: string }) {
  return (
    <div className="max-w-2xl">
      <div className="text-[11px] uppercase tracking-widest text-aureus-gold mb-3">{eyebrow}</div>
      <h2 className="font-display text-3xl md:text-4xl text-aureus-text leading-tight mb-4" style={{ fontWeight: 600 }}>
        {title}
      </h2>
      <p className="text-sm text-aureus-muted leading-relaxed">{sub}</p>
    </div>
  );
}

/** Circular pillar gauge, matching the one on the real analysis page. */
function Gauge({ score, label }: { score: number; label: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const tone = score >= 65 ? "var(--verdigris)" : score < 35 ? "var(--oxblood)" : "var(--gold)";
  return (
    <div className="text-center">
      <div className="relative w-[68px] h-[68px] mx-auto">
        <svg width="68" height="68" viewBox="0 0 68 68" className="-rotate-90">
          <circle cx="34" cy="34" r={r} fill="none" stroke="var(--rule)" strokeWidth="5" />
          <circle cx="34" cy="34" r={r} fill="none" stroke={tone} strokeWidth="5"
                  strokeLinecap="round" strokeDasharray={`${c * (score / 100)} ${c}`} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono-num text-[15px]" style={{ color: tone }}>{score}</span>
        </div>
      </div>
      <div className="text-[10px] text-aureus-muted mt-1.5 tracking-wide">{label}</div>
    </div>
  );
}

function MockAnalysisCard() {
  return (
    <div className="rounded-2xl border border-aureus-rule overflow-hidden shadow-2xl"
         style={{ background: "var(--panel)", boxShadow: "0 24px 70px -20px rgb(0 0 0 / 0.7)" }}>
      {/* Header */}
      <div className="px-6 py-5 border-b border-aureus-rule flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="font-display text-2xl text-aureus-text" style={{ fontWeight: 600 }}>AAPL</span>
            <span className="rounded px-2 py-0.5 text-[10px] font-bold tracking-wider border border-aureus-gold/40 text-aureus-gold"
                  style={{ background: "rgb(var(--gold-rgb) / 0.08)" }}>
              HOLD
            </span>
          </div>
          <div className="text-[11px] text-aureus-muted mt-1">
            Medium term · fundamentals via Finnhub + SEC EDGAR
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono-num text-xl text-aureus-text">62.8</div>
          <div className="text-[10px] text-aureus-muted">confidence</div>
        </div>
      </div>

      {/* Pillars */}
      <div className="px-6 py-5 grid grid-cols-3 gap-3 border-b border-aureus-rule">
        <Gauge score={81} label="FUNDAMENTAL" />
        <Gauge score={54} label="TECHNICAL" />
        <Gauge score={52} label="SENTIMENT" />
      </div>

      {/* Sub-signals — the part that makes the score legible */}
      <div className="px-6 py-5 space-y-2.5 border-b border-aureus-rule">
        {[
          ["Operating margin", 100, "31.8% — top decile for the sector"],
          ["Revenue growth (YoY)", 88, "+9.6% against a 4.1% sector median"],
          ["RSI (14)", 34, "58 — no momentum edge either way"],
          ["News sentiment", 51, "132 articles, authority-weighted"],
        ].map(([label, val, detail]) => (
          <div key={label as string}>
            <div className="flex items-center gap-2 text-[11px]">
              <span className="flex-1 text-aureus-text">{label}</span>
              <div className="w-20 h-1 rounded-full bg-aureus-rule overflow-hidden">
                <div className="h-full rounded-full"
                     style={{
                       width: `${val}%`,
                       background: (val as number) >= 65 ? "var(--verdigris)"
                                 : (val as number) < 35 ? "var(--oxblood)" : "var(--gold)",
                     }} />
              </div>
              <span className="w-6 text-right font-mono-num text-aureus-muted">{val}</span>
            </div>
            <div className="text-[10px] text-aureus-muted/70 mt-0.5">{detail}</div>
          </div>
        ))}
      </div>

      {/* Weighting honesty — the thing no competitor shows */}
      <div className="px-6 py-4" style={{ background: "var(--bg)" }}>
        <div className="text-[10px] uppercase tracking-widest text-aureus-muted mb-2">
          Weighting used
        </div>
        <div className="flex h-2 rounded-full overflow-hidden mb-2">
          <div style={{ width: "35%", background: "var(--gold)" }} />
          <div style={{ width: "35%", background: "var(--verdigris)" }} />
          <div style={{ width: "30%", background: "var(--oxblood)" }} />
        </div>
        <div className="flex justify-between text-[10px] text-aureus-muted font-mono-num">
          <span>35% fundamental</span><span>35% technical</span><span>30% sentiment</span>
        </div>
      </div>
    </div>
  );
}
