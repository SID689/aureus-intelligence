"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import StrategyBuilder from "@/components/backtest/StrategyBuilder";
import ResultsOverviewCards from "@/components/backtest/ResultsOverviewCards";
import EquityCurveChart from "@/components/backtest/EquityCurveChart";
import TradesTable from "@/components/backtest/TradesTable";
import { runStrategyBacktest } from "@/lib/api";
import type { StrategyBacktestRequest, StrategyBacktestResult } from "@/lib/api";

export default function BacktestPage() {
  const [result, setResult] = useState<StrategyBacktestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async (req: StrategyBacktestRequest) => {
    setRunning(true);
    setError(null);
    try {
      const res = await runStrategyBacktest(req);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Backtest failed — check the backend is reachable and the date range has historical data available.");
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Strategy Backtesting</h1>
        <p className="text-aureus-muted text-sm mt-0.5">
          Define a rule-based trading strategy and simulate it against historical price data —
          full trade log, equity curve vs. S&amp;P 500, and institutional performance metrics.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 items-start">
        <Card>
          <CardHeader>
            <CardTitle>Strategy Builder</CardTitle>
          </CardHeader>
          <CardContent>
            <StrategyBuilder onRun={handleRun} running={running} />
          </CardContent>
        </Card>

        <div className="space-y-6">
          {error && (
            <div className="rounded-lg border border-aureus-red bg-red-950/20 p-4 text-aureus-red text-sm">
              {error}
            </div>
          )}

          {!result && !error && !running && (
            <Card>
              <CardContent className="p-16 text-center">
                <div className="text-4xl mb-3">📊</div>
                <p className="text-aureus-muted text-sm">
                  Configure a strategy on the left and click Run Backtest to see performance
                  metrics, an equity curve vs. the S&amp;P 500, and a full trade log here.
                </p>
              </CardContent>
            </Card>
          )}

          {running && (
            <Card>
              <CardContent className="p-16 text-center">
                <p className="text-aureus-muted text-sm">Running backtest — simulating trade-by-trade execution…</p>
              </CardContent>
            </Card>
          )}

          {result && !running && (
            <>
              <ResultsOverviewCards summary={result.summary} />

              <Card>
                <CardHeader>
                  <CardTitle>Equity Curve — Strategy vs. S&amp;P 500</CardTitle>
                </CardHeader>
                <CardContent>
                  <EquityCurveChart points={result.equity_curve} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Trade Log</CardTitle>
                </CardHeader>
                <CardContent>
                  <TradesTable trades={result.trades} />
                </CardContent>
              </Card>

              {(result.config.tickers as string[])?.length > 0 && (
                <p className="text-xs text-aureus-muted px-1">
                  Backtest of {(result.config.tickers as string[]).join(", ")} from{" "}
                  {result.config.start_date as string} to {result.config.end_date as string}.
                  Past performance does not indicate future results. This is not financial advice.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
