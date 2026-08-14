"use client";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { Zap, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TIER_TO_PRICE } from "@/lib/stripe";

interface Props {
  feature?:      string;
  requiredTier?: string;
  onClose?:      () => void;
}

// These are checked against what the backend actually enforces
// (db/migrations/008_tier_entitlements.sql). The previous list advertised
// live execution, direct Alpaca trading, "5 concurrent live agent
// strategies" and human-in-the-loop alerts — all four were removed from
// the product when agentic execution was deleted, and every one of them
// had zero implementing files. Do not add a line here without a limit or
// feature flag in subscription_tiers to back it.
const TIER_BENEFITS = {
  elite: [
    "200 full analyses per day (vs 15 free)",
    "The Quant Lab — factor models, Monte Carlo, VaR",
    "SEC filing-tone analysis and full news catalysts",
    "Real-time news feed (no 15-minute delay)",
    "50 backtests/day, 5 tickers, 10 years of history",
    "500 voice conversation minutes per month",
  ],
  institutional: [
    "Everything in Elite, uncapped",
    "Unlimited analyses, backtests and voice minutes",
    "10 years of factor history (vs 3)",
    "50,000-path Monte Carlo simulations (vs 10,000)",
    "Custom peer sets for relative-value work",
    "25 tickers per backtest, unlimited history",
  ],
};

export default function UpgradeModal({ feature, requiredTier = "elite", onClose }: Props) {
  const { data: session } = useSession();
  const [loading, setLoading] = useState<string | null>(null);

  const handleUpgrade = async (tier: "elite" | "institutional") => {
    setLoading(tier);
    try {
      const res = await fetch("/api/billing/checkout", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ tier }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (e) {
      console.error("Checkout failed:", e);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl border border-aureus-border p-6 space-y-6"
           style={{ background: "var(--surface)" }}
           onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-full bg-aureus-gold/10 border border-aureus-gold/30
                          flex items-center justify-center mx-auto">
            <Zap className="w-6 h-6 text-aureus-gold" />
          </div>
          <h2 className="text-white text-xl font-bold">
            {feature ? `Unlock ${feature}` : "Upgrade your plan"}
          </h2>
          <p className="text-aureus-muted text-sm">
            {feature
              ? `${feature} requires ${requiredTier === "institutional" ? "Institutional" : "Elite"} or above.`
              : "Access advanced features built for serious traders."}
          </p>
        </div>

        {/* Plans */}
        <div className="grid grid-cols-2 gap-4">
          {(["elite", "institutional"] as const).map((tier) => (
            <div key={tier}
                 className={`rounded-xl border p-4 space-y-3 ${
                   tier === requiredTier
                     ? "border-aureus-gold"
                     : "border-aureus-border"
                 }`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white font-bold capitalize">{tier}</div>
                  <div className="text-aureus-gold text-lg font-bold">
                    ${tier === "elite" ? "50" : "100"}
                    <span className="text-aureus-muted text-xs font-normal">/mo</span>
                  </div>
                </div>
                {tier === requiredTier && (
                  <span className="text-xs bg-aureus-gold/20 text-aureus-gold
                                   border border-aureus-gold/40 rounded px-2 py-0.5">
                    Recommended
                  </span>
                )}
              </div>

              <ul className="space-y-1.5">
                {TIER_BENEFITS[tier].map((benefit) => (
                  <li key={benefit} className="flex items-start gap-2 text-xs text-aureus-muted">
                    <Check className="w-3 h-3 text-aureus-green mt-0.5 flex-shrink-0" />
                    {benefit}
                  </li>
                ))}
              </ul>

              <Button
                onClick={() => handleUpgrade(tier)}
                disabled={loading !== null}
                variant={tier === requiredTier ? "default" : "outline"}
                className="w-full"
                size="sm"
              >
                {loading === tier ? "Redirecting..." : `Upgrade to ${tier}`}
              </Button>
            </div>
          ))}
        </div>

        <div className="text-center">
          <button onClick={onClose} className="text-xs text-aureus-muted hover:text-white transition-colors">
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
