"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getCredits, getEntitlements } from "@/lib/api";
import { SkeletonLines, SkeletonSheet } from "@/components/ui/Skeleton";
import { TIER_LABEL, nextTier } from "@/lib/tiers";
import type { AccountEntitlements, CreditBalance, UsageBlock } from "@/lib/api";

/**
 * The user's plan, what it includes, and how much they've used.
 *
 * Every number here comes from GET /api/v1/account/entitlements, which
 * reads subscription_tiers directly. Nothing is hardcoded, deliberately:
 * a limit written into the UI is a limit that goes stale the first time
 * someone edits a plan, and this app already shipped a pricing modal
 * advertising four features that had been deleted from the product.
 */

function UsageBar({ label, u }: { label: string; u: UsageBlock }) {
  const pct = u.unlimited || !u.limit ? 0 : Math.min(100, (u.used / u.limit) * 100);
  const tone = u.exceeded ? "var(--crimson)" : pct >= 80 ? "var(--gold)" : "var(--emerald)";

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-aureus-text">{label}</span>
        <span className="text-[11px] font-mono text-aureus-muted">
          {u.unlimited ? (
            <span className="text-aureus-emerald">Unlimited</span>
          ) : (
            <>
              <span className={u.exceeded ? "text-aureus-crimson" : "text-aureus-text"}>
                {u.used % 1 === 0 ? u.used.toFixed(0) : u.used.toFixed(1)}
              </span>
              {" / "}{u.limit} {u.unit}
            </>
          )}
        </span>
      </div>
      {!u.unlimited && (
        <div className="h-1.5 bg-aureus-rule overflow-hidden">
          <div className="h-full transition-all"
               style={{ width: `${pct}%`, background: tone }} />
        </div>
      )}
      <div className="text-[10px] text-aureus-muted">
        {u.unlimited ? "No cap on this plan" : `${u.remaining ?? 0} remaining · ${u.resets}`}
      </div>
    </div>
  );
}

function Limit({ label, value, suffix = "" }: { label: string; value: number | null; suffix?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-[11px] py-1">
      <span className="text-aureus-muted">{label}</span>
      <span className="font-mono text-aureus-text">
        {value === null ? "Unlimited" : `${value.toLocaleString()}${suffix}`}
      </span>
    </div>
  );
}

export default function PlanUsageCard() {
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const [data, setData] = useState<AccountEntitlements | null>(null);
  const [credits, setCredits] = useState<CreditBalance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    getEntitlements(userId)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load plan"));
    getCredits(userId).then((c) => setCredits(c.balance)).catch(() => setCredits(null));
  }, [userId]);

  if (error) {
    return (
      <Card><CardContent className="p-4 text-xs text-aureus-crimson">{error}</CardContent></Card>
    );
  }
  if (!data) {
    return (
      <SkeletonSheet><SkeletonLines lines={6} /></SkeletonSheet>
    );
  }

  const f = data.features;
  const l = data.limits;
  const upgradeTo = data.tier === "institutional" ? null : nextTier(data.tier);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Plan &amp; Usage</CardTitle>
        <span className="rounded-sm px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] font-mono-num
                         border border-aureus-gold/40 bg-aureus-gold/10 text-aureus-gold">
          {data.display_name.toUpperCase()}
          {data.price_cents > 0 && ` · $${(data.price_cents / 100).toFixed(0)}/mo`}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Credits are the real spend ceiling — the request counters below
            are a secondary abuse guard. Shown first for that reason. */}
        {credits && l.monthly_credits > 0 && (
          <div className="rounded-sm border border-aureus-gold/30 p-3 space-y-1.5"
               style={{ background: "var(--ink)" }}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs text-aureus-gold font-medium">AI Credits</span>
              <span className="text-[11px] font-mono text-aureus-text">
                {credits.remaining.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                <span className="text-aureus-muted"> / {l.monthly_credits.toLocaleString()}</span>
              </span>
            </div>
            <div className="h-1.5 bg-aureus-rule overflow-hidden">
              <div className="h-full"
                   style={{
                     width: `${Math.max(0, Math.min(100, (credits.remaining / l.monthly_credits) * 100))}%`,
                     background: credits.remaining / l.monthly_credits < 0.15 ? "var(--crimson)" : "var(--gold)",
                   }} />
            </div>
            <div className="text-[10px] text-aureus-muted">
              Covers ${credits.usd_value_remaining.toFixed(2)} of AI analysis and voice ·
              resets monthly
            </div>
            {data.quality.llm_model_default && (
              <div className="text-[10px] text-aureus-muted">
                Model: <span className="text-aureus-text">{data.quality.llm_model_default}</span>
                {data.quality.llm_model_deep && (
                  <> · deep dives on <span className="text-aureus-text">{data.quality.llm_model_deep}</span></>
                )}
              </div>
            )}
          </div>
        )}

        <div className="space-y-3">
          <UsageBar label="Analyses" u={data.usage.analysis} />
          <UsageBar label="Backtests" u={data.usage.backtest} />
          <UsageBar label="Voice" u={data.usage.voice} />
        </div>

        <div className="pt-3 border-t border-aureus-rule">
          <h4 className="text-[10px] uppercase tracking-wider text-aureus-muted mb-1.5">
            Plan limits
          </h4>
          <Limit label="Backtest tickers per run" value={l.backtest_tickers} />
          <Limit label="Backtest history" value={l.backtest_years} suffix=" yrs" />
          <Limit label="Portfolio positions" value={l.portfolio_holdings} />
          <Limit label="Data freshness (cache)" value={l.cache_ttl_seconds / 60} suffix=" min" />
          <Limit label="Concurrent jobs" value={l.max_concurrent_jobs} />
          <Limit label="API keys" value={l.api_keys_allowed} />
          <Limit label="News feed delay"
                 value={l.news_feed_delay_seconds === 0 ? null : l.news_feed_delay_seconds / 60}
                 suffix=" min" />
          {l.news_feed_delay_seconds === 0 && (
            <p className="text-[10px] text-aureus-emerald -mt-1">Real-time, no delay</p>
          )}
          {f.quant_lab && (
            <>
              <Limit label="Quant Lab history" value={l.quant_history_years} suffix=" yrs" />
              <Limit label="Monte Carlo paths" value={l.quant_monte_carlo_paths} />
            </>
          )}
        </div>

        <div className="pt-3 border-t border-aureus-rule space-y-1">
          <h4 className="text-[10px] uppercase tracking-wider text-aureus-muted mb-1.5">
            Features
          </h4>
          {[
            ["Three-pillar analysis", true],
            ["Education & games", true],
            ["Strategy backtesting", true],
            ["Quant Lab", !!f.quant_lab],
            ["SEC filing tone", !!f.sec_filing_tone],
            ["Custom peer sets", !!f.quant_custom_peers],
            ["Voice interface", (l.voice_minutes_per_month ?? 1) !== 0],
          ].map(([label, on]) => (
            <div key={String(label)} className="flex items-baseline justify-between gap-2 text-[11px] py-0.5">
              <span className={on ? "text-aureus-text" : "text-aureus-muted"}>{label}</span>
              <span className={on ? "label-caps text-[9px] text-aureus-emerald" : "label-caps text-[9px]"}>{on ? "Included" : "Not in plan"}</span>
            </div>
          ))}
        </div>

        {upgradeTo && (
          <Link href="/upgrade" className="block">
            <Button className="w-full" size="sm" variant={data.tier === "sovereign" ? "default" : "outline"}>
              Compare with {TIER_LABEL[upgradeTo]}
            </Button>
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
