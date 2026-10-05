/**
 * lib/navigation.ts — where you can go, defined once.
 *
 * Three surfaces render this list: the function row across the top, the
 * command palette behind Cmd-K, and the tab bar on a phone. They were
 * going to disagree about the order or miss a destination the first time
 * one was edited, so none of them owns the list.
 *
 * The two-digit figure is not decoration. It is how a destination is
 * addressed: the function row prints it, the palette matches on it, and
 * typing "04" is a complete query. Numbering is therefore positional and
 * stable, which is why the array order is the contract and new entries go
 * at the end of their group rather than wherever reads nicely.
 */
import type { TierName } from "@/types";

export interface Destination {
  href: string;
  label: string;
  /** Two-digit address, assigned from array order. */
  figure: string;
  group: "Portfolio" | "Research" | "Learn";
  /** Minimum plan. Undefined means every plan includes it. */
  tier?: TierName;
  /** One line, shown in the palette and as the function row's tooltip. */
  note: string;
  /** Extra words the palette should match on, for things people call by another name. */
  keywords?: string[];
  /** Shown in the phone tab bar. Four at most, or the bar stops being tappable. */
  primary?: boolean;
  /** Tab bar label, where a 75px cell truncates anything longer. */
  short?: string;
}

const RAW: Omit<Destination, "figure">[] = [
  {
    href: "/", label: "Dashboard", group: "Portfolio", primary: true,
    note: "Positions, allocation and exposure",
    keywords: ["portfolio", "holdings", "positions", "home"],
  },
  {
    href: "/analysis", label: "Analysis", group: "Portfolio", primary: true,
    note: "Score any ticker on all three pillars",
    keywords: ["score", "ticker", "research", "stock"],
  },
  {
    href: "/leaderboard", label: "Leaderboard", group: "Research", tier: "elite", primary: true, short: "Board",
    note: "The index ranked by composite score",
    keywords: ["hottest", "ranked", "strong buy", "board"],
  },
  {
    href: "/backtest", label: "Backtest", group: "Research", primary: true,
    note: "Test a strategy against real history",
    keywords: ["strategy", "history", "simulate"],
  },
  {
    href: "/quant-lab", label: "Quant Lab", group: "Research", tier: "elite",
    note: "Monte Carlo, value at risk, peer sets",
    keywords: ["monte carlo", "var", "risk", "factor"],
  },
  {
    href: "/voice", label: "Voice", group: "Research", tier: "elite",
    note: "Ask questions against your own book",
    keywords: ["speak", "talk", "audio", "assistant"],
  },
  {
    href: "/education", label: "Education", group: "Learn",
    note: "Courses from beginner to expert",
    keywords: ["learn", "lessons", "courses", "teach"],
  },
  {
    href: "/games", label: "Games", group: "Learn",
    note: "FinWordle and chart patterns",
    keywords: ["finwordle", "wordle", "patterns", "play"],
  },
];

export const DESTINATIONS: Destination[] = RAW.map((d, i) => ({
  ...d,
  figure: String(i + 1).padStart(2, "0"),
}));

export const PRIMARY_DESTINATIONS = DESTINATIONS.filter((d) => d.primary);

export const GROUPS = ["Portfolio", "Research", "Learn"] as const;

/** Current page, by the same rule every surface should use. */
export function isCurrent(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Where a locked destination sends you instead. */
export function lockedHref(d: Destination): string {
  return `/upgrade?feature=${d.href.slice(1)}&required_tier=${d.tier}`;
}

/**
 * A query that names a ticker rather than a destination.
 *
 * One to five letters, which covers every US listing, and deliberately
 * not applied to anything that already matches a destination by name:
 * typing "games" should offer Games, not propose analysing GAMES.
 */
export function asTickerQuery(query: string): string | null {
  const clean = query.trim().toUpperCase();
  if (!/^[A-Z]{1,5}$/.test(clean)) return null;
  const collides = DESTINATIONS.some((d) => d.label.toUpperCase().startsWith(clean));
  return collides && clean.length < 3 ? null : clean;
}
