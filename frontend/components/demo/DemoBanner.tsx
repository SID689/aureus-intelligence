"use client";
/**
 * The standing notice on every page of a demo session.
 *
 * Above the ticker tape and inside the sticky chrome, so it is the first
 * line on the page and stays visible while scrolling. It is a hairline
 * gold-on-ink strip rather than a coloured alert bar: a presentation
 * environment should be labelled unmistakably and still look like part of
 * the instrument.
 *
 * It renders only for sessions the demo provider minted. A real signed-in
 * customer never sees it, even on a build with demo mode compiled in.
 */
import { useSession } from "next-auth/react";
import Link from "next/link";
import { DEMO_BANNER_NOTE, DEMO_BANNER_TEXT } from "@/lib/demo";

export default function DemoBanner() {
  const { data: session } = useSession();
  if (!session?.user?.demo) return null;

  return (
    <div className="bg-aureus-panelhigh border-b border-aureus-golddim">
      <div className="flex items-center gap-2 px-4 sm:px-6 py-1">
        <span
          aria-hidden
          className="w-1 h-1 bg-aureus-gold shrink-0"
        />
        <span className="label-caps text-aureus-gold text-[9.5px]">{DEMO_BANNER_TEXT}</span>
        <span className="hidden sm:inline text-aureus-golddim text-[10px]">|</span>
        <span className="hidden sm:inline label-caps text-[9.5px] text-aureus-soft">{DEMO_BANNER_NOTE}</span>
        <Link
          href="/demo/qr"
          className="tap-target ml-auto label-caps text-[9.5px] text-aureus-muted hover:text-aureus-gold shrink-0"
        >
          Share
        </Link>
      </div>
    </div>
  );
}
