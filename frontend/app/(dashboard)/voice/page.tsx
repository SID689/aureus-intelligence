"use client";
/**
 * Voice. Inherits the dashboard layout's auth guard and reads user and plan
 * from the session. The plan check here only chooses what to show: the voice
 * socket enforces the plan on the server regardless.
 */
import Link from "next/link";
import { useSession } from "next-auth/react";
import VoiceInterface from "@/components/VoiceInterface";
import { Button } from "@/components/ui/button";
import { Note, PageHeader, Sheet } from "@/components/ui/primitives";
import { LoadingRegion, Skeleton, SkeletonPageHeader } from "@/components/ui/Skeleton";
import { TIER_LABEL, asTier, meetsTier } from "@/lib/tiers";

export default function VoicePage() {
  const { data: session, status } = useSession();
  const userId = session?.user?.id ?? "";
  const tier = asTier(session?.user?.tier);

  if (status === "loading") {
    return (
      <LoadingRegion label="Loading voice" className="max-w-3xl mx-auto space-y-6">
        <SkeletonPageHeader />
        <Skeleton className="h-[420px] w-full" />
      </LoadingRegion>
    );
  }

  if (!meetsTier(tier, "elite")) {
    return (
      <div className="max-w-2xl mx-auto py-10">
        <Sheet lift className="p-8">
          <p className="label-caps text-aureus-gold">Elite and Institutional</p>
          <h1 className="font-display text-[30px] leading-tight text-aureus-text mt-3">Voice</h1>
          <p className="text-[14px] text-aureus-soft leading-relaxed mt-4 max-w-lg">
            Talk through a position out loud and get an answer that remembers the rest of the conversation. Your plan is{" "}
            {TIER_LABEL[tier]}. The three-pillar analysis stays available on every plan, including yours.
          </p>
          <div className="flex flex-wrap gap-2 mt-7">
            <Link href="/upgrade?feature=voice&required_tier=elite"><Button>See Elite</Button></Link>
            <Link href="/"><Button variant="outline">Back to dashboard</Button></Link>
          </div>
        </Sheet>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader
        title="Voice"
        lead="Talk through a position out loud. Context carries across the session, so a follow-up does not need to restate which stock you meant."
      />
      <VoiceInterface userId={userId} tier={tier} />
      <Note>
        Nothing said here is financial advice. Voice sessions are processed by AI providers as described in the{" "}
        <Link href="/privacy#ai" className="text-aureus-gold hover:underline">Privacy Policy</Link>.
      </Note>
    </div>
  );
}
