"use client";
/**
 * The plans, as a comparison matrix.
 *
 * Four identical boxes with a checkmark list each make the reader do the
 * comparison in their head. A matrix does it for them: one row per limit,
 * one column per plan, the difference visible as a figure changing along a
 * row.
 *
 * Every cell is rendered from GET /api/v1/account/plans, the same plan
 * records the backend enforces. Nothing here is a hand-typed benefit, so
 * the page cannot advertise a limit the product does not apply. Only the
 * one-line positioning under each price is copy.
 */
import Link from "next/link";
import { Fragment } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { TIER_LABEL, asTier, tierRank } from "@/lib/tiers";
import type { Plan } from "@/lib/api";
import type { TierName } from "@/types";

type Cell = string | boolean;
interface Row { label: string; note?: string; value: (p: Plan) => Cell }

const MODEL: Record<string, string> = { "claude-haiku": "Claude Haiku", "claude-sonnet": "Claude Sonnet", "claude-opus": "Claude Opus" };

const perDay = (n: number | null) => (n == null ? "Unlimited" : `${n.toLocaleString()} a day`);
const amount = (n: number | null, unit = "") => (n == null ? "Unlimited" : `${n.toLocaleString()}${unit}`);

const GROUPS: { label: string; rows: Row[] }[] = [
  {
    label: "Analysis",
    rows: [
      { label: "Full three-pillar analyses", value: (p) => perDay(p.limits.analysis_requests_per_day) },
      { label: "Catalyst timeline", value: () => true },
      {
        label: "Written synthesis",
        note: "Bull and bear cases edited by a language model",
        value: (p) => p.quality.llm_model_default
          ? `${MODEL[p.quality.llm_model_default] ?? p.quality.llm_model_default}${p.quality.llm_model_deep ? `, ${(MODEL[p.quality.llm_model_deep] ?? p.quality.llm_model_deep).replace("Claude ", "")} for deep dives` : ""}`
          : false,
      },
      { label: "AI credits each month", value: (p) => (p.limits.monthly_credits > 0 ? p.limits.monthly_credits.toLocaleString() : false) },
      { label: "SEC filing tone", value: (p) => !!p.features.sec_filing_tone },
      { label: "Sentiment catalysts shown", value: (p) => (p.limits.sentiment_catalysts == null ? "All" : `Top ${p.limits.sentiment_catalysts}`) },
    ],
  },
  {
    label: "Data",
    rows: [
      {
        label: "Market data",
        value: (p) => (p.quality.market_data_providers.some((m) => m.startsWith("polygon")) ? "Real-time" : "Delayed"),
      },
      {
        label: "News feed",
        value: (p) => {
          const s = p.limits.news_feed_delay_seconds;
          return s === 0 ? "Real-time" : s < 120 ? `${s} s delay` : `${Math.round(s / 60)} min delay`;
        },
      },
      {
        label: "Refresh interval",
        note: "How long a computed result is reused",
        value: (p) => {
          const s = p.limits.cache_ttl_seconds;
          return s < 120 ? `${s} s` : `${Math.round(s / 60)} min`;
        },
      },
    ],
  },
  {
    label: "Research",
    rows: [
      { label: "Backtests", value: (p) => perDay(p.limits.backtests_per_day) },
      { label: "Tickers per backtest", value: (p) => amount(p.limits.backtest_tickers) },
      { label: "Backtest history", value: (p) => (p.limits.backtest_years == null ? "Full history" : `${p.limits.backtest_years} years`) },
      {
        label: "Quant Lab",
        note: "Fama-French factors, Monte Carlo, VaR",
        value: (p) => (p.features.quant_lab
          ? `${p.limits.quant_history_years ?? "Full"} yr history, ${(p.limits.quant_monte_carlo_paths ?? 0).toLocaleString()} paths`
          : false),
      },
      { label: "Hottest Stocks leaderboard and alerts", value: (p) => !!p.features.leaderboard },
      {
        label: "Voice",
        value: (p) => {
          const m = p.limits.voice_minutes_per_month;
          return m === 0 ? false : m == null ? "Unlimited" : `${m.toLocaleString()} min a month`;
        },
      },
    ],
  },
  {
    label: "Portfolio and access",
    rows: [
      { label: "Portfolios", value: (p) => amount(p.limits.portfolios) },
      { label: "Positions", value: (p) => amount(p.limits.portfolio_holdings) },
      { label: "Concurrent jobs", value: (p) => String(p.limits.max_concurrent_jobs) },
      { label: "API keys", value: (p) => (p.limits.api_keys_allowed > 0 ? String(p.limits.api_keys_allowed) : false) },
      { label: "Curriculum and daily games", value: () => true },
    ],
  },
];

const POSITIONING: Record<TierName, string> = {
  sovereign: "The complete method at a daily ceiling.",
  plus: "More analyses and written synthesis for regular investors.",
  elite: "The full research desk: Quant Lab, leaderboard and voice.",
  institutional: "No ceilings, the strongest models, every data source.",
};

function CellValue({ v }: { v: Cell }) {
  if (v === true) return <span className="text-aureus-soft">Included</span>;
  if (v === false) return <span className="text-aureus-muted" aria-label="Not included">–</span>;
  return <span className="text-aureus-text">{v}</span>;
}

export interface PricingMatrixProps {
  plans: Plan[];
  mode: "public" | "app";
  currentTier?: TierName | null;
  highlight?: TierName | null;
  busy?: TierName | "portal" | null;
  onCheckout?: (tier: TierName) => void;
  onPortal?: () => void;
}

export default function PricingMatrix({ plans, mode, currentTier, highlight, busy, onCheckout, onPortal }: PricingMatrixProps) {
  const ordered = [...plans].sort((a, b) => tierRank(a.tier) - tierRank(b.tier));

  const action = (p: Plan) => {
    const tier = asTier(p.tier);
    if (mode === "public") {
      return (
        <Link href={tier === "sovereign" ? "/sign-up" : `/sign-up?plan=${tier}`} className="block">
          <Button className="w-full" size="sm" variant={tier === highlight ? "default" : "outline"}>
            {tier === "sovereign" ? "Start free" : `Choose ${TIER_LABEL[tier]}`}
          </Button>
        </Link>
      );
    }
    const current = asTier(currentTier);
    if (tier === current) return <p className="h-7 flex items-center label-caps text-aureus-gold">Your plan</p>;
    if (tier === "sovereign") return <p className="h-7 flex items-center text-[12px] text-aureus-muted font-sans">Free</p>;
    if (current !== "sovereign") {
      // A paid subscriber changes plan in the billing portal. A second
      // checkout would open a second subscription alongside the first.
      return (
        <Button className="w-full" size="sm" variant="outline" onClick={onPortal} disabled={busy != null}>
          {busy === "portal" ? "Opening" : tierRank(tier) > tierRank(current) ? "Upgrade in billing" : "Change in billing"}
        </Button>
      );
    }
    return (
      <Button className="w-full" size="sm" variant={tier === highlight ? "default" : "outline"} onClick={() => onCheckout?.(tier)} disabled={busy != null}>
        {busy === tier ? "Opening checkout" : `Upgrade to ${TIER_LABEL[tier]}`}
      </Button>
    );
  };

  if (ordered.length === 0) {
    return (
      <div className="border border-aureus-rule bg-aureus-panel px-5 py-6 text-[13px] text-aureus-muted">
        Plan details are unavailable right now. The free plan needs no card, and{" "}
        <Link href="/sign-up" className="text-aureus-gold hover:underline">you can open an account</Link> and compare plans inside.
      </div>
    );
  }

  return (
    <div>
      <div className="border border-aureus-rule bg-aureus-panel overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse text-left">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 w-[15rem] bg-aureus-panel align-bottom px-5 pb-4 border-b border-aureus-rule font-normal">
                <span className="label-caps">Monthly, in US dollars</span>
              </th>
              {ordered.map((p) => {
                const tier = asTier(p.tier);
                const hl = tier === highlight;
                return (
                  <th key={p.tier} scope="col" className={cn("align-top px-5 pb-4 border-b border-l border-aureus-rule font-normal", hl && "bg-aureus-panellift")}>
                    <div className={cn("h-0.5 mb-5", hl ? "bg-aureus-gold" : "bg-transparent")} />
                    <div className="font-display text-[22px] leading-none text-aureus-text">{p.display_name}</div>
                    <div className="mt-3 flex items-baseline gap-1.5">
                      <span className="font-mono-num text-[30px] leading-none text-aureus-text">${(p.price_cents / 100).toFixed(0)}</span>
                      <span className="text-[12px] text-aureus-muted font-sans">{p.price_cents === 0 ? "free" : "a month"}</span>
                    </div>
                    <p className="text-[12.5px] text-aureus-muted leading-snug mt-3 min-h-[2.6rem] font-sans">{POSITIONING[tier]}</p>
                    <div className="mt-4">{action(p)}</div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {GROUPS.map((g) => (
              <Fragment key={g.label}>
                <tr>
                  <th scope="colgroup" colSpan={ordered.length + 1} className="sticky left-0 bg-aureus-panel px-5 pt-6 pb-2 text-left font-normal">
                    <span className="label-caps text-aureus-gold">{g.label}</span>
                  </th>
                </tr>
                {g.rows.map((r) => (
                  <tr key={r.label} className="border-t border-aureus-rulesoft">
                    <th scope="row" className="sticky left-0 z-10 bg-aureus-panel px-5 py-2.5 text-[13px] font-normal text-aureus-soft">
                      {r.label}
                      {r.note && <span className="block text-[11px] text-aureus-muted mt-0.5">{r.note}</span>}
                    </th>
                    {ordered.map((p) => (
                      <td key={p.tier} className={cn("px-5 py-2.5 border-l border-aureus-rulesoft text-[13px]", asTier(p.tier) === highlight && "bg-aureus-panellift")}>
                        <CellValue v={r.value(p)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11.5px] text-aureus-muted mt-3 leading-relaxed max-w-3xl">
        Read from the same plan records the platform enforces. Paid plans renew monthly until cancelled, and cancelling keeps the
        plan until the end of the paid period. See the <Link href="/terms#billing" className="text-aureus-soft underline underline-offset-2">Terms of Service</Link>.
      </p>
    </div>
  );
}
