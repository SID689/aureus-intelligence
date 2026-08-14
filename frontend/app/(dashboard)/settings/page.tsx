"use client";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import UpgradeModal from "@/components/billing/UpgradeModal";
import LearningLevelCard from "@/components/dashboard/LearningLevelCard";
import PlanUsageCard from "@/components/account/PlanUsageCard";
import { TIER_FEATURES } from "@/types";
import type { TierName } from "@/types";
import { Check } from "lucide-react";

export default function SettingsPage() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const tier = (session?.user?.tier ?? "sovereign") as TierName;

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
              {TIER_FEATURES[tier].label}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Plan, limits and live usage — served from the database */}
      <PlanUsageCard />

      {/* Learning level */}
      <LearningLevelCard userId={userId} />

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
