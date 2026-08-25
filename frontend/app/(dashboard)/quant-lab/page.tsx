"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { FlaskConical, Lock, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CapsLabel, ErrorNote, Input, Note, PageHeader, Sheet,
} from "@/components/ui/primitives";
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
  { id: "factors", label: "Factor models", blurb: "Fama-French exposures and true alpha" },
  { id: "risk", label: "Risk & simulation", blurb: "Monte Carlo, VaR, CVaR, beta stability" },
  { id: "reversion", label: "Mean reversion", blurb: "Z-score, half-life, pairs, vol regime" },
];

function UpgradePrompt({ tier }: { tier: string }) {
  return (
    <Card>
      <CardContent className="p-10 text-center space-y-4 max-w-xl mx-auto">
        <div className="w-12 h-12 rounded-full bg-aureus-gold/10 flex items-center justify-center mx-auto">
          <Lock className="w-5 h-5 text-aureus-gold" />
        </div>
        <div>
          <h2 className="font-display text-xl text-aureus-text">The Quant Lab is an Elite feature</h2>
          <p className="text-sm text-aureus-muted mt-2 leading-relaxed">
            Factor modelling, Monte Carlo simulation, Value at Risk and statistical
            mean-reversion analysis are institutional research tools. Your current plan is{" "}
            <span className="text-aureus-text font-medium">{tier}</span>.
          </p>
        </div>
        <div className="text-left rounded-md border border-aureus-rule bg-aureus-ink p-4">
          <CapsLabel>What you get</CapsLabel>
          <ul className="text-[13px] text-aureus-soft mt-2.5">
            {[
              "Fama-French 3 and 5-factor exposures with significance testing",
              "Monte Carlo return distributions from bootstrapped history",
              "Value at Risk and expected shortfall at 1 and 10-day horizons",
              "Rolling beta stability and drawdown analysis",
              "Z-score deviation, reversion half-life, and pairs correlation",
            ].map((f, i) => (
              <li key={f} className={`py-2 ${i > 0 ? "border-t border-aureus-rulesoft" : ""}`}>{f}</li>
            ))}
          </ul>
        </div>
        <div className="flex gap-2 justify-center">
          <Link href="/upgrade?feature=quant-lab">
            <Button>Upgrade to Elite</Button>
          </Link>
          <Link href="/analysis">
            <Button variant="outline">Back to analysis</Button>
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
      <Card flat><CardContent className="py-16 text-center text-sm text-aureus-muted">
        Sign in to use the Quant Lab.
      </CardContent></Card>
    );
  }
  if (access === null) {
    return (
      <Card flat><CardContent className="py-16 text-center text-sm text-aureus-muted">
        Checking access…
      </CardContent></Card>
    );
  }
  if (!access.has) return <UpgradePrompt tier={access.tier} />;

  return (
    <div className="space-y-5">
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <FlaskConical className="w-5 h-5 text-aureus-gold" strokeWidth={1.75} />
            Quant Lab
            <Badge>{access.tier}</Badge>
          </span>
        }
        lead={
          <>
            Statistical research on <span className="text-aureus-soft font-mono-num">{ticker}</span>
            {report && ` · ${report.observations} sessions · ${report.start_date} → ${report.end_date}`}
          </>
        }
        actions={
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (input.trim()) { setTicker(input.trim().toUpperCase()); setInput(""); }
            }}
            className="flex gap-2"
          >
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-aureus-muted pointer-events-none" />
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ticker"
                className="w-36 pl-8 py-1.5"
                spellCheck={false}
              />
            </div>
            <Button type="submit" size="sm" variant="outline">Run</Button>
          </form>
        }
      />

      {/* Tabs carry a one-line blurb because these three are not
          self-explanatory the way "Overview / Details" would be. */}
      <div className="grid sm:grid-cols-3 gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-md border px-3.5 py-2.5 text-left transition-colors ${
              tab === t.id
                ? "border-aureus-gold bg-aureus-gold/[0.08]"
                : "border-aureus-rule hover:border-aureus-rulestrong hover:bg-aureus-panellift"
            }`}
          >
            <div className={`text-[13px] font-medium ${tab === t.id ? "text-aureus-gold" : "text-aureus-text"}`}>
              {t.label}
            </div>
            <div className="text-[11px] text-aureus-muted mt-0.5">{t.blurb}</div>
          </button>
        ))}
      </div>

      {loading && (
        <Card flat><CardContent className="py-16 text-center text-sm text-aureus-muted">
          Running factor regressions and simulations for {ticker}…
        </CardContent></Card>
      )}

      {error && !loading && (
        <div className="space-y-3">
          <ErrorNote>{error}</ErrorNote>
          <Button variant="outline" size="sm" onClick={load}>Retry</Button>
        </div>
      )}

      {report && !loading && (
        <>
          {report.notes.length > 0 && (
            <Sheet className="px-4 py-3 border-l-2 border-l-aureus-amber space-y-1">
              {report.notes.map((n) => (
                <p key={n} className="text-[12px] text-aureus-amber leading-relaxed">{n}</p>
              ))}
            </Sheet>
          )}

          {tab === "factors" && (
            <div className="space-y-4">
              <FactorPanel model={report.factor_model_5} />
              <FactorPanel model={report.factor_model_3} />
            </div>
          )}
          {tab === "risk" && <RiskPanel report={report} />}
          {tab === "reversion" && <MeanReversionPanel report={report} />}

          <Note>{report.disclaimer}</Note>
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
