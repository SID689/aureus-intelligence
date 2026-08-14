"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { Infinity as InfinityIcon, Lock, Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getEntitlements } from "@/lib/api";
import type { AccountEntitlements, UsageBlock } from "@/lib/api";

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
  const tone = u.exceeded ? "#ef4444" : pct >= 80 ? "#d4a843" : "#22c55e";

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-aureus-text">{label}</span>
        <span className="text-[11px] font-mono text-aureus-muted">
          {u.unlimited ? (
            <span className="flex items-center gap-1 text-aureus-green">
              <InfinityIcon className="w-3 h-3" /> unlimited
            </span>
          ) : (
            <>
              <span className={u.exceeded ? "text-aureus-red" : "text-white"}>
                {u.used % 1 === 0 ? u.used.toFixed(0) : u.used.toFixed(1)}
              </span>
              {" / "}{u.limit} {u.unit}
            </>
          )}
        </span>
      </div>
      {!u.unlimited && (
        <div className="h-1.5 rounded-full bg-aureus-rule overflow-hidden">
          <div className="h-full rounded-full transition-all"
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
      <span className="font-mono text-white">
        {value === null ? "Unlimited" : `${value.toLocaleString()}${suffix}`}
      </span>
    </div>
  );
}

export default function PlanUsageCard() {
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const [data, setData] = useState<AccountEntitlements | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    getEntitlements(userId)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load plan"));
  }, [userId]);

  if (error) {
    return (
      <Card><CardContent className="p-4 text-xs text-aureus-red">{error}</CardContent></Card>
    );
  }
  if (!data) {
    return (
      <Card><CardContent className="p-4 text-xs text-aureus-muted">Loading plan…</CardContent></Card>
    );
  }

  const f = data.features;
  const l = data.limits;
  const isFree = data.tier === "sovereign";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Plan &amp; Usage</CardTitle>
        <span className="rounded px-2 py-0.5 text-[10px] font-bold tracking-wider
                         border border-aureus-gold/40 bg-aureus-gold/10 text-aureus-gold">
          {data.display_name.toUpperCase()}
          {data.price_cents > 0 && ` · $${(data.price_cents / 100).toFixed(0)}/mo`}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
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
          <Limit label="News feed delay"
                 value={l.news_feed_delay_seconds === 0 ? null : l.news_feed_delay_seconds / 60}
                 suffix=" min" />
          {l.news_feed_delay_seconds === 0 && (
            <p className="text-[10px] text-aureus-green -mt-1">Real-time — no delay</p>
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
            <div key={String(label)} className="flex items-center gap-2 text-[11px]">
              {on
                ? <Check className="w-3 h-3 text-aureus-green flex-shrink-0" />
                : <Lock className="w-3 h-3 text-aureus-muted flex-shrink-0" />}
              <span className={on ? "text-aureus-text" : "text-aureus-muted/60"}>{label}</span>
            </div>
          ))}
        </div>

        {isFree && (
          <Link href="/upgrade" className="block">
            <Button className="w-full" size="sm">Upgrade to Elite</Button>
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
