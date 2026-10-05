"use client";
/**
 * The function row: navigation across the top, where a terminal keeps it.
 *
 * WHY IT IS NOT A SIDE RAIL ANY MORE
 * A 224px column was spending an eighth of a laptop screen on eight words
 * that never change, in a product whose whole output is wide: price
 * charts, a five-column leaderboard, a pricing matrix that had to scroll
 * sideways to be read. Across the top the same eight destinations cost
 * about 44px of height and give all of that width back.
 *
 * SELECTION IS A RULED TAB
 * The current destination is underscored with a hairline of gold and its
 * label brightens. In a horizontal row an underline is the native idiom
 * for "you are here", it reads as the rule under a ledger heading rather
 * than as an accent bar, and it costs no fill.
 *
 * WHAT HAPPENS AS THE WINDOW NARROWS
 * Eight labels, the mark and the instruments need about 970px. Below
 * `xl` the figures drop and the labels carry the row alone; below `lg`
 * the row is replaced entirely by the tab bar at the bottom of the
 * screen, which is where a thumb is. Nothing is ever cut off mid-word or
 * pushed into a sideways scroll.
 */
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { IconChevronDown, IconLogout, IconSearch } from "@/components/ui/icons";
import Logo from "@/components/brand/Logo";
import NotificationBell from "@/components/notifications/NotificationBell";
import { DESTINATIONS, isCurrent, lockedHref } from "@/lib/navigation";
import { TIER_LABEL, asTier, meetsTier, nextTier } from "@/lib/tiers";
import type { TierName } from "@/types";

const TIER_BADGE: Record<TierName, "muted" | "default" | "institutional"> = {
  sovereign: "muted",
  plus: "muted",
  elite: "default",
  institutional: "institutional",
};

function monogram(name: string | null | undefined, email: string | null | undefined): string {
  const source = (name || "").trim();
  if (source) {
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return source.slice(0, 2).toUpperCase();
  }
  return (email || "··").slice(0, 2).toUpperCase();
}

/** The account menu, which is where everything the old rail's footer held now lives. */
function AccountMenu({ tier }: { tier: TierName }) {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const name = session?.user?.name ?? "";
  const email = session?.user?.email ?? "";

  return (
    <div ref={root} className="relative shrink-0">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account"
        className={cn(
          "flex items-center gap-1.5 pl-1 pr-1.5 h-8 touch:h-11 rounded-sm transition-colors",
          open ? "bg-aureus-panelhigh" : "hover:bg-aureus-panellift",
        )}
      >
        <span className="w-[22px] h-[22px] grid place-items-center rounded-sm border border-aureus-rulestrong font-mono-num text-[9.5px] text-aureus-soft">
          {monogram(name, email)}
        </span>
        <IconChevronDown className={cn("w-3 h-3 text-aureus-muted transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1 w-60 border border-aureus-rule bg-aureus-panel shadow-overlay z-50"
        >
          <div className="px-4 py-3 border-b border-aureus-rule">
            <div className="text-[13px] text-aureus-text truncate">{name || "Account"}</div>
            <div className="text-[11px] text-aureus-muted truncate font-mono-num">{email}</div>
            <div className="mt-2.5 flex items-center gap-2">
              <span className="label-caps">Plan</span>
              <Badge variant={TIER_BADGE[tier]}>{TIER_LABEL[tier]}</Badge>
              {tier !== "institutional" && (
                <Link
                  href="/upgrade"
                  onClick={() => setOpen(false)}
                  className="ml-auto text-[11px] text-aureus-gold hover:text-aureus-goldbright"
                >
                  {tier === "sovereign" ? "Upgrade" : TIER_LABEL[nextTier(tier)]}
                </Link>
              )}
            </div>
          </div>

          <Link
            href="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="block px-4 py-2.5 text-[13px] text-aureus-soft hover:bg-aureus-panellift hover:text-aureus-text transition-colors"
          >
            Settings
          </Link>
          <button
            role="menuitem"
            onClick={() => { setOpen(false); void signOut({ callbackUrl: "/welcome" }); }}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-left text-[13px] text-aureus-soft hover:bg-aureus-panellift hover:text-aureus-text transition-colors"
          >
            <IconLogout className="w-3.5 h-3.5" />
            Sign out
          </button>

          <div className="px-4 py-2.5 border-t border-aureus-rule flex gap-4 text-[10.5px] text-aureus-muted">
            <Link href="/terms" onClick={() => setOpen(false)} className="hover:text-aureus-text">Terms</Link>
            <Link href="/privacy" onClick={() => setOpen(false)} className="hover:text-aureus-text">Privacy</Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FunctionRow({ onOpenPalette }: { onOpenPalette: () => void }) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = asTier(session?.user?.tier);

  return (
    <div className="flex items-stretch gap-1 px-3 sm:px-4 bg-aureus-panel border-b border-aureus-rule">
      <Link href="/" aria-label="Aureus Intelligence" className="shrink-0 flex items-center pr-3 sm:pr-4 mr-1 border-r border-aureus-rule">
        <Logo size={24} />
      </Link>

      {/* ── Destinations ───────────────────────────────────────── */}
      <nav aria-label="Primary" className="hidden lg:flex items-stretch min-w-0 flex-1">
        {DESTINATIONS.map((d) => {
          const locked = !!d.tier && !meetsTier(tier, d.tier);
          const active = isCurrent(pathname, d.href);
          return (
            <Link
              key={d.href}
              href={locked ? lockedHref(d) : d.href}
              aria-current={active ? "page" : undefined}
              title={locked ? `${d.note}  ·  ${TIER_LABEL[d.tier!]} plan` : d.note}
              className={cn(
                "group relative flex items-baseline gap-1.5 px-2.5 lg:px-3 py-3 text-[13px] whitespace-nowrap transition-colors",
                active ? "text-aureus-text" : locked ? "text-aureus-muted hover:text-aureus-soft" : "text-aureus-soft hover:text-aureus-text",
              )}
            >
              <span
                className={cn(
                  "hidden xl:inline font-mono-num text-[10px] transition-colors",
                  active ? "text-aureus-gold" : "text-aureus-muted group-hover:text-aureus-soft",
                )}
              >
                {d.figure}
              </span>
              {d.label}
              {locked && (
                <span className="label-caps text-[8.5px] text-aureus-golddim group-hover:text-aureus-gold">
                  {TIER_LABEL[d.tier!]}
                </span>
              )}
              {/* The ruled tab. Sits on the row's own bottom border, so the
                  active item reads as ruled rather than boxed. */}
              <span
                aria-hidden
                className={cn(
                  "absolute left-2 right-2 -bottom-px h-px transition-colors",
                  active ? "bg-aureus-gold" : "bg-transparent group-hover:bg-aureus-rulestrong",
                )}
              />
            </Link>
          );
        })}
      </nav>

      {/* On a phone the destinations live in the tab bar at the bottom, so
          this side carries the title of the page instead of nothing. */}
      <span className="lg:hidden flex-1 flex items-center min-w-0">
        <span className="font-display text-[15px] text-aureus-text truncate">
          {DESTINATIONS.find((d) => isCurrent(pathname, d.href))?.label ?? "Aureus"}
        </span>
      </span>

      {/* ── Instruments ────────────────────────────────────────── */}
      <div className="shrink-0 flex items-center gap-1 sm:gap-2 pl-2 sm:pl-3 ml-1 border-l border-aureus-rule">
        <button
          onClick={onOpenPalette}
          aria-label="Open the command palette"
          className="flex items-center gap-2 h-8 touch:h-11 px-2 sm:px-2.5 rounded-sm border border-aureus-rule text-aureus-muted hover:border-aureus-gold hover:text-aureus-gold transition-colors"
        >
          <IconSearch className="w-3.5 h-3.5" />
          <span className="hidden xl:inline text-[12px]">Search</span>
          <kbd className="hidden xl:inline font-mono-num text-[10px] text-aureus-muted/80 border border-aureus-rule px-1 leading-[1.4]">
            ⌘K
          </kbd>
        </button>

        <NotificationBell />
        <AccountMenu tier={tier} />
      </div>
    </div>
  );
}
