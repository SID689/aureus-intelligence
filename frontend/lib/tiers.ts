// lib/tiers.ts — plan ordering for the frontend.
//
// Mirrors backend/app/core/entitlements.py _TIER_ORDER. Every "is this plan
// high enough" check in the UI goes through here instead of comparing a tier
// to the string "sovereign", which silently stopped being the only free-ish
// answer the day a fourth plan was added.
//
// Display and routing only. The backend enforces every limit on its own.
import type { TierName } from "@/types";

export const TIER_ORDER: TierName[] = ["sovereign", "plus", "elite", "institutional"];

export const TIER_LABEL: Record<TierName, string> = {
  sovereign: "Sovereign",
  plus: "Plus",
  elite: "Elite",
  institutional: "Institutional",
};

export function tierRank(tier?: string | null): number {
  const i = TIER_ORDER.indexOf((tier ?? "sovereign").toLowerCase() as TierName);
  return i < 0 ? 0 : i;
}

export function asTier(tier?: string | null): TierName {
  return TIER_ORDER[tierRank(tier)];
}

export function meetsTier(tier: string | null | undefined, minimum: TierName): boolean {
  return tierRank(tier) >= tierRank(minimum);
}

/** One step up: what a quota message should offer. */
export function nextTier(tier?: string | null): TierName {
  return TIER_ORDER[Math.min(tierRank(tier) + 1, TIER_ORDER.length - 1)];
}
