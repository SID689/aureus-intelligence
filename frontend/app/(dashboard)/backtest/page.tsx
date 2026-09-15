"use client";
import { useState } from "react";
import { LoadingRegion, Skeleton, SkeletonChart, SkeletonLines, SkeletonList, SkeletonPageHeader, SkeletonSheet, SkeletonStatColumns } from "@/components/ui/Skeleton";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorNote, Note, PageHeader } from "@/components/ui/primitives";
import StrategyBuilder from "@/components/backtest/StrategyBuilder";
import ResultsOverviewCards from "@/components/backtest/ResultsOverviewCards";
import EquityCurveChart from "@/components/backtest/EquityCurveChart";
import TradesTable from "@/components/backtest/TradesTable";
import { useSession } from "next-auth/react";
import { runStrategyBacktest } from "@/lib/api";
import type { StrategyBacktestRequest, StrategyBacktestResult } from "@/lib/api";

export default function BacktestPage() {
  const { data: session } = useSession();
  const userId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const [result, setResult] = useState<StrategyBacktestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async (req: Omit<StrategyBacktestRequest, "user_id">) => {
    setRunning(true);
    setError(null);
    try {
      const res = await runStrategyBacktest({ ...req, user_id: userId });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Backtest failed, check the backend is reachable and the date range has historical data available.");
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Backtesting"
        lead="Define a rule-based strategy and simulate it trade by trade against historical prices:
              full execution log, equity curve against the S&amp;P 500, and the performance statistics
              an allocator would actually ask for."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 items-start">
        <Card>
          <CardHeader>
            <CardTitle>Strategy builder</CardTitle>
          </CardHeader>
          <CardContent>
            <StrategyBuilder onRun={handleRun} running={running} />
          </CardContent>
        </Card>

        <div className="space-y-6">
          {error && (
            <ErrorNote>{error}</ErrorNote>
          )}

          {!result && !error && !running && (
            <Card flat>
              <EmptyState title="No backtest run yet">
                Configure a strategy on the left and run it. Performance statistics, an equity
                curve against the S&amp;P 500, and every simulated trade will appear here.
              </EmptyState>
            </Card>
          )}

          {running && (
            <Card flat>
              <CardContent><LoadingRegion label="Simulating trade-by-trade execution" className="space-y-5"><SkeletonStatColumns columns={4} /><SkeletonChart height={240} /></LoadingRegion></CardContent>
            </Card>
          )}

          {result && !running && (
            <>
              <ResultsOverviewCards summary={result.summary} />

              <Card>
                <CardHeader>
                  <CardTitle>Equity curve: strategy vs. S&amp;P 500</CardTitle>
                </CardHeader>
                <CardContent>
                  <EquityCurveChart points={result.equity_curve} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Trade log</CardTitle>
                </CardHeader>
                <CardContent>
                  <TradesTable trades={result.trades} />
                </CardContent>
              </Card>

              {(result.config.tickers as string[])?.length > 0 && (
                <Note>
                  Backtest of {(result.config.tickers as string[]).join(", ")} from{" "}
                  {result.config.start_date as string} to {result.config.end_date as string}.
                  Simulated results carry no execution slippage beyond what the model applies, and
                  past performance does not indicate future results. Not financial advice.
                </Note>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
