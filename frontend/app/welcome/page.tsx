import Link from "next/link";
import type { Metadata } from "next";
import Logo from "@/components/brand/Logo";
import SiteFooter from "@/components/site/SiteFooter";
import PricingMatrix from "@/components/billing/PricingMatrix";
import type { Plan } from "@/lib/api";

/**
 * The public landing page, set as an editorial document.
 *
 * It shows the product’s working instead of describing it: a specimen tear
 * sheet, the actual horizon weights, the three figures printed beside every
 * score, a ledger of what ships, and the plan matrix read from the database.
 * Server component: static markup, no client JavaScript beyond the matrix.
 */

export const metadata: Metadata = {
  title: "Equity research that shows its working",
  description:
    "Fundamental, technical and sentiment analysis of US equities, with the weighting, data completeness and reasoning behind every score.",
};

export const revalidate = 300;

const API = process.env.NEXTAUTH_API_URL || "http://backend:8000";

async function loadPlans(): Promise<Plan[]> {
  try {
    const res = await fetch(`${API}/api/v1/account/plans`, { next: { revalidate: 300 }, signal: AbortSignal.timeout(4000) });
    if (!res.ok) return [];
    return ((await res.json()) as { plans?: Plan[] }).plans ?? [];
  } catch {
    return [];
  }
}

const FACTS: [string, string][] = [
  ["Coverage", "S&P 500"],
  ["Rescored", "Every 15 min in session"],
  ["Pillars", "Fundamental · Technical · Sentiment"],
  ["Curriculum", "60 lessons"],
];

const WEIGHTS: { horizon: string; range: string; w: [number, number, number] }[] = [
  { horizon: "Short", range: "1 day to 1 month", w: [10, 50, 40] },
  { horizon: "Medium", range: "1 to 6 months", w: [35, 35, 30] },
  { horizon: "Long", range: "1 year and beyond", w: [65, 20, 15] },
];

const PILLARS: { name: string; reads: string; blind: string }[] = [
  {
    name: "Fundamental",
    reads: "Discounted cash flow, margins, returns on capital and balance-sheet durability, read from SEC filings and compared with sector medians.",
    blind: "Cannot explain a six percent move on an earnings surprise.",
  },
  {
    name: "Technical",
    reads: "Trend structure, momentum and volatility, with support and resistance drawn from actual swing pivots.",
    blind: "Says nothing about what the business is worth.",
  },
  {
    name: "Sentiment",
    reads: "News scored by a finance-specific model, filing tone against the prior quarter, and retail positioning weighted by source authority.",
    blind: "The easiest pillar to manipulate, so social input is capped at a minority share.",
  },
];

const DISCLOSURES: [string, string][] = [
  ["Conviction", "How far the evidence leans, discounted when the pillars disagree or the data is thin."],
  ["Pillar agreement", "Whether the three pillars point the same way. A 50 reached by consensus and a 50 reached by cancellation are different findings, and the page says which one you are looking at."],
  ["Data completeness", "How much of each pillar actually computed. A pillar with missing inputs loses weight; it is never padded with a neutral guess."],
];

const MODULES: [string, string, string][] = [
  ["Three-pillar analysis", "Composite score with every sub-signal, its figure, and the weight it carried.", "Sovereign"],
  ["Catalyst timeline", "Earnings dates, SEC 8-K events, dividends, FOMC meetings and FDA calendars around each stock.", "Sovereign"],
  ["Strategy backtesting", "RSI and moving-average strategies replayed bar by bar with commission, slippage and stops.", "Sovereign"],
  ["Curriculum and daily games", "Sixty lessons from first principles to factor mechanics, with calculations to work through.", "Sovereign"],
  ["Written synthesis", "Bull and bear cases edited by a language model, and SEC filing tone against the prior quarter.", "Plus"],
  ["The Quant Lab", "Fama-French factor exposures, bootstrap Monte Carlo, value at risk and expected shortfall.", "Elite"],
  ["Hottest Stocks leaderboard", "Verified Strong Buy entries across the S&P 500, with in-app and push alerts.", "Elite"],
  ["Voice", "Talk through a position with the session carried as context.", "Elite"],
];

export default async function WelcomePage() {
  const plans = await loadPlans();

  return (
    <div className="min-h-screen bg-aureus-ink text-aureus-text">
      <header className="border-b border-aureus-rule">
        <nav className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between gap-6" aria-label="Main">
          <Link href="/welcome" aria-label="Aureus Intelligence home"><Logo size={28} withWordmark wordmarkClassName="text-xl" /></Link>
          <div className="hidden md:flex items-center gap-7 text-[13px] text-aureus-muted">
            <a href="#method" className="hover:text-aureus-text">Method</a>
            <a href="#disclosure" className="hover:text-aureus-text">Disclosure</a>
            <a href="#modules" className="hover:text-aureus-text">Modules</a>
            <a href="#plans" className="hover:text-aureus-text">Plans</a>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/sign-in" className="hidden sm:inline text-[13px] text-aureus-muted hover:text-aureus-text">Sign in</Link>
            <Link href="/sign-up" className="h-9 px-4 inline-flex items-center bg-aureus-gold text-aureus-ink text-[13px] font-semibold rounded-sm hover:bg-aureus-goldbright transition-colors">
              Create account
            </Link>
          </div>
        </nav>
        <div className="border-t border-aureus-rule bg-aureus-panel">
          <dl className="max-w-6xl mx-auto px-5 sm:px-8 flex flex-wrap gap-x-10 gap-y-1 py-2.5 text-[11.5px]">
            {FACTS.map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="label-caps pt-px">{k}</dt>
                <dd className="font-mono-num text-aureus-soft">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </header>

      <main>
        {/* ── Hero ─────────────────────────────────────────────────── */}
        <section className="ruled-field border-b border-aureus-rule">
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16 lg:py-24 grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] gap-x-16 gap-y-14 items-center">
            <div>
              <p className="label-caps text-aureus-gold">Equity research</p>
              <h1 className="font-display text-[48px] sm:text-[64px] leading-[0.98] tracking-[-0.02em] text-aureus-text mt-5">
                Every score, with its working.
              </h1>
              <p className="text-[17px] text-aureus-soft leading-relaxed mt-7 max-w-xl">
                Aureus scores stocks on fundamental, technical and sentiment evidence, then prints what produced the number:
                each signal and its figure, the weight every pillar carried for your holding period, and how much data stood
                behind it.
              </p>
              <div className="flex flex-wrap items-center gap-3 mt-10">
                <Link href="/sign-up" className="h-11 px-6 inline-flex items-center bg-aureus-gold text-aureus-ink text-[14px] font-semibold rounded-sm hover:bg-aureus-goldbright transition-colors">
                  Create a free account
                </Link>
                <Link href="/sign-in" className="h-11 px-6 inline-flex items-center border border-aureus-rulestrong text-aureus-text text-[14px] rounded-sm hover:border-aureus-gold transition-colors">
                  Sign in
                </Link>
              </div>
              <p className="font-mono-num text-[12px] text-aureus-muted mt-5">Free plan: 15 full analyses a day. No card required.</p>
            </div>
            <TearSheet />
          </div>
        </section>

        {/* ── Method ───────────────────────────────────────────────── */}
        <section id="method" className="scroll-mt-4 border-b border-aureus-rule">
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-20 grid lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] gap-x-16 gap-y-10">
            <div className="lg:sticky lg:top-8 self-start">
              <p className="label-caps text-aureus-gold">Method</p>
              <h2 className="font-display text-[36px] leading-[1.08] mt-4">Three kinds of evidence, weighted by how long you hold.</h2>
              <p className="text-[15px] text-aureus-soft leading-relaxed mt-5 max-w-md">
                Each pillar answers a question the other two cannot, and each has a blind spot the others cover. Over weeks, price
                and news carry the information. Over years, the business does.
              </p>
            </div>

            <div className="space-y-12">
              <div className="border border-aureus-rule bg-aureus-panel overflow-x-auto">
                <table className="w-full min-w-[520px] text-left">
                  <caption className="sr-only">Pillar weights by holding period</caption>
                  <thead>
                    <tr className="border-b border-aureus-rule">
                      <th className="px-5 py-3 label-caps font-normal">Holding period</th>
                      {["Fundamental", "Technical", "Sentiment"].map((h) => <th key={h} className="px-5 py-3 label-caps font-normal">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {WEIGHTS.map((row) => (
                      <tr key={row.horizon} className="border-t border-aureus-rulesoft first:border-t-0">
                        <th scope="row" className="px-5 py-4 font-normal">
                          <div className="text-[14px] text-aureus-text">{row.horizon}</div>
                          <div className="text-[11.5px] text-aureus-muted">{row.range}</div>
                        </th>
                        {row.w.map((w, i) => (
                          <td key={i} className="px-5 py-4 align-middle">
                            <div className="flex items-center gap-3">
                              <span className="font-mono-num text-[15px] w-9">{w}%</span>
                              <span className="flex-1 h-1 bg-aureus-panelhigh"><span className="block h-full bg-aureus-gold" style={{ width: `${w}%` }} /></span>
                            </div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <dl className="border-t border-aureus-rule">
                {PILLARS.map((p) => (
                  <div key={p.name} className="grid sm:grid-cols-[9rem_minmax(0,1fr)] gap-x-8 gap-y-2 py-6 border-b border-aureus-rule">
                    <dt className="font-display text-[22px] leading-none">{p.name}</dt>
                    <dd>
                      <p className="text-[14.5px] text-aureus-soft leading-relaxed">{p.reads}</p>
                      <p className="text-[12.5px] text-aureus-muted mt-2"><span className="label-caps mr-2">Blind spot</span>{p.blind}</p>
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* ── Disclosure ───────────────────────────────────────────── */}
        <section id="disclosure" className="scroll-mt-4 border-b border-aureus-rule bg-aureus-panel">
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-20">
            <div className="max-w-2xl">
              <p className="label-caps text-aureus-gold">Disclosure</p>
              <h2 className="font-display text-[36px] leading-[1.08] mt-4">Three figures sit beside every composite.</h2>
              <p className="text-[15px] text-aureus-soft leading-relaxed mt-5">
                A score alone invites blind trust or dismissal. These say how much the score deserves.
              </p>
            </div>
            <ol className="mt-12 border-t border-aureus-rule">
              {DISCLOSURES.map(([title, body], i) => (
                <li key={title} className="grid md:grid-cols-[6rem_16rem_minmax(0,1fr)] gap-x-8 gap-y-2 py-7 border-b border-aureus-rule">
                  <span className="font-mono-num text-[40px] leading-none text-aureus-golddim">{String(i + 1).padStart(2, "0")}</span>
                  <h3 className="font-display text-[24px] leading-tight">{title}</h3>
                  <p className="text-[15px] text-aureus-soft leading-relaxed max-w-2xl">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── Modules ──────────────────────────────────────────────── */}
        <section id="modules" className="scroll-mt-4 border-b border-aureus-rule">
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-20 grid lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)] gap-x-16 gap-y-10">
            <div>
              <p className="label-caps text-aureus-gold">Modules</p>
              <h2 className="font-display text-[36px] leading-[1.08] mt-4">What ships today.</h2>
              <p className="text-[15px] text-aureus-soft leading-relaxed mt-5 max-w-sm">
                Everything listed is live. The right-hand column names the first plan that includes it.
              </p>
            </div>
            <div className="border-t border-aureus-rule">
              {MODULES.map(([name, detail, plan]) => (
                <div key={name} className="grid grid-cols-[minmax(0,1fr)_5.5rem] sm:grid-cols-[13rem_minmax(0,1fr)_6rem] gap-x-6 gap-y-1 py-4 border-b border-aureus-rulesoft">
                  <div className="text-[14.5px] text-aureus-text">{name}</div>
                  <div className="col-span-2 sm:col-span-1 row-start-2 sm:row-start-auto text-[13px] text-aureus-muted leading-relaxed">{detail}</div>
                  <div className="col-start-2 row-start-1 sm:col-start-auto sm:row-start-auto text-right label-caps pt-1 text-aureus-soft">{plan}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Plans ────────────────────────────────────────────────── */}
        <section id="plans" className="scroll-mt-4 border-b border-aureus-rule">
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-20">
            <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-4 mb-10">
              <div className="max-w-2xl">
                <p className="label-caps text-aureus-gold">Plans</p>
                <h2 className="font-display text-[36px] leading-[1.08] mt-4">Four plans. One method.</h2>
              </div>
              <p className="text-[14px] text-aureus-soft leading-relaxed max-w-md">
                Scoring is identical on every plan. Paid plans raise the ceilings and add depth: written synthesis from $12, then the
                Quant Lab, the leaderboard and voice.
              </p>
            </div>
            <PricingMatrix plans={plans} mode="public" highlight="plus" />
          </div>
        </section>

        {/* ── Close ────────────────────────────────────────────────── */}
        <section>
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-20 grid md:grid-cols-[minmax(0,1fr)_auto] gap-8 items-end">
            <p className="font-display text-[34px] sm:text-[42px] leading-[1.1] max-w-2xl">
              Open an account and read your first analysis in under a minute.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/sign-up" className="h-11 px-6 inline-flex items-center bg-aureus-gold text-aureus-ink text-[14px] font-semibold rounded-sm hover:bg-aureus-goldbright transition-colors">
                Create a free account
              </Link>
              <Link href="#plans" className="h-11 px-6 inline-flex items-center border border-aureus-rulestrong text-aureus-text text-[14px] rounded-sm hover:border-aureus-gold transition-colors">
                Compare plans
              </Link>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

/**
 * A specimen of the analysis output, set as a printed tear sheet. Marked as a
 * specimen with illustrative figures, because a public page must never
 * present a rating that could be read as current advice on a real stock.
 */
function TearSheet() {
  const pillars: [string, number, number, number][] = [
    ["Fundamental", 81, 35, 96],
    ["Technical", 54, 35, 100],
    ["Sentiment", 52, 30, 68],
  ];
  const evidence: [string, string, string, "up" | "flat"][] = [
    ["Operating margin", "31.8%", "Top decile for the sector", "up"],
    ["Revenue growth", "+9.6%", "Against a 4.1% sector median", "up"],
    ["RSI (14)", "58", "No momentum edge either way", "flat"],
    ["News tone", "132 articles", "Authority-weighted, balanced", "flat"],
  ];
  return (
    <figure className="border border-aureus-rulestrong bg-aureus-panel" aria-label="Specimen analysis output with illustrative figures">
      <div className="flex items-center justify-between px-5 py-2.5 border-b border-aureus-rule bg-aureus-panellift">
        <span className="label-caps">Specimen · illustrative figures</span>
        <span className="font-mono-num text-[11px] text-aureus-muted">Medium term</span>
      </div>

      <div className="px-5 pt-5 pb-4 flex items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="font-mono-num text-[26px] leading-none">AAPL</span>
            <span className="border border-aureus-gold/60 px-1.5 py-0.5 font-mono-num text-[10px] uppercase tracking-[0.14em] text-aureus-gold">Hold</span>
          </div>
          <p className="text-[11.5px] text-aureus-muted mt-2">Fundamentals via Finnhub and SEC EDGAR</p>
        </div>
        <div className="text-right">
          <div className="font-mono-num text-[34px] leading-none text-aureus-gold">62.8</div>
          <div className="label-caps mt-1.5">Composite</div>
        </div>
      </div>

      <div className="px-5 pb-4">
        <div className="relative h-1.5 bg-aureus-panelhigh">
          <div className="absolute inset-y-0 left-0 bg-aureus-gold" style={{ width: "62.8%" }} />
          <span className="absolute -top-1 -bottom-1 w-px bg-aureus-rulestrong" style={{ left: "35%" }} />
          <span className="absolute -top-1 -bottom-1 w-px bg-aureus-rulestrong" style={{ left: "65%" }} />
        </div>
        <div className="grid grid-cols-3 mt-4 border-t border-aureus-rule pt-3 font-mono-num text-[12px]">
          <div><span className="label-caps block">Conviction</span>41</div>
          <div><span className="label-caps block">Agreement</span>67%</div>
          <div><span className="label-caps block">Data</span>88%</div>
        </div>
      </div>

      <table className="w-full border-t border-aureus-rule text-left">
        <thead>
          <tr className="border-b border-aureus-rule">
            {["Pillar", "Score", "Weight", "Data"].map((h, i) => (
              <th key={h} className={`px-5 py-2 label-caps font-normal ${i > 0 ? "text-right" : ""}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono-num text-[12.5px]">
          {pillars.map(([name, score, weight, data]) => (
            <tr key={name} className="border-t border-aureus-rulesoft first:border-t-0">
              <td className="px-5 py-2 font-sans text-[13px] text-aureus-soft">{name}</td>
              <td className={`px-5 py-2 text-right ${score >= 65 ? "text-aureus-emerald" : "text-aureus-gold"}`}>{score}</td>
              <td className="px-5 py-2 text-right text-aureus-soft">{weight}%</td>
              <td className="px-5 py-2 text-right text-aureus-muted">{data}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="border-t border-aureus-rule px-5 py-3">
        <p className="label-caps">Evidence</p>
        <ul className="mt-2">
          {evidence.map(([label, figure, note, tone]) => (
            <li key={label} className="grid grid-cols-[7.5rem_5.5rem_minmax(0,1fr)] gap-3 py-1.5 text-[12px] border-t border-aureus-rulesoft first:border-t-0">
              <span className="text-aureus-soft">{label}</span>
              <span className={`font-mono-num ${tone === "up" ? "text-aureus-emerald" : "text-aureus-text"}`}>{figure}</span>
              <span className="text-aureus-muted truncate">{note}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="border-t border-aureus-rule px-5 py-3 bg-aureus-ink">
        <p className="label-caps">What would change this view</p>
        <p className="text-[12px] text-aureus-soft leading-relaxed mt-1.5">
          <span className="font-mono-num text-aureus-golddim mr-2">1.</span>
          The next earnings report: a miss against consensus would test the case sooner than any slower evidence.
        </p>
      </div>
    </figure>
  );
}
