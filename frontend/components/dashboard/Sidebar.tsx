"use client";
/**
 * The navigation rail, set as an index rather than an icon list.
 *
 * Each destination carries a two-digit number in the figure face, the way
 * a terminal lists its functions, and a locked destination names the plan
 * it needs in small caps instead of showing a padlock. The rail reads as
 * a table of contents for an instrument, which is what it is.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { IconClose } from "@/components/ui/icons";
import Logo from "@/components/brand/Logo";
import { TIER_LABEL, asTier, meetsTier, nextTier } from "@/lib/tiers";
import type { TierName } from "@/types";

type NavItem = { href: string; label: string; tier?: TierName };

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  { label: "Portfolio", items: [{ href: "/", label: "Dashboard" }, { href: "/analysis", label: "Analysis" }] },
  {
    label: "Research",
    items: [
      { href: "/leaderboard", label: "Leaderboard", tier: "elite" },
      { href: "/backtest", label: "Backtest" },
      { href: "/quant-lab", label: "Quant Lab", tier: "elite" },
      { href: "/voice", label: "Voice", tier: "elite" },
    ],
  },
  { label: "Learn", items: [{ href: "/education", label: "Education" }, { href: "/games", label: "Games" }] },
];

const TIER_BADGE: Record<TierName, "muted" | "default" | "institutional"> = {
  sovereign: "muted",
  plus: "muted",
  elite: "default",
  institutional: "institutional",
};

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = asTier(session?.user?.tier);
  let index = 0;

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`));

  return (
    <aside className="w-56 shrink-0 flex flex-col h-full bg-aureus-panel border-r border-aureus-rule">
      <div className="px-5 py-5 border-b border-aureus-rule flex items-start justify-between">
        <Logo size={28} withWordmark wordmarkClassName="text-xl" tagline="Intelligence" />
        {onNavigate && (
          <button onClick={onNavigate} className="tap-target md:hidden p-1 text-aureus-muted hover:text-aureus-text" aria-label="Close navigation">
            <IconClose className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="px-5 py-3 border-b border-aureus-rule flex items-center gap-2">
        <span className="label-caps">Plan</span>
        <Badge variant={TIER_BADGE[tier]}>{TIER_LABEL[tier]}</Badge>
        {tier !== "institutional" && (
          <Link href="/upgrade" onClick={onNavigate} className="ml-auto text-[11px] text-aureus-gold hover:text-aureus-goldbright">
            {tier === "sovereign" ? "Upgrade" : `${TIER_LABEL[nextTier(tier)]}`}
          </Link>
        )}
      </div>

      <nav className="flex-1 px-2 py-4 space-y-5 overflow-y-auto" aria-label="Primary">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="label-caps px-3 pb-1.5">{group.label}</div>
            <ul>
              {group.items.map((item) => {
                index += 1;
                const locked = !!item.tier && !meetsTier(tier, item.tier);
                const active = isActive(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={locked ? `/upgrade?feature=${item.href.slice(1)}&required_tier=${item.tier}` : item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group grid grid-cols-[1.75rem_1fr_auto] items-baseline px-3 py-3 md:py-[7px] text-[13px] transition-colors",
                        active ? "bg-aureus-panelhigh text-aureus-text" : "text-aureus-soft hover:bg-aureus-panellift hover:text-aureus-text",
                      )}
                    >
                      <span className={cn("font-mono-num text-[10.5px]", active ? "text-aureus-gold" : "text-aureus-muted")}>
                        {String(index).padStart(2, "0")}
                      </span>
                      <span className={cn(locked && "text-aureus-muted")}>{item.label}</span>
                      {locked && <span className="label-caps text-[9px] text-aureus-golddim group-hover:text-aureus-gold">{TIER_LABEL[item.tier!]}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="px-2 py-3 border-t border-aureus-rule">
        <Link
          href="/settings"
          onClick={onNavigate}
          className={cn(
            "grid grid-cols-[1.75rem_1fr] items-baseline px-3 py-3 md:py-[7px] text-[13px] transition-colors",
            isActive("/settings") ? "bg-aureus-panelhigh text-aureus-text" : "text-aureus-soft hover:bg-aureus-panellift hover:text-aureus-text",
          )}
        >
          <span className="font-mono-num text-[10.5px] text-aureus-muted">··</span>
          Settings
        </Link>
        <div className="px-3 pt-3">
          <div className="text-aureus-soft text-[13px] font-medium truncate">{session?.user?.name || session?.user?.email || "Account"}</div>
          <div className="text-aureus-muted text-[11px] truncate font-mono-num">{session?.user?.email}</div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/welcome" })}
          className="mt-2 w-full text-left px-3 py-3 md:py-[7px] text-[12.5px] text-aureus-muted hover:text-aureus-text hover:bg-aureus-panellift transition-colors"
        >
          Sign out
        </button>
        <div className="px-3 pt-2 flex gap-4 text-[10.5px] text-aureus-muted">
          <Link href="/terms" className="py-2 md:py-0 hover:text-aureus-text">Terms</Link>
          <Link href="/privacy" className="py-2 md:py-0 hover:text-aureus-text">Privacy</Link>
        </div>
      </div>
    </aside>
  );
}
