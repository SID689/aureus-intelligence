"use client";
import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Activity, TrendingUp, Bell, Zap } from "lucide-react";
import { MetricCard } from "@/components/dashboard/DashboardWidgets";
import { PositionTable } from "@/components/dashboard/DashboardWidgets";
import PriceChart from "@/components/charts/PriceChart";
import PortfolioDonut from "@/components/charts/PortfolioDonut";
import AlertFeed from "@/components/AlertFeed";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { Holding } from "@/types";

const TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"];

// Mock holdings for display — replace with real API call
const MOCK_HOLDINGS: Holding[] = [
  { ticker: "AAPL", quantity: 10,  average_cost_basis: 175.00, current_price: 191.45, current_weight: 24.1, beta: 1.20 },
  { ticker: "MSFT", quantity: 5,   average_cost_basis: 380.00, current_price: 415.30, current_weight: 26.1, beta: 0.90 },
  { ticker: "NVDA", quantity: 8,   average_cost_basis: 650.00, current_price: 875.50, current_weight: 22.1, beta: 1.75 },
  { ticker: "TSLA", quantity: 12,  average_cost_basis: 200.00, current_price: 248.70, current_weight: 18.8, beta: 2.10 },
  { ticker: "AMZN", quantity: 4,   average_cost_basis: 178.00, current_price: 194.20, current_weight: 9.8,  beta: 1.15 },
];

function calcPortfolioMetrics(holdings: Holding[]) {
  let totalValue = 0, totalCost = 0;
  for (const h of holdings) {
    if (h.current_price) {
      totalValue += h.current_price    * h.quantity;
      totalCost  += h.average_cost_basis * h.quantity;
    }
  }
  const pnl    = totalValue - totalCost;
  const pnlPct = totalCost > 0 ? (pnl / totalCost) * 100 : 0;
  return { totalValue, pnl, pnlPct };
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const [activeTicker, setActiveTicker] = useState("AAPL");
  const userId = session?.user?.id ?? "00000000-0000-0000-0000-000000000001";

  const { totalValue, pnl, pnlPct } = calcPortfolioMetrics(MOCK_HOLDINGS);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio Intelligence</h1>
          <p className="text-aureus-muted text-sm mt-0.5">
            {new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs border border-aureus-border rounded px-3 py-1.5"
             style={{ background: "var(--surface)" }}>
          <div className="w-2 h-2 rounded-full bg-aureus-green pulse-gold" />
          <span className="text-aureus-muted">Live</span>
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Portfolio Value"
          value={`$${totalValue.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
          sub="Paper account"
        />
        <MetricCard
          label="Total P&L"
          value={`${pnl >= 0 ? "+" : ""}$${Math.abs(pnl).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
          sub={`${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}% all-time`}
          trend={pnl >= 0 ? "up" : "down"}
        />
        <MetricCard
          label="Active Strategies"
          value="1"
          sub="1 awaiting signal"
        />
        <MetricCard
          label="Unread Alerts"
          value="0"
          sub="All clear"
          trend="neutral"
        />
      </div>

      {/* Main content: chart + alerts */}
      <div className="grid grid-cols-3 gap-4">
        {/* Price chart (2/3 width) */}
        <Card className="col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle>Price Chart & Signals</CardTitle>
              {/* Ticker selector */}
              <div className="flex gap-1">
                {TICKERS.map((t) => (
                  <button
                    key={t}
                    onClick={() => setActiveTicker(t)}
                    className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                      activeTicker === t
                        ? "bg-aureus-gold text-black"
                        : "text-aureus-muted hover:text-white"
                    }`}
                  >
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

        {/* Live alerts (1/3 width) */}
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="w-3 h-3" /> Live Alerts
            </CardTitle>
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
        {/* Donut chart */}
        <Card>
          <CardHeader><CardTitle>Allocation</CardTitle></CardHeader>
          <CardContent>
            <PortfolioDonut holdings={MOCK_HOLDINGS} />
          </CardContent>
        </Card>

        {/* Positions table */}
        <Card className="col-span-2">
          <CardHeader><CardTitle>Positions</CardTitle></CardHeader>
          <CardContent className="p-0 pb-2">
            <PositionTable holdings={MOCK_HOLDINGS} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
