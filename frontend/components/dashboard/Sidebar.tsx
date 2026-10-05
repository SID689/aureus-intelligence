"use client";
/**
 * The navigation rail, set as an index rather than an icon list.
 *
 * THE NUMBERS ARE THE ICONS
 * Every destination carries a two-digit figure, the way a terminal lists
 * its functions. That was already true, but the figure sat beside the
 * label as an ornament. Here it is promoted into a bordered cell, which
 * makes it the thing the eye lands on and gives the rail something to
 * collapse to: at 68px the labels fall away and the cells remain, and the
 * rail is still navigable because 03 has meant Leaderboard since the
 * first time you opened it. No icon set to draw, nothing to learn twice,
 * and a collapsed rail that looks like the spine of the instrument rather
 * than a strip of pictograms.
 *
 * SELECTION IS A REVERSE, NOT A STRIPE
 * The active cell inverts: gold ground, ink figure. A filled cell reads
 * from the far side of a desk in a way a tinted row never does, and it
 * spends no new colour. The row behind it lifts one step in luminance so
 * the pairing still works for anyone who cannot separate the gold.
 *
 * WHAT THE RAIL KNOWS
 * Dashboard shows the number of positions on file, read from the
 * portfolio context the chrome above already loads. It costs no request,
 * and it means the rail reports state rather than only listing places.
 * Locked destinations name the plan they need in small caps, as before:
 * a padlock says "no", a plan name says what to do about it.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { IconChevronLeft, IconChevronRight, IconClose, IconLogout } from "@/components/ui/icons";
import Logo from "@/components/brand/Logo";
import { usePortfolio } from "./PortfolioProvider";
import { TIER_LABEL, asTier, meetsTier, nextTier } from "@/lib/tiers";
import type { TierName } from "@/types";

type NavItem = {
  href: string;
  label: string;
  tier?: TierName;
  /** One line explaining the destination, shown as the title on hover. */
  note: string;
};

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Portfolio",
    items: [
      { href: "/", label: "Dashboard", note: "Positions, allocation and exposure" },
      { href: "/analysis", label: "Analysis", note: "Score any ticker on all three pillars" },
    ],
  },
  {
    label: "Research",
    items: [
      { href: "/leaderboard", label: "Leaderboard", tier: "elite", note: "The index ranked by composite" },
      { href: "/backtest", label: "Backtest", note: "Test a strategy against real history" },
      { href: "/quant-lab", label: "Quant Lab", tier: "elite", note: "Monte Carlo, value at risk, peer sets" },
      { href: "/voice", label: "Voice", tier: "elite", note: "Ask questions against your own book" },
    ],
  },
  {
    label: "Learn",
    items: [
      { href: "/education", label: "Education", note: "Courses from beginner to expert" },
      { href: "/games", label: "Games", note: "FinWordle and chart patterns" },
    ],
  },
];

const TIER_BADGE: Record<TierName, "muted" | "default" | "institutional"> = {
  sovereign: "muted",
  plus: "muted",
  elite: "default",
  institutional: "institutional",
};

const STORE = "aureus.rail.collapsed";

/** Two letters for the account cell, from the display name or the address. */
function monogram(name: string | null | undefined, email: string | null | undefined): string {
  const source = (name || "").trim();
  if (source) {
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return source.slice(0, 2).toUpperCase();
  }
  return (email || "··").slice(0, 2).toUpperCase();
}

/**
 * The index cell. Square, hairline-bordered, inverted when active, and
 * the only thing left of a row once the rail is collapsed.
 */
function IndexCell({ figure, active, locked }: { figure: string; active: boolean; locked?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "w-[22px] h-[22px] shrink-0 grid place-items-center rounded-sm border font-mono-num text-[10px] leading-none transition-colors",
        active
          ? "bg-aureus-gold border-aureus-gold text-aureus-ink font-semibold"
          : locked
            ? "border-aureus-rule text-aureus-muted group-hover:border-aureus-golddim group-hover:text-aureus-golddim"
            : "border-aureus-rule text-aureus-muted group-hover:border-aureus-gold group-hover:text-aureus-gold",
      )}
    >
      {figure}
    </span>
  );
}

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const { holdings } = usePortfolio();
  const tier = asTier(session?.user?.tier);

  // The drawer is never collapsed: on a phone the rail IS the menu, and a
  // 68px spine over a scrim would be a worse version of both.
  const inDrawer = !!onNavigate;
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Read the stored preference after mount rather than during render, so
  // the server and first client paint agree. The width transition is held
  // back until then too, otherwise a restored collapsed rail animates
  // shut in front of the user on every page load.
  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(STORE) === "1");
    } catch {
      /* private window, or storage refused. Expanded is the safe default. */
    }
    setMounted(true);
  }, []);

  const toggle = useCallback(() => {
    setCollapsed((was) => {
      const next = !was;
      try {
        window.localStorage.setItem(STORE, next ? "1" : "0");
      } catch { /* the preference simply does not persist */ }
      return next;
    });
  }, []);

  const narrow = collapsed && !inDrawer;
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  const email = session?.user?.email ?? "";
  const name = session?.user?.name ?? "";
  const settingsActive = isActive("/settings");
  let index = 0;

  return (
    <aside
      className={cn(
        "shrink-0 flex flex-col h-full bg-aureus-panel border-r border-aureus-rule",
        narrow ? "w-[68px]" : "w-56",
        mounted && "transition-[width] duration-200 ease-out",
      )}
      data-collapsed={narrow ? "true" : "false"}
    >
      {/* ── Mark ─────────────────────────────────────────────────── */}
      <div
        className={cn(
          "border-b border-aureus-rule flex items-center",
          narrow ? "justify-center px-0 py-4" : "justify-between px-5 py-5",
        )}
      >
        {narrow ? (
          <Link href="/" aria-label="Aureus Intelligence" title="Aureus Intelligence">
            <Logo size={26} />
          </Link>
        ) : (
          <Logo size={28} withWordmark wordmarkClassName="text-xl" tagline="Intelligence" />
        )}

        {inDrawer && (
          <button
            onClick={onNavigate}
            className="tap-target md:hidden p-1 text-aureus-muted hover:text-aureus-text"
            aria-label="Close navigation"
          >
            <IconClose className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* ── Plan ─────────────────────────────────────────────────── */}
      {narrow ? (
        <Link
          href={tier === "institutional" ? "/settings" : "/upgrade"}
          title={`${TIER_LABEL[tier]} plan`}
          aria-label={`${TIER_LABEL[tier]} plan`}
          className="border-b border-aureus-rule py-3 grid place-items-center hover:bg-aureus-panellift transition-colors"
        >
          <span
            className={cn(
              "w-[22px] h-[22px] grid place-items-center rounded-sm border font-mono-num text-[10px] leading-none",
              tier === "institutional"
                ? "bg-aureus-text border-aureus-text text-aureus-ink"
                : tier === "elite"
                  ? "border-aureus-gold text-aureus-gold"
                  : "border-aureus-rule text-aureus-muted",
            )}
          >
            {TIER_LABEL[tier].slice(0, 1)}
          </span>
        </Link>
      ) : (
        <div className="px-5 py-3 border-b border-aureus-rule flex items-center gap-2">
          <span className="label-caps">Plan</span>
          <Badge variant={TIER_BADGE[tier]}>{TIER_LABEL[tier]}</Badge>
          {tier !== "institutional" && (
            <Link
              href="/upgrade"
              onClick={onNavigate}
              className="ml-auto text-[11px] text-aureus-gold hover:text-aureus-goldbright"
            >
              {tier === "sovereign" ? "Upgrade" : TIER_LABEL[nextTier(tier)]}
            </Link>
          )}
        </div>
      )}

      {/* ── Index ────────────────────────────────────────────────── */}
      <nav
        className={cn("flex-1 overflow-y-auto overflow-x-hidden py-4", narrow ? "px-3 space-y-3" : "px-2 space-y-5")}
        aria-label="Primary"
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {narrow ? (
              // The group still divides the rail, it just stops naming
              // itself. A hairline is legible at 68px; 10px small caps
              // rotated or truncated would not be.
              <div aria-hidden className="h-px bg-aureus-rule mx-1 mb-2" />
            ) : (
              <div className="rule-label label-caps px-3 pb-2">{group.label}</div>
            )}

            <ul className={cn(narrow && "space-y-[3px]")}>
              {group.items.map((item) => {
                index += 1;
                const figure = String(index).padStart(2, "0");
                const locked = !!item.tier && !meetsTier(tier, item.tier);
                const active = isActive(item.href);
                const href = locked
                  ? `/upgrade?feature=${item.href.slice(1)}&required_tier=${item.tier}`
                  : item.href;
                const count = item.href === "/" && holdings.length > 0 ? holdings.length : null;

                return (
                  <li key={item.href}>
                    <Link
                      href={href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      // Collapsed, the cell is all there is to read, so the
                      // tooltip carries what the row would have said: the
                      // name, and the plan it needs if it is locked.
                      title={
                        narrow
                          ? `${figure}  ${item.label}${locked ? `  ·  ${TIER_LABEL[item.tier!]} plan` : ""}`
                          : locked
                            ? `${item.note}  ·  ${TIER_LABEL[item.tier!]} plan`
                            : item.note
                      }
                      aria-label={narrow ? item.label : undefined}
                      className={cn(
                        "group flex items-center transition-colors rounded-sm",
                        narrow
                          ? "justify-center py-2.5 touch:py-3"
                          : "gap-2.5 px-2.5 py-3 md:py-2 text-[13px]",
                        active
                          ? "bg-aureus-panelhigh text-aureus-text"
                          : "text-aureus-soft hover:bg-aureus-panellift hover:text-aureus-text",
                      )}
                    >
                      <IndexCell figure={figure} active={active} locked={locked} />

                      {!narrow && (
                        <>
                          <span className={cn("truncate", locked && "text-aureus-muted")}>{item.label}</span>
                          <span className="ml-auto pl-2 flex items-center">
                            {locked ? (
                              <span className="label-caps text-[9px] text-aureus-golddim group-hover:text-aureus-gold">
                                {TIER_LABEL[item.tier!]}
                              </span>
                            ) : count !== null ? (
                              <span className="font-mono-num text-[10.5px] text-aureus-muted">{count}</span>
                            ) : null}
                          </span>
                        </>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* ── Account ──────────────────────────────────────────────── */}
      <div className={cn("border-t border-aureus-rule", narrow ? "px-3 py-3 space-y-2" : "px-2 py-3")}>
        <Link
          href="/settings"
          onClick={onNavigate}
          title={narrow ? "Settings" : undefined}
          aria-current={settingsActive ? "page" : undefined}
          className={cn(
            "group flex items-center transition-colors rounded-sm",
            narrow ? "justify-center py-2.5 touch:py-3" : "gap-2.5 px-2.5 py-3 md:py-2 text-[13px]",
            settingsActive
              ? "bg-aureus-panelhigh text-aureus-text"
              : "text-aureus-soft hover:bg-aureus-panellift hover:text-aureus-text",
          )}
        >
          <IndexCell figure="··" active={settingsActive} />
          {!narrow && <span>Settings</span>}
        </Link>

        {narrow ? (
          <>
            <div
              title={email || "Account"}
              className="grid place-items-center py-1"
            >
              <span className="w-[22px] h-[22px] grid place-items-center rounded-sm border border-aureus-rulestrong font-mono-num text-[9.5px] text-aureus-soft">
                {monogram(name, email)}
              </span>
            </div>
            <button
              onClick={() => signOut({ callbackUrl: "/welcome" })}
              title="Sign out"
              aria-label="Sign out"
              className="w-full grid place-items-center py-2.5 touch:py-3 rounded-sm text-aureus-muted hover:text-aureus-text hover:bg-aureus-panellift transition-colors"
            >
              <IconLogout className="w-4 h-4" />
            </button>
          </>
        ) : (
          <>
            <div className="px-2.5 pt-3 flex items-center gap-2.5 min-w-0">
              <span className="w-[22px] h-[22px] shrink-0 grid place-items-center rounded-sm border border-aureus-rulestrong font-mono-num text-[9.5px] text-aureus-soft">
                {monogram(name, email)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-aureus-soft text-[12.5px] truncate">{name || "Account"}</span>
                <span className="block text-aureus-muted text-[10.5px] truncate font-mono-num">{email}</span>
              </span>
              <button
                onClick={() => signOut({ callbackUrl: "/welcome" })}
                title="Sign out"
                aria-label="Sign out"
                className="tap-target shrink-0 p-1 text-aureus-muted hover:text-aureus-text transition-colors"
              >
                <IconLogout className="w-4 h-4" />
              </button>
            </div>

            <div className="px-2.5 pt-3 flex gap-4 text-[10.5px] text-aureus-muted">
              <Link href="/terms" className="py-2 md:py-0 hover:text-aureus-text">Terms</Link>
              <Link href="/privacy" className="py-2 md:py-0 hover:text-aureus-text">Privacy</Link>
            </div>
          </>
        )}
      </div>

      {/* ── Collapse ─────────────────────────────────────────────── */}
      {!inDrawer && (
        <button
          onClick={toggle}
          aria-expanded={!narrow}
          aria-label={narrow ? "Expand the navigation rail" : "Collapse the navigation rail"}
          title={narrow ? "Expand" : "Collapse"}
          className={cn(
            "hidden md:flex items-center gap-2 border-t border-aureus-rule py-2 text-aureus-muted",
            "hover:text-aureus-gold hover:bg-aureus-panellift transition-colors",
            narrow ? "justify-center px-0" : "justify-end px-4",
          )}
        >
          {!narrow && <span className="label-caps text-[9px]">Collapse</span>}
          {narrow ? <IconChevronRight className="w-3.5 h-3.5" /> : <IconChevronLeft className="w-3.5 h-3.5" />}
        </button>
      )}
    </aside>
  );
}
