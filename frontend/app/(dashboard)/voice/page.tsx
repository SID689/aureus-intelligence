"use client";
/**
 * Moved under (dashboard) from a top-level /voice route. The URL is
 * unchanged — parenthesised segments are route groups, not path segments —
 * but the page now inherits the sidebar, the tape and, critically, the
 * layout's auth guard. Before this it rendered for anyone who typed the
 * URL, with no navigation back out.
 *
 * It also used to hardcode `userId="00000000-…-0001"` and `tier="elite"`,
 * so every voice session was attributed to a user that does not exist and
 * the tier gate was decided by a string literal. Both now come from the
 * session.
 */
import Link from "next/link";
import { useSession } from "next-auth/react";
import { Lock, Mic } from "lucide-react";
import VoiceInterface from "@/components/VoiceInterface";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, Note, PageHeader } from "@/components/ui/primitives";
import type { TierName } from "@/types";

export default function VoicePage() {
  const { data: session, status } = useSession();
  const userId = session?.user?.id ?? "";
  const tier = (session?.user?.tier ?? "sovereign") as TierName;

  if (status === "loading") {
    return <div className="py-20 text-center text-sm text-aureus-muted">Loading…</div>;
  }

  // Client-side gate for a useful message only. The server returns 402 on
  // the voice socket regardless of what this component renders, which is
  // what makes the gate real rather than a hidden link.
  if (tier === "sovereign") {
    return (
      <div className="max-w-xl mx-auto py-10">
        <Card accent>
          <EmptyState
            icon={Lock}
            title="Voice is an Elite feature"
            action={
              <div className="flex gap-2">
                <Link href="/upgrade?feature=voice"><Button>Upgrade to Elite</Button></Link>
                <Link href="/"><Button variant="outline">Back to dashboard</Button></Link>
              </div>
            }
          >
            Talk through a position out loud and get an answer that remembers the rest of the
            conversation. Your plan is Sovereign — the three-pillar analysis stays available on
            every plan, including yours.
          </EmptyState>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <Mic className="w-5 h-5 text-aureus-gold" strokeWidth={1.75} /> Voice
          </span>
        }
        lead="Talk through a position out loud. Context carries across the session, so you can ask a
              follow-up without restating which stock you meant."
      />

      <VoiceInterface userId={userId} tier={tier} />

      <Note>
        Nothing said here constitutes financial advice. Voice sessions are processed by AI and may
        be logged for quality purposes.
      </Note>
    </div>
  );
}
