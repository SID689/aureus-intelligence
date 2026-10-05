"use client";
/**
 * The phone's navigation: a bar at the bottom, under the thumb.
 *
 * The drawer this replaces needed two taps and a hand position most
 * people cannot reach one-handed on a modern phone, to show a list that
 * then covered the page it was navigating. Four destinations and a More
 * sheet sit permanently within reach instead, and nothing obscures the
 * content until you ask it to.
 *
 * Four is the limit, not a preference: a 375px screen divided five ways
 * leaves 75px a cell, and the fifth is the sheet.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { cn } from "@/lib/utils";
import { IconClose, IconLock, IconMenu, IconSearch } from "@/components/ui/icons";
import { DESTINATIONS, GROUPS, PRIMARY_DESTINATIONS, isCurrent, lockedHref } from "@/lib/navigation";
import { TIER_LABEL, asTier, meetsTier } from "@/lib/tiers";

export default function MobileTabBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const tier = asTier(session?.user?.tier);
  const [sheet, setSheet] = useState(false);

  // Following a link closes the sheet, so it never covers the page it
  // just opened.
  useEffect(() => { setSheet(false); }, [pathname]);

  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSheet(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sheet]);

  const secondary = DESTINATIONS.filter((d) => !d.primary);
  const inSheet = secondary.some((d) => isCurrent(pathname, d.href));

  return (
    <>
      {sheet && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/70" onClick={() => setSheet(false)}>
          <div
            className="absolute inset-x-0 bottom-0 bg-aureus-panel border-t border-aureus-rule shadow-overlay"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="All destinations"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-aureus-rule">
              <span className="label-caps">All destinations</span>
              <button
                onClick={() => setSheet(false)}
                aria-label="Close"
                className="tap-target p-1 text-aureus-muted hover:text-aureus-text"
              >
                <IconClose className="w-4 h-4" />
              </button>
            </div>

            <div className="max-h-[60vh] overflow-y-auto pb-[env(safe-area-inset-bottom)]">
              {GROUPS.map((group) => {
                const items = DESTINATIONS.filter((d) => d.group === group);
                if (!items.length) return null;
                return (
                  <div key={group}>
                    <div className="label-caps px-4 pt-4 pb-1.5">{group}</div>
                    {items.map((d) => {
                      const locked = !!d.tier && !meetsTier(tier, d.tier);
                      const active = isCurrent(pathname, d.href);
                      return (
                        <Link
                          key={d.href}
                          href={locked ? lockedHref(d) : d.href}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            "flex items-center gap-3 px-4 py-3.5 min-h-[52px] transition-colors",
                            active ? "bg-aureus-panelhigh text-aureus-text" : "text-aureus-soft active:bg-aureus-panellift",
                          )}
                        >
                          <span
                            className={cn(
                              "w-[22px] h-[22px] shrink-0 grid place-items-center rounded-sm border font-mono-num text-[10px] leading-none",
                              active ? "bg-aureus-gold border-aureus-gold text-aureus-ink" : "border-aureus-rule text-aureus-muted",
                            )}
                          >
                            {d.figure}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className={cn("block text-[14px]", locked && "text-aureus-muted")}>{d.label}</span>
                            <span className="block text-[11.5px] text-aureus-muted truncate">{d.note}</span>
                          </span>
                          {locked && (
                            <span className="shrink-0 flex items-center gap-1 label-caps text-[9px] text-aureus-golddim">
                              <IconLock className="w-3 h-3" />
                              {TIER_LABEL[d.tier!]}
                            </span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                );
              })}

              <div className="border-t border-aureus-rule mt-3">
                <Link href="/settings" className="flex items-center gap-3 px-4 py-3.5 min-h-[52px] text-[14px] text-aureus-soft">
                  <span className="w-[22px] h-[22px] grid place-items-center rounded-sm border border-aureus-rule font-mono-num text-[10px] text-aureus-muted">··</span>
                  Settings
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      <nav
        aria-label="Primary"
        className="lg:hidden fixed inset-x-0 bottom-0 z-30 flex items-stretch bg-aureus-panel border-t border-aureus-rule pb-[env(safe-area-inset-bottom)]"
      >
        {PRIMARY_DESTINATIONS.map((d) => {
          const locked = !!d.tier && !meetsTier(tier, d.tier);
          const active = isCurrent(pathname, d.href);
          return (
            <Link
              key={d.href}
              href={locked ? lockedHref(d) : d.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex-1 min-w-0 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] transition-colors",
                active ? "text-aureus-text" : "text-aureus-muted active:bg-aureus-panellift",
              )}
            >
              <span
                className={cn(
                  "w-[22px] h-[22px] grid place-items-center rounded-sm border font-mono-num text-[10px] leading-none",
                  active ? "bg-aureus-gold border-aureus-gold text-aureus-ink" : "border-aureus-rule text-aureus-muted",
                )}
              >
                {d.figure}
              </span>
              <span className="text-[10px] truncate max-w-full px-1">{d.short ?? d.label}</span>
              {locked && <span aria-hidden className="absolute top-1.5 right-1/2 translate-x-[18px] w-1 h-1 bg-aureus-golddim" />}
            </Link>
          );
        })}

        <button
          onClick={onOpenPalette}
          aria-label="Search"
          className="flex-1 min-w-0 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] text-aureus-muted active:bg-aureus-panellift transition-colors"
        >
          <span className="w-[22px] h-[22px] grid place-items-center rounded-sm border border-aureus-rule">
            <IconSearch className="w-3 h-3" />
          </span>
          <span className="text-[10px]">Search</span>
        </button>

        <button
          onClick={() => setSheet(true)}
          aria-label="All destinations"
          aria-expanded={sheet}
          className={cn(
            "flex-1 min-w-0 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] transition-colors",
            inSheet || sheet ? "text-aureus-text" : "text-aureus-muted active:bg-aureus-panellift",
          )}
        >
          <span
            className={cn(
              "w-[22px] h-[22px] grid place-items-center rounded-sm border",
              inSheet ? "bg-aureus-gold border-aureus-gold text-aureus-ink" : "border-aureus-rule",
            )}
          >
            <IconMenu className="w-3 h-3" />
          </span>
          <span className="text-[10px]">More</span>
        </button>
      </nav>
    </>
  );
}
