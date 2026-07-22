"use client";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import UpgradeModal from "@/components/billing/UpgradeModal";
import { TIER_FEATURES } from "@/types";
import type { TierName } from "@/types";
import { Check, X } from "lucide-react";

export default function SettingsPage() {
  const { data: session } = useSession();
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const tier = (session?.user?.tier ?? "sovereign") as TierName;
  const features = TIER_FEATURES[tier];

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const res  = await fetch("/api/billing/portal", { method: "POST" });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (e) {
      console.error(e);
    } finally {
      setPortalLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {showUpgrade && <UpgradeModal onClose={() => setShowUpgrade(false)} />}

      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-aureus-muted text-sm mt-0.5">Account, billing, and preferences</p>
      </div>

      {/* Account info */}
      <Card>
        <CardHeader><CardTitle>Account</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-aureus-muted">Email</span>
            <span className="text-white">{session?.user?.email}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-aureus-muted">User ID</span>
            <span className="text-white font-mono text-xs">{session?.user?.id}</span>
          </div>
          <div className="flex justify-between text-sm items-center">
            <span className="text-aureus-muted">Subscription Tier</span>
            <Badge variant={tier === "institutional" ? "institutional" : tier === "elite" ? "default" : "muted"}>
              {features.label}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Current plan features */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Plan Features</CardTitle>
            {tier !== "institutional" && (
              <Button size="sm" onClick={() => setShowUpgrade(true)}>Upgrade</Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {[
            { label: "Daily Analysis Requests", value: features.maxAnalysisPerDay == null ? "Unlimited" : String(features.maxAnalysisPerDay), enabled: true },
            { label: "Voice Minutes / Month",   value: features.voiceMinutes == null ? "Unlimited" : features.voiceMinutes === 0 ? "Not included" : `${features.voiceMinutes} min`, enabled: features.voiceMinutes !== 0 },
            { label: "Live Execution",          value: features.liveExecution ? "Enabled" : "Paper only",     enabled: features.liveExecution },
            { label: "Real-Time News",          value: features.realtimeNews ? "Enabled" : "15-min delayed",  enabled: features.realtimeNews },
            { label: "Concurrent Strategies",   value: features.concurrentStrategies == null ? "Unlimited" : features.concurrentStrategies === 0 ? "Not included" : String(features.concurrentStrategies), enabled: (features.concurrentStrategies ?? 0) > 0 },
          ].map(({ label, value, enabled }) => (
            <div key={label} className="flex items-center justify-between text-sm py-1.5 border-b border-aureus-border/50 last:border-0">
              <div className="flex items-center gap-2 text-aureus-muted">
                {enabled
                  ? <Check className="w-3.5 h-3.5 text-aureus-green" />
                  : <X     className="w-3.5 h-3.5 text-aureus-red"   />}
                {label}
              </div>
              <span className={enabled ? "text-white" : "text-aureus-muted"}>{value}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Billing management */}
      {tier !== "sovereign" && (
        <Card>
          <CardHeader><CardTitle>Billing</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-aureus-muted text-sm">
              Manage your subscription, invoices, and payment methods through the Stripe billing portal.
            </p>
            <Button variant="outline" onClick={openPortal} disabled={portalLoading}>
              {portalLoading ? "Redirecting..." : "Open Billing Portal"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
