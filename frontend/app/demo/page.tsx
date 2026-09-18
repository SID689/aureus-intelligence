import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import type { Metadata } from "next";
import { authOptions } from "@/lib/auth";
import AuthFrame from "@/components/auth/AuthFrame";
import DemoEntry from "@/components/demo/DemoEntry";
import { DEMO_MODE, SHOWCASE_TICKERS } from "@/lib/demo";

export const metadata: Metadata = {
  title: "Institutional Demo · Aureus Intelligence",
  description: "A showcase session on the Institutional plan, with every feature unlocked.",
  robots: { index: false, follow: false },
};

const INCLUDED: [string, string][] = [
  ["Leaderboard", "The S&P 500 ranked by composite, rescored through the session"],
  ["Catalysts", "Earnings, filings, dividends and policy dates on one timeline"],
  ["Sentiment", "News, filing tone and retail messages, weighted by source"],
  ["Backtesting", "Twenty-five names, full history, commission and slippage modelled"],
  ["Voice", "Spoken questions against your own book"],
  ["Quant Lab", "Monte Carlo, value at risk, custom peer sets"],
];

export default async function DemoPage() {
  const session = await getServerSession(authOptions);
  if (session) redirect("/");

  if (!DEMO_MODE) {
    return (
      <AuthFrame
        title="The demo is not open on this deployment"
        lead="This build was compiled without the showcase environment. Everything it demonstrates is available on a normal account."
        below={
          <>
            Create an account at{" "}
            <Link href="/sign-up" className="text-aureus-gold hover:text-aureus-goldbright">sign-up</Link>
            {", or read what the plans include on the "}
            <Link href="/welcome" className="text-aureus-gold hover:text-aureus-goldbright">overview</Link>.
          </>
        }
      >
        <p className="text-[13px] text-aureus-muted leading-relaxed">
          Demo mode is set at build time, so whether a deployment can issue unlocked
          accounts is a property of the artefact rather than a runtime switch.
        </p>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Institutional Demo"
      lead="A private showcase account on the top plan. No email, no password, nothing to cancel."
      below={
        <>
          Figures are real engine output on a paper portfolio. Informational research only,
          not investment advice. Demo accounts and anything entered in them are cleared
          after the event. Read the{" "}
          <Link href="/terms" className="text-aureus-gold hover:text-aureus-goldbright">Terms</Link>
          {" and "}
          <Link href="/privacy" className="text-aureus-gold hover:text-aureus-goldbright">Privacy Policy</Link>.
        </>
      }
    >
      <DemoEntry />

      <dl className="mt-9 border-t border-aureus-rule">
        {INCLUDED.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[6.5rem_1fr] gap-4 py-2.5 border-b border-aureus-rulesoft">
            <dt className="label-caps pt-0.5">{k}</dt>
            <dd className="text-[12.5px] text-aureus-soft leading-relaxed">{v}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-6 text-[12px] text-aureus-muted leading-relaxed">
        Seeded with a paper book and current analyses for{" "}
        <span className="font-mono-num text-aureus-soft">{SHOWCASE_TICKERS.join(", ")}</span>, so
        the first screen has something to say. Any other listed ticker runs live.
      </p>
    </AuthFrame>
  );
}
