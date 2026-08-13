"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import {
  LayoutDashboard, LineChart, Mic, FlaskConical, GraduationCap, Gamepad2,
  Settings, LogOut, Lock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { TierName } from "@/types";

const NAV_ITEMS = [
  { href: "/",         label: "Dashboard",  icon: LayoutDashboard },
  { href: "/analysis", label: "Analysis",   icon: LineChart       },
  { href: "/voice",    label: "Voice",      icon: Mic, tier: "elite" as TierName },
  { href: "/backtest", label: "Backtest",   icon: FlaskConical    },
  { href: "/education", label: "Education", icon: GraduationCap   },
  { href: "/games",    label: "Games",     icon: Gamepad2        },
  { href: "/settings", label: "Settings",   icon: Settings        },
];

const TIER_BADGE: Record<TierName, { label: string; variant: "default" | "green" | "institutional" | "muted" }> = {
  sovereign:     { label: "Sovereign",     variant: "muted"         },
  elite:         { label: "Elite",         variant: "default"       },
  institutional: { label: "Institutional", variant: "institutional" },
};

export default function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = (session?.user?.tier ?? "sovereign") as TierName;
  const tierBadge = TIER_BADGE[tier];

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col border-r border-aureus-rule h-screen sticky top-0"
           style={{ background: "var(--panel)" }}>
      {/* Logo — serif wordmark is the one typographic flourish here */}
      <div className="px-5 py-5 border-b border-aureus-rule">
        <div className="font-display text-aureus-gold text-xl tracking-wide" style={{ fontWeight: 600 }}>
          Aureus
        </div>
        <div className="text-aureus-muted text-[10px] mt-0.5 tracking-widest uppercase">Intelligence Platform</div>
      </div>

      {/* Tier badge */}
      <div className="px-5 py-3 border-b border-aureus-rule flex items-center gap-2">
        <Badge variant={tierBadge.variant}>{tierBadge.label}</Badge>
        {tier === "sovereign" && (
          <Link href="/upgrade" className="text-xs text-aureus-gold hover:underline ml-auto">Upgrade</Link>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, tier: requiredTier }) => {
          const isActive = pathname === href;
          const isLocked = requiredTier && tier === "sovereign";

          return (
            <Link key={href} href={isLocked ? `/upgrade?feature=${label.toLowerCase()}` : href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                    isActive
                      ? "text-aureus-gold border-l-2 border-aureus-gold bg-aureus-gold/[0.06] -ml-px"
                      : "text-aureus-muted hover:text-aureus-text hover:bg-white/[0.03] border-l-2 border-transparent",
                    isLocked && "opacity-40 cursor-not-allowed"
                  )}>
              <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.75} />
              <span className="flex-1">{label}</span>
              {isLocked && <Lock className="w-3 h-3 text-aureus-gold" />}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="px-3 py-3 border-t border-aureus-rule space-y-1">
        <div className="px-3 py-2">
          <div className="text-aureus-text text-sm font-medium truncate">
            {session?.user?.name || session?.user?.email || "User"}
          </div>
          <div className="text-aureus-muted text-xs truncate font-mono">{session?.user?.email}</div>
        </div>
        <button
          onClick={() => signOut({ callbackUrl: "/welcome" })}
          className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-aureus-muted
                     hover:text-aureus-text hover:bg-white/[0.03] transition-colors w-full text-left"
        >
          <LogOut className="w-4 h-4" strokeWidth={1.75} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
