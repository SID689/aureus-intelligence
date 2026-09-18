"use client";
/**
 * The strip above every dashboard page: a live tape, then a slim status
 * rail carrying the market phase, the clock, and the disclaimer.
 *
 * The disclaimer used to be a centred banner in body-sized text, which
 * gave a legal notice the same visual weight as the product. It is still
 * on every page and still always visible — it just sits in the rail with
 * the other standing metadata, where a status bar belongs.
 */
import { IconMenu } from "@/components/ui/icons";
import { usePortfolio } from "./PortfolioProvider";
import { TickerTape, StatusDot, useClock, useMounted } from "@/components/ui/primitives";
import { marketPhase } from "@/lib/format";
import NotificationBell from "@/components/notifications/NotificationBell";
import DemoBanner from "@/components/demo/DemoBanner";

export default function TopChrome({ onOpenNav }: { onOpenNav?: () => void }) {
  const { holdings, loading } = usePortfolio();
  const now = useClock();
  const mounted = useMounted();
  const phase = marketPhase(now);

  const tape = holdings.map((h) => ({
    ticker: h.ticker,
    price: h.current_price,
    changePct:
      h.current_price != null && h.average_cost_basis > 0
        ? ((h.current_price - h.average_cost_basis) / h.average_cost_basis) * 100
        : null,
  }));

  return (
    <div className="sticky top-0 z-20">
      {/* Inside the sticky block, so the demo label does not scroll away
          from the app it is labelling. Renders nothing for real sessions. */}
      <DemoBanner />
      <TickerTape
        items={tape}
        note={loading ? "Loading positions" : "Tape is empty, add a position and it starts running."}
      />

      <div className="flex items-center gap-3 px-4 sm:px-6 py-1.5 bg-aureus-ink border-b border-aureus-rule">
        {onOpenNav && (
          <button
            onClick={onOpenNav}
            className="tap-target md:hidden -ml-1 p-1 text-aureus-muted hover:text-aureus-text"
            aria-label="Open navigation"
          >
            <IconMenu className="w-4 h-4" />
          </button>
        )}

        <span className="flex items-center gap-1.5 text-[11px] text-aureus-muted shrink-0">
          <StatusDot on={phase.open} />
          {phase.label}
        </span>

        <span className="hidden sm:inline text-aureus-rule">·</span>
        <span className="hidden sm:inline font-mono-num text-[11px] text-aureus-muted shrink-0">
          {/* Blank until mounted: rendering a clock during SSR and again on
              the client produces two different strings and React logs a
              hydration mismatch for every one. */}
          {mounted ? now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : " "}
        </span>

        <span className="ml-auto text-[10px] text-aureus-muted/80 truncate text-right">
          Informational only · not financial advice · past performance does not indicate future results
        </span>

        <NotificationBell />
      </div>
    </div>
  );
}
