"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { FlaskConical, Lock, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import FactorPanel from "@/components/quant/FactorPanel";
import RiskPanel from "@/components/quant/RiskPanel";
import MeanReversionPanel from "@/components/quant/MeanReversionPanel";
import { getQuantAccess, getQuantLab } from "@/lib/api";
import type { QuantLabReport } from "@/lib/api";

/**
 * The Advanced Quant Lab — Elite / Institutional only.
 *
 * Access is checked BOTH here and on the server (backend app/core/tiers.py).
 * The client check exists to render a useful upgrade prompt instead of an
 * error page; it is not the enforcement. The server returns 402 regardless
 * of what this component does, which is what makes the gate real rather
 * than a hidden nav link.
 */

type Tab = "factors" | "risk" | "reversion";

const TABS: { id: Tab; label: string; blurb: string }[] = [
  { id: "factors", label: "Factor Models", blurb: "Fama-French exposures and true alpha" },
  { id: "risk", label: "Risk & Simulation", blurb: "Monte Carlo, VaR, CVaR, beta stability" },
  { id: "reversion", label: "Mean Reversion", blurb: "Z-score, half-life, pairs, vol regime" },
];

function UpgradePrompt({ tier }: { tier: string }) {
  return (
    <Card>
      <CardContent className="p-10 text-center space-y-4 max-w-xl mx-auto">
        <div className="w-12 h-12 rounded-full bg-aureus-gold/10 flex items-center justify-center mx-auto">
          <Lock className="w-5 h-5 text-aureus-gold" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">The Quant Lab is an Elite feature</h2>
          <p className="text-sm text-aureus-muted mt-2 leading-relaxed">
            Factor modelling, Monte Carlo simulation, Value at Risk and statistical
            mean-reversion analysis are institutional research tools. Your current plan is{" "}
            <span className="text-aureus-text font-medium">{tier}</span>.
          </p>
        </div>
        <div className="text-left rounded-lg border border-aureus-rule p-4 space-y-2"
             style={{ background: "var(--bg)" }}>
          <p className="text-[11px] uppercase tracking-wider text-aureus-muted">What you get</p>
          <ul className="text-xs text-aureus-text space-y-1.5">
            <li>· Fama-French 3 and 5-factor exposures with significance testing</li>
            <li>· Monte Carlo return distributions from bootstrapped history</li>
            <li>· Value at Risk and expected shortfall at 1 and 10-day horizons</li>
            <li>· Rolling beta stability and drawdown analysis</li>
            <li>· Z-score deviation, reversion half-life, and pairs correlation</li>
          </ul>
        </div>
        <div className="flex gap-2 justify-center">
          <Link href="/upgrade?feature=quant-lab">
            <Button>Upgrade to Elite</Button>
          </Link>
          <Link href="/analysis">
            <Button variant="outline">Back to Analysis</Button>
          </Link>
        </div>
        <p className="text-[10px] text-aureus-muted">
          The three-pillar analysis — Fundamental, Technical and Sentiment — stays available on
          every plan, including yours.
        </p>
      </CardContent>
    </Card>
  );
}

function QuantLabInner() {
  const { data: session } = useSession();
  const params = useSearchParams();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";

  const [ticker, setTicker] = useState((params.get("ticker") ?? "AAPL").toUpperCase());
  const [input, setInput] = useState("");
  const [tab, setTab] = useState<Tab>("factors");

  const [access, setAccess] = useState<{ has: boolean; tier: string } | null>(null);
  const [report, setReport] = useState<QuantLabReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    getQuantAccess(userId)
      .then((a) => setAccess({ has: a.has_access, tier: a.tier }))
      .catch(() => setAccess({ has: false, tier: "sovereign" }));
  }, [userId]);

  const load = useCallback(async () => {
    if (!userId || !access?.has || !ticker) return;
    setLoading(true);
    setError(null);
    try {
      setReport(await getQuantLab(ticker, userId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Quant Lab request failed");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [ticker, userId, access?.has]);

  useEffect(() => { load(); }, [load]);

  if (!userId) {
    return (
      <Card><CardContent className="p-10 text-center text-sm text-aureus-muted">
        Sign in to use the Quant Lab.
      </CardContent></Card>
    );
  }
  if (access === null) {
    return (
      <Card><CardContent className="p-10 text-center text-sm text-aureus-muted">
        Checking access…
      </CardContent></Card>
    );
  }
  if (!access.has) return <UpgradePrompt tier={access.tier} />;

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <FlaskConical className="w-5 h-5 text-aureus-gold" strokeWidth={1.75} />
                <h1 className="text-2xl font-bold text-white tracking-tight">Quant Lab</h1>
                <span className="rounded bg-aureus-gold/10 border border-aureus-gold/40 px-2 py-0.5
                                 text-[10px] font-bold tracking-wider text-aureus-gold">
                  {access.tier.toUpperCase()}
                </span>
              </div>
              <p className="text-xs text-aureus-muted mt-1">
                Statistical research on <span className="text-aureus-text font-mono">{ticker}</span>
                {report && ` · ${report.observations} sessions · ${report.start_date} → ${report.end_date}`}
              </p>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (input.trim()) { setTicker(input.trim().toUpperCase()); setInput(""); }
              }}
              className="flex gap-2"
            >
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-aureus-muted" />
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ticker"
                  className="w-36 rounded-md border border-aureus-border pl-8 pr-3 py-1.5 text-sm text-white
                             placeholder:text-aureus-muted/50 focus:outline-none focus:border-aureus-gold"
                  style={{ background: "var(--bg)" }}
                />
              </div>
              <Button type="submit" size="sm" variant="outline">Run</Button>
            </form>
          </div>

          <div className="flex gap-1.5">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex-1 rounded-md border px-3 py-2 text-left transition-colors ${
                  tab === t.id
                    ? "border-aureus-gold bg-aureus-gold/10"
                    : "border-aureus-border hover:border-aureus-muted"
                }`}
              >
                <div className={`text-xs font-medium ${tab === t.id ? "text-aureus-gold" : "text-aureus-text"}`}>
                  {t.label}
                </div>
                <div className="text-[10px] text-aureus-muted">{t.blurb}</div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {loading && (
        <Card><CardContent className="p-16 text-center text-sm text-aureus-muted">
          Running factor regressions and simulations for {ticker}…
        </CardContent></Card>
      )}

      {error && !loading && (
        <Card><CardContent className="p-8 text-center space-y-3">
          <p className="text-sm text-aureus-red">{error}</p>
          <Button variant="outline" size="sm" onClick={load}>Retry</Button>
        </CardContent></Card>
      )}

      {report && !loading && (
        <>
          {report.notes.length > 0 && (
            <Card><CardContent className="p-3 space-y-1">
              {report.notes.map((n) => (
                <p key={n} className="text-[11px] text-aureus-gold">⚠ {n}</p>
              ))}
            </CardContent></Card>
          )}

          {tab === "factors" && (
            <div className="space-y-4">
              <FactorPanel model={report.factor_model_5} />
              <FactorPanel model={report.factor_model_3} />
            </div>
          )}
          {tab === "risk" && <RiskPanel report={report} />}
          {tab === "reversion" && <MeanReversionPanel report={report} />}

          <Card><CardContent className="p-4">
            <p className="text-[10px] text-aureus-muted leading-relaxed">{report.disclaimer}</p>
          </CardContent></Card>
        </>
      )}
    </div>
  );
}

export default function QuantLabPage() {
  // useSearchParams needs a Suspense boundary in the App Router, or the
  // whole route opts out of static rendering and Next fails the build.
  return (
    <Suspense fallback={
      <Card><CardContent className="p-16 text-center text-sm text-aureus-muted">
        Loading Quant Lab…
      </CardContent></Card>
    }>
      <QuantLabInner />
    </Suspense>
  );
}
