"use client";
import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Bell, Plus } from "lucide-react";
import { MetricCard, PositionTable } from "@/components/dashboard/DashboardWidgets";
import AddPositionModal from "@/components/dashboard/AddPositionModal";
import DailyLesson from "@/components/dashboard/DailyLesson";
import PriceChart from "@/components/charts/PriceChart";
import PortfolioDonut from "@/components/charts/PortfolioDonut";
import AlertFeed from "@/components/AlertFeed";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ensureDefaultPortfolio, listHoldings } from "@/lib/api";
import type { Holding as ApiHolding } from "@/lib/api";
import type { Holding } from "@/types";

const DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"];

function toDisplayHolding(h: ApiHolding): Holding {
  return {
    id: h.id, ticker: h.ticker, quantity: h.quantity, average_cost_basis: h.average_cost_basis,
    current_price: h.current_price, current_weight: h.current_weight, beta: h.beta,
  };
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";

  const [portfolioId, setPortfolioId] = useState<string | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [totals, setTotals] = useState({ totalValue: 0, pnl: 0, pnlPct: 0 });
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingHolding, setEditingHolding] = useState<Holding | null>(null);
  const [activeTicker, setActiveTicker] = useState("AAPL");

  const loadPortfolio = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const { portfolio_id } = await ensureDefaultPortfolio(userId);
      setPortfolioId(portfolio_id);
      const data = await listHoldings(portfolio_id);
      setHoldings(data.holdings.map(toDisplayHolding));
      setTotals({ totalValue: data.total_value, pnl: data.total_pnl, pnlPct: data.total_pnl_pct });
    } catch (e) {
      console.error("Failed to load portfolio:", e);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { loadPortfolio(); }, [loadPortfolio]);

  const chartTickers = holdings.length > 0 ? holdings.map((h) => h.ticker).slice(0, 6) : DEFAULT_TICKERS;

  return (
    <div className="space-y-6">
      {showAddModal && portfolioId && (
        <AddPositionModal
          portfolioId={portfolioId}
          userId={userId}
          onClose={() => setShowAddModal(false)}
          onAdded={loadPortfolio}
        />
      )}

      {editingHolding && portfolioId && (
        <AddPositionModal
          portfolioId={portfolioId}
          userId={userId}
          editingHolding={editingHolding}
          onClose={() => setEditingHolding(null)}
          onAdded={loadPortfolio}
        />
      )}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl text-aureus-text" style={{ fontWeight: 600 }}>Portfolio Intelligence</h1>
          <p className="text-aureus-muted text-sm mt-0.5">
            {new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button size="sm" onClick={() => setShowAddModal(true)} disabled={!portfolioId}>
            <Plus className="w-4 h-4 mr-1" /> Add Position
          </Button>
          <div className="flex items-center gap-2 text-xs border border-aureus-border rounded px-3 py-1.5"
               style={{ background: "var(--surface)" }}>
            <div className="w-2 h-2 rounded-full bg-aureus-green pulse-gold" />
            <span className="text-aureus-muted">Live</span>
          </div>
        </div>
      </div>

      {/* Daily lesson */}
      <DailyLesson userId={userId} />

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Portfolio Value"
          value={loading ? "…" : `$${totals.totalValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={holdings.length === 0 ? "No positions yet" : "Live pricing"}
        />
        <MetricCard
          label="Total P&L"
          value={loading ? "…" : `${totals.pnl >= 0 ? "+" : ""}$${Math.abs(totals.pnl).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={holdings.length === 0 ? "—" : `${totals.pnlPct >= 0 ? "+" : ""}${totals.pnlPct.toFixed(2)}% all-time`}
          trend={totals.pnl >= 0 ? "up" : "down"}
        />
        <MetricCard label="Positions" value={loading ? "…" : String(holdings.length)} sub={holdings.length === 0 ? "Add your first position" : "Tracked"} />
        <MetricCard label="Data Source" value="Polygon" sub="Real-time via fallback chain" />
      </div>

      {/* Main content: chart + alerts */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle>Price Chart & Signals</CardTitle>
              <div className="flex gap-1 flex-wrap justify-end">
                {chartTickers.map((t) => (
                  <button key={t} onClick={() => setActiveTicker(t)}
                          className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                            activeTicker === t ? "bg-aureus-gold text-black" : "text-aureus-muted hover:text-white"
                          }`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <PriceChart ticker={activeTicker} horizon="medium_term" />
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Bell className="w-3 h-3" /> Alerts & News</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="h-[420px] overflow-y-auto px-4 pb-4">
              <AlertFeed userId={userId} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Portfolio allocation + positions */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle>Allocation</CardTitle></CardHeader>
          <CardContent>
            {holdings.length > 0
              ? <PortfolioDonut holdings={holdings} />
              : <p className="text-aureus-muted text-sm text-center py-8">Add a position to see allocation</p>}
          </CardContent>
        </Card>

        <Card className="col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Positions</CardTitle>
            {holdings.length > 0 && <span className="text-[10px] text-aureus-muted normal-case">Click a row to edit or remove</span>}
          </CardHeader>
          <CardContent className="p-0 pb-2">
            {loading ? (
              <p className="text-center py-10 text-aureus-muted text-sm">Loading positions...</p>
            ) : (
              <PositionTable holdings={holdings} onEditHolding={setEditingHolding} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
