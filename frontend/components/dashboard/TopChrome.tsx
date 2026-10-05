"use client";
/**
 * The strip under the function row: a live tape, then a slim status rail
 * carrying the market phase and the standing disclaimer.
 *
 * The disclaimer is on every page and always visible, but it sits in the
 * rail with the other standing metadata rather than in a banner at body
 * size, where a legal notice would carry the same visual weight as the
 * product. The clock and phase live here at every width rather than in
 * the function row, which needs its horizontal space for the eight
 * destinations.
 */
import { usePortfolio } from "./PortfolioProvider";
import { TickerTape, StatusDot, useClock, useMounted } from "@/components/ui/primitives";
import { marketPhase } from "@/lib/format";

export default function TopChrome() {
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
    <>
      <TickerTape
        items={tape}
        note={loading ? "Loading positions" : "Tape is empty, add a position and it starts running."}
      />

      <div className="flex items-center gap-3 px-4 sm:px-6 py-1.5 bg-aureus-ink border-b border-aureus-rule">
        <span className="flex items-center gap-1.5 text-[11px] text-aureus-muted shrink-0">
          <StatusDot on={phase.open} />
          {phase.label}
        </span>
        <span className="hidden sm:inline font-mono-num text-[11px] text-aureus-muted shrink-0">
          {/* Blank until mounted: rendering a clock during SSR and again on
              the client produces two different strings and React logs a
              hydration mismatch for every one. */}
          {mounted ? now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : " "}
        </span>

        <span className="ml-auto text-[10px] text-aureus-muted/80 truncate text-right">
          Informational only · not financial advice · past performance does not indicate future results
        </span>
      </div>
    </>
  );
}
