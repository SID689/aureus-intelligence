"use client";
import { useSearchParams } from "next/navigation";
import UpgradeModal from "@/components/billing/UpgradeModal";
import { useRouter } from "next/navigation";
export default function UpgradePage() {
  const params = useSearchParams();
  const router = useRouter();
  return (
    <UpgradeModal
      feature={params.get("feature") ?? undefined}
      requiredTier={params.get("required_tier") ?? "elite"}
      onClose={() => router.back()}
    />
  );
}
