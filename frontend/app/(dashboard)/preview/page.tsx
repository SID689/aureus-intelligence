"use client";
/**
 * Design preview harness for the portfolio dashboard.
 *
 * Three complete layout treatments over the SAME live data, swapped with
 * one click so they can be compared like for like rather than from memory.
 * Nothing here is wired into navigation and nothing in the shipped app
 * imports it — the whole experiment is `app/(dashboard)/preview/` plus
 * `components/dashboard/previews/`, and deleting those two paths returns
 * the app to exactly its current state.
 *
 * The real dashboard at app/(dashboard)/page.tsx is untouched.
 */
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { ensureDefaultPortfolio, listHoldings } from "@/lib/api";
import type { Holding as ApiHolding } from "@/lib/api";
import type { Holding } from "@/types";
import AddPositionModal from "@/components/dashboard/AddPositionModal";
import Broadsheet from "@/components/dashboard/previews/Broadsheet";
import Tape from "@/components/dashboard/previews/Tape";
import Ledger from "@/components/dashboard/previews/Ledger";
import type { VariantProps } from "@/components/dashboard/previews/kit";

const FALLBACK_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"];

const VARIANTS: {
  key: string;
  letter: string;
  name: string;
  blurb: string;
  swatch: string;
  Component: (props: VariantProps) => React.JSX.Element;
}[] = [
  {
    key: "broadsheet", letter: "A", name: "Broadsheet",
    blurb: "Light paper ground · editorial rules · one dominant figure",
    swatch: "#efeade",
    Component: Broadsheet,
  },
  {
    key: "tape", letter: "B", name: "Tape",
    blurb: "Dark, brightened · live ticker tape · dense terminal rows",
    swatch: "#191d12",
    Component: Tape,
  },
  {
    key: "ledger", letter: "C", name: "Ledger",
    blurb: "Warm graphite · raised sheets · statement-of-account framing",
    swatch: "#272a20",
    Component: Ledger,
  },
];

/**
 * The API holding carries `last_priced_at`, which the display type does
 * not. Variants get the display shape; AddPositionModal is handed the
 * original API record, so neither side is fed a structurally wrong object.
 */
function toDisplayHolding(h: ApiHolding): Holding {
  return {
    id: h.id, ticker: h.ticker, quantity: h.quantity,
    average_cost_basis: h.average_cost_basis, current_price: h.current_price,
    current_weight: h.current_weight, beta: h.beta,
  };
}

function PreviewHarness() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";
  const router = useRouter();
  const params = useSearchParams();

  const fromUrl = params.get("v");
  const [variant, setVariant] = useState(
    VARIANTS.some((v) => v.key === fromUrl) ? (fromUrl as string) : "broadsheet"
  );

  const [portfolioId, setPortfolioId] = useState<string | null>(null);
  const [apiHoldings, setApiHoldings] = useState<ApiHolding[]>([]);
  const [totals, setTotals] = useState({ totalValue: 0, pnl: 0, pnlPct: 0 });
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<ApiHolding | null>(null);
  const [activeTicker, setActiveTicker] = useState("AAPL");

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const { portfolio_id } = await ensureDefaultPortfolio(userId);
      setPortfolioId(portfolio_id);
      const data = await listHoldings(portfolio_id);
      setApiHoldings(data.holdings);
      setTotals({ totalValue: data.total_value, pnl: data.total_pnl, pnlPct: data.total_pnl_pct });
      // Open on the largest position rather than a hardcoded AAPL that may
      // not be held — a preview of your dashboard should show your data.
      if (data.holdings.length) {
        const largest = [...data.holdings].sort(
          (a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0)
        )[0];
        setActiveTicker(largest.ticker);
      }
    } catch (e) {
      console.error("Preview: failed to load portfolio", e);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  const holdings = useMemo(() => apiHoldings.map(toDisplayHolding), [apiHoldings]);

  // Keep the URL in step so a chosen variant survives a reload and can be
  // linked to directly (/preview?v=ledger).
  const choose = (key: string) => {
    setVariant(key);
    router.replace(`/preview?v=${key}`, { scroll: false });
  };

  const tickers = holdings.length ? holdings.map((h) => h.ticker).slice(0, 6) : FALLBACK_TICKERS;
  const active = VARIANTS.find((v) => v.key === variant) ?? VARIANTS[0];
  const Variant = active.Component;

  return (
    <div>
      {showAdd && portfolioId && (
        <AddPositionModal
          portfolioId={portfolioId} userId={userId}
          onClose={() => setShowAdd(false)} onAdded={load}
        />
      )}
      {editing && portfolioId && (
        <AddPositionModal
          portfolioId={portfolioId} userId={userId} editingHolding={editing}
          onClose={() => setEditing(null)} onAdded={load}
        />
      )}

      {/* ── Switcher ─────────────────────────────────────────────────
          Deliberately neutral chrome in the CURRENT theme, so it reads as
          tooling sitting on top of the page rather than as part of any
          variant's design. */}
      <div className="-mx-6 -mt-6 mb-6 px-6 py-3 sticky top-0 z-30 backdrop-blur"
           style={{ background: "rgba(11,13,9,0.92)", borderBottom: "1px solid var(--rule)" }}>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <span className="text-[10px] uppercase tracking-[0.2em] text-aureus-muted">
            Design preview
          </span>
          <div className="flex flex-wrap gap-2">
            {VARIANTS.map((v) => {
              const on = v.key === variant;
              return (
                <button
                  key={v.key}
                  onClick={() => choose(v.key)}
                  className={`flex items-center gap-2.5 pl-2 pr-3.5 py-1.5 rounded-md border text-left transition-colors ${
                    on ? "border-aureus-gold" : "border-aureus-rule hover:border-aureus-muted"
                  }`}
                  style={{ background: on ? "rgba(184,147,90,0.10)" : "transparent" }}
                >
                  <span
                    className="w-6 h-6 rounded flex items-center justify-center text-[11px] font-mono-num font-semibold"
                    style={{
                      background: v.swatch,
                      color: v.key === "broadsheet" ? "#15180f" : "#f1ede1",
                      border: "1px solid var(--rule)",
                    }}
                  >
                    {v.letter}
                  </span>
                  <span>
                    <span className={`block text-[13px] leading-tight ${on ? "text-aureus-gold" : "text-aureus-text"}`}>
                      {v.name}
                    </span>
                    <span className="block text-[10px] leading-tight text-aureus-muted mt-0.5">
                      {v.blurb}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          <a href="/" className="ml-auto text-xs text-aureus-muted hover:text-aureus-gold transition-colors">
            ← Back to the current dashboard
          </a>
        </div>
      </div>

      <Variant
        userId={userId}
        holdings={holdings}
        totals={totals}
        loading={loading}
        tickers={tickers}
        activeTicker={activeTicker}
        onSelectTicker={setActiveTicker}
        onAdd={() => setShowAdd(true)}
        onEdit={(h) => setEditing(apiHoldings.find((a) => a.id === h.id) ?? null)}
      />
    </div>
  );
}

/**
 * useSearchParams() opts the subtree into client-side rendering, and Next
 * fails the production build unless it sits under a Suspense boundary.
 */
export default function PreviewPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-aureus-muted text-sm">Loading preview…</div>}>
      <PreviewHarness />
    </Suspense>
  );
}
