"use client";
/**
 * Plans, from inside the app.
 *
 * A full page rather than a modal. Choosing a plan is a considered decision
 * made against a comparison table, and a table this wide does not belong in
 * a dialog. Arriving from a locked feature adds that feature’s case above
 * the table and highlights the plan that unlocks it.
 */
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import PricingMatrix from "@/components/billing/PricingMatrix";
import { ErrorNote, PageHeader } from "@/components/ui/primitives";
import { LoadingRegion, SkeletonPageHeader, SkeletonSheet, SkeletonTable } from "@/components/ui/Skeleton";
import { getEntitlements, getPlans } from "@/lib/api";
import type { Plan } from "@/lib/api";
import { TIER_LABEL, asTier, nextTier } from "@/lib/tiers";
import type { TierName } from "@/types";

const FEATURE_PITCH: Record<string, { title: string; minimum: TierName; lead: string; points: string[] }> = {
  leaderboard: {
    title: "The Hottest Stocks Leaderboard",
    minimum: "elite",
    lead: "The S&P 500, rescored every 15 minutes while the market is open by the same engine as your analysis page.",
    points: [
      "Every stock whose verified score clears the Strong Buy line, with its price, composite and primary catalyst.",
      "An alert the moment a new name enters: in the app while you are here, as a push notification when you are not.",
      "The names close to the line, and the exact test each one is still failing.",
      "Entry and exit rules published in full. No name on the board is chosen by hand.",
    ],
  },
  notifications: {
    title: "Strong Buy alerts",
    minimum: "elite",
    lead: "Know when a stock enters the Strong Buy board, whether or not the app is open.",
    points: [
      "In-app alerts, and push notifications to any browser you enable.",
      "At most one alert per stock every 72 hours, so a name hovering at the line cannot flood you.",
      "A full history behind the bell for anything you missed.",
    ],
  },
  voice: {
    title: "Voice",
    minimum: "elite",
    lead: "Talk through a position out loud, with the whole session carried as context.",
    points: [
      "Ask why a score moved, what the bear case rests on, or how a holding changes your exposure.",
      "Follow-up questions need no restating of which stock you meant.",
    ],
  },
  "quant-lab": {
    title: "The Quant Lab",
    minimum: "elite",
    lead: "Research statistics that do not belong in a single score.",
    points: [
      "Fama-French three and five-factor exposures with significance testing.",
      "Bootstrap Monte Carlo, value at risk and expected shortfall.",
      "Rolling beta stability and mean-reversion diagnostics.",
    ],
  },
};

function UpgradeInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";
  const feature = params.get("feature") ?? "";
  const pitch = FEATURE_PITCH[feature];

  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [current, setCurrent] = useState<TierName>(asTier(session?.user?.tier));
  const [busy, setBusy] = useState<TierName | "portal" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPlans().then((r) => setPlans(r.plans)).catch(() => setPlans([]));
  }, []);
  // The session tier is only as fresh as the last sign-in; the entitlement
  // endpoint is not.
  useEffect(() => {
    if (!userId) return;
    getEntitlements(userId).then((e) => setCurrent(asTier(e.tier))).catch(() => {});
  }, [userId]);

  const requested = params.get("required_tier");
  const highlight: TierName = pitch?.minimum ?? (requested ? asTier(requested) : nextTier(current));

  const post = async (url: string, body?: object) => {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (data.url) window.location.href = data.url;
    else setError(data.error ?? "That could not be opened. Try again in a moment.");
  };

  const checkout = async (tier: TierName) => {
    setBusy(tier); setError(null);
    try { await post("/api/billing/checkout", { tier }); } finally { setBusy(null); }
  };
  const portal = async () => {
    setBusy("portal"); setError(null);
    try { await post("/api/billing/portal"); } finally { setBusy(null); }
  };

  return (
    <div className="space-y-8">
      <button onClick={() => router.back()} className="text-[12.5px] touch:min-h-[44px] touch:px-1 -ml-1 text-aureus-muted hover:text-aureus-gold">Back</button>

      {pitch ? (
        <section className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-x-12 gap-y-6 border-b border-aureus-rule pb-8">
          <div>
            <p className="label-caps text-aureus-gold">{TIER_LABEL[pitch.minimum]} and above</p>
            <h1 className="font-display text-[34px] leading-tight text-aureus-text mt-3">{pitch.title}</h1>
            <p className="text-[14px] text-aureus-soft leading-relaxed mt-3 max-w-md">{pitch.lead}</p>
          </div>
          <ol className="border-t border-aureus-rule">
            {pitch.points.map((pt, i) => (
              <li key={pt} className="grid grid-cols-[2.25rem_1fr] py-3 border-b border-aureus-rulesoft text-[13.5px] text-aureus-soft leading-relaxed">
                <span className="font-mono-num text-[12px] text-aureus-gold pt-0.5">{String(i + 1).padStart(2, "0")}</span>
                <span>{pt}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : (
        <PageHeader
          title="Plans"
          lead={`You are on ${TIER_LABEL[current]}. The method is identical on every plan; paid plans raise ceilings and add written synthesis, the Quant Lab, the leaderboard and voice.`}
        />
      )}

      {error && <div className="max-w-xl"><ErrorNote>{error}</ErrorNote></div>}

      {plans === null ? (
        <LoadingRegion label="Loading plans"><SkeletonSheet title={false}><SkeletonTable rows={10} columns={[3, 2, 2, 2, 2]} /></SkeletonSheet></LoadingRegion>
      ) : (
        <PricingMatrix plans={plans} mode="app" currentTier={current} highlight={highlight} busy={busy} onCheckout={checkout} onPortal={portal} />
      )}
    </div>
  );
}

export default function UpgradePage() {
  return (
    <Suspense fallback={
      <LoadingRegion label="Loading plans" className="space-y-8">
        <SkeletonPageHeader />
        <SkeletonSheet title={false}><SkeletonTable rows={10} columns={[3, 2, 2, 2, 2]} /></SkeletonSheet>
      </LoadingRegion>
    }>
      <UpgradeInner />
    </Suspense>
  );
}
