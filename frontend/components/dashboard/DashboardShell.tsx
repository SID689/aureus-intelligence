"use client";
/**
 * App chrome for every authenticated page.
 *
 * Navigation used to be a 224px column down the left at every screen
 * size. It is now a function row across the top on a laptop, a tab bar
 * along the bottom on a phone, and a command palette on Cmd-K everywhere:
 * see FunctionRow, MobileTabBar and CommandPalette, each of which argues
 * its own case. What is left here is the frame they hang in.
 *
 * The whole width now belongs to the page, which is the point. This is a
 * product whose output is wide — price charts, a five-column board, a
 * four-plan matrix that used to need a sideways scroll to read.
 */
import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import CommandPalette from "./CommandPalette";
import FunctionRow from "./FunctionRow";
import MobileTabBar from "./MobileTabBar";
import TopChrome from "./TopChrome";
import { asTier } from "@/lib/tiers";

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = asTier(session?.user?.tier);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  // Navigating closes it, so following a result never leaves the overlay
  // sitting over the page it just opened.
  useEffect(() => { setPaletteOpen(false); }, [pathname]);

  // Cmd-K, or Ctrl-K away from a Mac. Bound here rather than inside the
  // palette so the shortcut works when the palette is closed, which is
  // the only time it is any use.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-aureus-ink">
      <header className="shrink-0 z-30">
        <FunctionRow onOpenPalette={openPalette} />
        <TopChrome />
      </header>

      <main className="flex-1 overflow-y-auto min-w-0">
        {/* The bottom padding clears the phone tab bar, which is fixed and
            would otherwise sit on top of the last row of every page. */}
        <div className="px-4 sm:px-6 py-6 pb-28 lg:pb-10 max-w-[1500px] mx-auto">{children}</div>
      </main>

      <MobileTabBar onOpenPalette={openPalette} />
      <CommandPalette open={paletteOpen} onClose={closePalette} tier={tier} />
    </div>
  );
}
