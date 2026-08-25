"use client";
/**
 * Moved under (dashboard). The URL is unchanged — parenthesised segments
 * are route groups, not path segments — but two things were broken while
 * it sat at the top level:
 *
 *   · UpgradeModal calls useSession(), and SessionProvider is mounted by
 *     the (dashboard) layout. Outside that tree the page threw
 *     "`useSession` must be wrapped in a <SessionProvider />" — so the
 *     Upgrade link in the sidebar, the one a Sovereign user is most
 *     likely to click, crashed for every user who clicked it.
 *   · useSearchParams() without a Suspense boundary fails the production
 *     build.
 *
 * Both are fixed by living here and by the boundary below.
 */
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import UpgradeModal from "@/components/billing/UpgradeModal";

function UpgradeInner() {
  const params = useSearchParams();
  const router = useRouter();
  return (
    <UpgradeModal
      feature={params.get("feature") ?? undefined}
      requiredTier={params.get("required_tier") ?? "elite"}
      // back() rather than push("/"): arriving here from Quant Lab should
      // return you to Quant Lab, not dump you on the dashboard.
      onClose={() => router.back()}
    />
  );
}

export default function UpgradePage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-sm text-aureus-muted">Loading plans…</div>}>
      <UpgradeInner />
    </Suspense>
  );
}
