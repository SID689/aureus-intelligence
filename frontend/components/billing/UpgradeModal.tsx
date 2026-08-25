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

// Checked against what the backend actually enforces
// (db/migrations/008-010). An earlier version of this list advertised
// live execution, direct Alpaca trading, "5 concurrent live agent
// strategies" and human-in-the-loop alerts — all four were removed from
// the product and had zero implementing files. Do not add a line here
// without a limit or feature flag in subscription_tiers to back it.
const TIER_BENEFITS = {
  elite: [
    "Claude-powered analysis (Haiku, Sonnet on deep dives)",
    "25,000 credits/month — ~1,600 AI analyses",
    "Real-time market data via Polygon (no 15-min delay)",
    "The Quant Lab — factor models, Monte Carlo, VaR",
    "5-minute cache, priority queue, 3 concurrent jobs",
    "300 voice minutes + 2 programmatic API keys",
  ],
  institutional: [
    "Everything in Elite, uncapped",
    "Claude Sonnet standard, Opus on deep dives",
    "150,000 credits/month — ~2,500 Sonnet analyses",
    "Every premium data source: Polygon Advanced, Finnhub, X, Reddit",
    "60-second cache, top queue priority, 10 concurrent jobs",
    "10 years of factor history, 50,000-path simulations",
  ],
};

const TIER_PRICE: Record<"elite" | "institutional", string> = {
  elite: "99",
  institutional: "499",
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
      <div className="w-full max-w-2xl rounded-2xl border border-aureus-rule p-6 space-y-6"
           style={{ background: "var(--panel)" }}
           onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-full bg-aureus-gold/10 border border-aureus-gold/30
                          flex items-center justify-center mx-auto">
            <Zap className="w-6 h-6 text-aureus-gold" />
          </div>
          <h2 className="text-aureus-text text-xl font-bold">
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
                     : "border-aureus-rule"
                 }`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-aureus-text font-bold capitalize">{tier}</div>
                  <div className="text-aureus-gold text-lg font-bold">
                    ${TIER_PRICE[tier]}
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
                    <Check className="w-3 h-3 text-aureus-verdigris mt-0.5 flex-shrink-0" />
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
          <button onClick={onClose} className="text-xs text-aureus-muted hover:text-aureus-text transition-colors">
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
