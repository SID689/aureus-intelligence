"use client";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataRow, PageHeader, RuledLabel, Sheet } from "@/components/ui/primitives";
import LearningLevelCard from "@/components/dashboard/LearningLevelCard";
import PlanUsageCard from "@/components/account/PlanUsageCard";
import { TIER_LABEL, asTier, meetsTier } from "@/lib/tiers";
import { LEGAL } from "@/lib/legal";

export default function SettingsPage() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";
  const tier = asTier(session?.user?.tier);
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);

  const openPortal = async () => {
    setPortalLoading(true);
    setPortalError(null);
    try {
      const res = await fetch("/api/billing/portal", { method: "POST" });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
      else setPortalError(data.error ?? "The billing portal is unavailable right now.");
    } catch {
      setPortalError("The billing portal is unavailable right now.");
    } finally {
      setPortalLoading(false);
    }
  };

  return (
    <div className="space-y-8 max-w-3xl">
      <PageHeader title="Settings" lead="Your account, plan, billing and learning level." />

      <section>
        <RuledLabel>Account</RuledLabel>
        <div className="mt-2">
          <DataRow first label="Email" value={<span className="font-sans text-aureus-text">{session?.user?.email}</span>} />
          <DataRow label="Account ID" value={<span className="text-[12px] text-aureus-muted">{session?.user?.id}</span>} />
          <DataRow
            label="Plan"
            value={<Badge variant={tier === "institutional" ? "institutional" : tier === "elite" ? "default" : "muted"}>{TIER_LABEL[tier]}</Badge>}
          />
        </div>
      </section>

      <PlanUsageCard />

      <LearningLevelCard userId={userId} />

      <section>
        <RuledLabel>Billing</RuledLabel>
        <Sheet className="mt-3 p-5">
          {meetsTier(tier, "plus") ? (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-[13px] text-aureus-muted max-w-md leading-relaxed">
                Invoices, payment method and cancellation are handled in the Stripe billing portal. Cancelling keeps your
                plan until the end of the period you have paid for.
              </p>
              <Button variant="outline" onClick={openPortal} disabled={portalLoading}>
                {portalLoading ? "Opening" : "Open billing portal"}
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-[13px] text-aureus-muted max-w-md leading-relaxed">
                You are on the free plan, so there is nothing to bill. Plus starts at $12 a month.
              </p>
              <Link href="/upgrade"><Button variant="outline">Compare plans</Button></Link>
            </div>
          )}
          {portalError && <p className="text-[12px] text-aureus-crimson mt-3">{portalError}</p>}
        </Sheet>
      </section>

      <section>
        <RuledLabel>Legal and privacy</RuledLabel>
        <div className="mt-2">
          <DataRow first label={<Link href="/terms" className="hover:text-aureus-gold">Terms of Service</Link>} value="" />
          <DataRow label={<Link href="/privacy" className="hover:text-aureus-gold">Privacy Policy</Link>} value="" />
          <DataRow
            label="Access or delete your data"
            sub="Write from the email on this account and we will respond within the time the law requires."
            value={<a href={`mailto:${LEGAL.contact.privacy}`} className="font-sans text-[12.5px] text-aureus-gold hover:underline">{LEGAL.contact.privacy}</a>}
          />
        </div>
      </section>
    </div>
  );
}
