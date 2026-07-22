"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import {
  LayoutDashboard, LineChart, Mic, ShoppingBag,
  Settings, LogOut, Zap, AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { TierName } from "@/types";

const NAV_ITEMS = [
  { href: "/",         label: "Dashboard",  icon: LayoutDashboard },
  { href: "/analysis", label: "Analysis",   icon: LineChart       },
  { href: "/voice",    label: "Voice",      icon: Mic, tier: "elite" as TierName },
  { href: "/orders",   label: "Orders",     icon: ShoppingBag, tier: "elite" as TierName },
  { href: "/settings", label: "Settings",   icon: Settings        },
];

const TIER_BADGE: Record<TierName, { label: string; variant: "default" | "green" | "institutional" | "muted" }> = {
  sovereign:     { label: "Sovereign",     variant: "muted"         },
  elite:         { label: "Elite",         variant: "default"       },
  institutional: { label: "Institutional", variant: "institutional" },
};

export default function Sidebar() {
  const pathname    = usePathname();
  const { data: session } = useSession();
  const tier        = (session?.user?.tier ?? "sovereign") as TierName;
  const tierBadge   = TIER_BADGE[tier];

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col border-r border-aureus-border h-screen sticky top-0"
           style={{ background: "var(--surface)" }}>
      {/* Logo */}
      <div className="px-5 py-4 border-b border-aureus-border">
        <div className="text-aureus-gold font-bold text-lg tracking-wide">◆ AUREUS</div>
        <div className="text-aureus-muted text-xs mt-0.5">Intelligence Platform</div>
      </div>

      {/* Tier badge */}
      <div className="px-5 py-3 border-b border-aureus-border flex items-center gap-2">
        <Badge variant={tierBadge.variant}>{tierBadge.label}</Badge>
        {tier === "sovereign" && (
          <Link href="/upgrade"
                className="text-xs text-aureus-gold hover:underline ml-auto">
            Upgrade
          </Link>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, tier: requiredTier }) => {
          const isActive  = pathname === href;
          const isLocked  = requiredTier && tier === "sovereign";

          return (
            <Link key={href} href={isLocked ? `/upgrade?feature=${label.toLowerCase()}` : href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                    isActive
                      ? "bg-aureus-gold/10 text-aureus-gold"
                      : "text-aureus-muted hover:text-white hover:bg-white/5",
                    isLocked && "opacity-40 cursor-not-allowed"
                  )}>
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{label}</span>
              {isLocked && <Zap className="w-3 h-3 text-aureus-gold" />}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="px-3 py-3 border-t border-aureus-border space-y-1">
        <div className="px-3 py-2">
          <div className="text-white text-sm font-medium truncate">
            {session?.user?.name || session?.user?.email || "User"}
          </div>
          <div className="text-aureus-muted text-xs truncate">{session?.user?.email}</div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/sign-in" })}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-aureus-muted
                     hover:text-white hover:bg-white/5 transition-colors w-full text-left"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
