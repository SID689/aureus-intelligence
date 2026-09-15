"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import {
  LayoutDashboard, LineChart, Mic, FlaskConical, GraduationCap, Gamepad2,
  Settings, LogOut, Lock, Sigma, X, Flame,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import Logo from "@/components/brand/Logo";
import type { TierName } from "@/types";

/**
 * Eight flat destinations is a list you read; three labelled groups is a
 * structure you navigate. The grouping also makes the tier gates legible
 * — Voice and Quant Lab sit together under Research, so it's obvious what
 * upgrading actually buys rather than two padlocks scattered down a list.
 */
const NAV_GROUPS: {
  label: string;
  items: { href: string; label: string; icon: LucideIcon; tier?: TierName }[];
}[] = [
  {
    label: "Portfolio",
    items: [
      { href: "/",         label: "Dashboard", icon: LayoutDashboard },
      { href: "/analysis", label: "Analysis",  icon: LineChart },
    ],
  },
  {
    label: "Research",
    items: [
      { href: "/leaderboard", label: "Leaderboard", icon: Flame, tier: "elite" },
      { href: "/backtest",  label: "Backtest",  icon: FlaskConical },
      { href: "/quant-lab", label: "Quant Lab", icon: Sigma, tier: "elite" },
      { href: "/voice",     label: "Voice",     icon: Mic,   tier: "elite" },
    ],
  },
  {
    label: "Learn",
    items: [
      { href: "/education", label: "Education", icon: GraduationCap },
      { href: "/games",     label: "Games",     icon: Gamepad2 },
    ],
  },
];

const TIER_BADGE: Record<TierName, { label: string; variant: "default" | "green" | "institutional" | "muted" }> = {
  sovereign:     { label: "Sovereign",     variant: "muted" },
  elite:         { label: "Elite",         variant: "default" },
  institutional: { label: "Institutional", variant: "institutional" },
};

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = (session?.user?.tier ?? "sovereign") as TierName;
  const tierBadge = TIER_BADGE[tier];

  const link = (
    { href, label, icon: Icon, tier: requiredTier }:
    { href: string; label: string; icon: LucideIcon; tier?: TierName }
  ) => {
    const isActive = pathname === href;
    const isLocked = !!requiredTier && tier === "sovereign";
    return (
      <Link
        key={href}
        href={isLocked ? `/upgrade?feature=${label.toLowerCase()}` : href}
        onClick={onNavigate}
        className={cn(
          "group flex items-center gap-3 pl-3 pr-2.5 py-2 rounded-md text-[13px] transition-colors border-l-2",
          isActive
            ? "text-aureus-gold border-aureus-gold bg-aureus-gold/[0.07]"
            : "text-aureus-muted border-transparent hover:text-aureus-text hover:bg-aureus-panellift"
        )}
      >
        <Icon className="w-4 h-4 shrink-0" strokeWidth={1.75} />
        <span className="flex-1">{label}</span>
        {isLocked && <Lock className="w-3 h-3 text-aureus-golddim group-hover:text-aureus-gold" />}
      </Link>
    );
  };

  return (
    <aside className="w-56 shrink-0 flex flex-col h-full bg-aureus-panel border-r border-aureus-rule">
      <div className="px-5 py-5 border-b border-aureus-rule flex items-start justify-between">
        <Logo size={30} withWordmark wordmarkClassName="text-xl" tagline="Intelligence Platform" />
        {onNavigate && (
          <button onClick={onNavigate} className="md:hidden text-aureus-muted hover:text-aureus-text" aria-label="Close navigation">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="px-5 py-3 border-b border-aureus-rule flex items-center gap-2">
        <Badge variant={tierBadge.variant}>{tierBadge.label}</Badge>
        {tier === "sovereign" && (
          <Link href="/upgrade" onClick={onNavigate} className="text-[11px] text-aureus-gold hover:text-aureus-goldbright ml-auto">
            Upgrade
          </Link>
        )}
      </div>

      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="label-caps px-3 pb-2">{group.label}</div>
            <div className="space-y-0.5">{group.items.map(link)}</div>
          </div>
        ))}
      </nav>

      <div className="px-3 py-3 border-t border-aureus-rule space-y-0.5">
        {link({ href: "/settings", label: "Settings", icon: Settings })}
        <div className="px-3 pt-3 pb-1">
          <div className="text-aureus-soft text-[13px] font-medium truncate">
            {session?.user?.name || session?.user?.email || "User"}
          </div>
          <div className="text-aureus-muted text-[11px] truncate font-mono">{session?.user?.email}</div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/welcome" })}
          className="flex items-center gap-3 pl-3 pr-2.5 py-2 rounded-md text-[13px] text-aureus-muted
                     hover:text-aureus-text hover:bg-aureus-panellift transition-colors w-full text-left border-l-2 border-transparent"
        >
          <LogOut className="w-4 h-4 shrink-0" strokeWidth={1.75} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
