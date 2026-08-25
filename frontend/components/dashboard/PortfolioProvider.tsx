"use client";
/**
 * One portfolio fetch, shared by everything that needs it.
 *
 * The ticker tape in the chrome and the dashboard page below it both want
 * the same holdings. Fetching in each would double the request on every
 * navigation and let the two drift apart — the tape showing one price
 * while the table beside it shows another. This loads once and hands the
 * same object to both.
 *
 * `reload` is exposed so mutations (adding or editing a position) can
 * refresh every consumer at once rather than only the panel that made
 * the change.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import { useSession } from "next-auth/react";
import { ensureDefaultPortfolio, listHoldings } from "@/lib/api";
import type { Holding as ApiHolding } from "@/lib/api";
import type { Holding } from "@/types";

export interface PortfolioTotals {
  totalValue: number;
  cost: number;
  pnl: number;
  pnlPct: number;
}

interface PortfolioState {
  userId: string;
  portfolioId: string | null;
  holdings: Holding[];
  /** The unmapped API records — AddPositionModal needs this exact shape. */
  apiHoldings: ApiHolding[];
  totals: PortfolioTotals;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

const EMPTY_TOTALS: PortfolioTotals = { totalValue: 0, cost: 0, pnl: 0, pnlPct: 0 };

const Ctx = createContext<PortfolioState>({
  userId: "", portfolioId: null, holdings: [], apiHoldings: [],
  totals: EMPTY_TOTALS, loading: true, error: null,
  reload: async () => {},
});

export function usePortfolio(): PortfolioState {
  return useContext(Ctx);
}

function toDisplayHolding(h: ApiHolding): Holding {
  return {
    id: h.id, ticker: h.ticker, quantity: h.quantity,
    average_cost_basis: h.average_cost_basis, current_price: h.current_price,
    current_weight: h.current_weight, beta: h.beta,
  };
}

export default function PortfolioProvider({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";

  const [portfolioId, setPortfolioId] = useState<string | null>(null);
  const [apiHoldings, setApiHoldings] = useState<ApiHolding[]>([]);
  const [totals, setTotals] = useState<PortfolioTotals>(EMPTY_TOTALS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!userId) return;
    setError(null);
    try {
      const { portfolio_id } = await ensureDefaultPortfolio(userId);
      setPortfolioId(portfolio_id);
      const data = await listHoldings(portfolio_id);
      setApiHoldings(data.holdings);
      setTotals({
        totalValue: data.total_value,
        cost: data.total_cost,
        pnl: data.total_pnl,
        pnlPct: data.total_pnl_pct,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load your portfolio");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    // Wait for the session before the first load, otherwise the request
    // goes out with an empty user id and comes back empty-handed.
    if (!userId) return;
    setLoading(true);
    reload();
  }, [userId, reload]);

  const holdings = useMemo(() => apiHoldings.map(toDisplayHolding), [apiHoldings]);

  const value = useMemo<PortfolioState>(
    () => ({ userId, portfolioId, holdings, apiHoldings, totals, loading, error, reload }),
    [userId, portfolioId, holdings, apiHoldings, totals, loading, error, reload]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
