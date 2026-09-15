"use client";
/**
 * App chrome for every authenticated page.
 *
 * The sidebar used to be a fixed 224px column at every screen size, which
 * on a 375px phone left the content 147px of usable width and made every
 * dashboard page scroll sideways. Below `md` it is now a drawer over a
 * scrim; at `md` and up nothing about the desktop layout changed.
 */
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import Sidebar from "./Sidebar";
import TopChrome from "./TopChrome";

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);
  const pathname = usePathname();

  // Close the drawer on navigation, so following a link doesn't leave the
  // menu covering the page it just opened.
  useEffect(() => { setNavOpen(false); }, [pathname]);

  // Escape closes it too — a drawer with no keyboard exit is a trap.
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setNavOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-aureus-ink">
      {/* Desktop rail */}
      <div className="hidden md:flex h-full">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      <div
        className={cn(
          "md:hidden fixed inset-0 z-50 transition-opacity duration-200",
          navOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
      >
        <div className="absolute inset-0 bg-black/70" onClick={() => setNavOpen(false)} />
        <div
          className={cn(
            "absolute inset-y-0 left-0 shadow-overlay transition-transform duration-200",
            navOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          <Sidebar onNavigate={() => setNavOpen(false)} />
        </div>
      </div>

      <main className="flex-1 overflow-y-auto min-w-0">
        <TopChrome onOpenNav={() => setNavOpen(true)} />
        <div className="px-4 sm:px-6 py-6 max-w-[1500px] mx-auto">{children}</div>
      </main>
    </div>
  );
}
