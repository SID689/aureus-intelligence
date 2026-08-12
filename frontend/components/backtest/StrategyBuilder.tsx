"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { StrategyBacktestRequest } from "@/lib/api";

interface Props {
  onRun: (req: StrategyBacktestRequest) => void;
  running: boolean;
}

const FIELD_LABEL = "text-xs text-aureus-muted mb-1 block";
const FIELD_INPUT =
  "w-full rounded-md border border-aureus-border px-3 py-2 text-sm text-white placeholder:text-aureus-muted/50 " +
  "focus:outline-none focus:border-aureus-gold transition-colors";
const FIELD_STYLE = { background: "var(--bg)" };

export default function StrategyBuilder({ onRun, running }: Props) {
  const [tickers, setTickers] = useState("AAPL");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [frequency, setFrequency] = useState<"1d" | "1h" | "5m">("1d");

  const [initialCapital, setInitialCapital] = useState("10000");
  const [maxPositionPct, setMaxPositionPct] = useState("100");
  const [commissionPct, setCommissionPct] = useState("0.1");
  const [slippagePct, setSlippagePct] = useState("0.05");

  const [ruleType, setRuleType] = useState<"rsi" | "ma_crossover">("rsi");
  const [rsiPeriod, setRsiPeriod] = useState("14");
  const [rsiBuyBelow, setRsiBuyBelow] = useState("30");
  const [rsiSellAbove, setRsiSellAbove] = useState("70");
  const [fastPeriod, setFastPeriod] = useState("20");
  const [slowPeriod, setSlowPeriod] = useState("50");
  const [maType, setMaType] = useState<"sma" | "ema">("sma");

  const [useStopLoss, setUseStopLoss] = useState(true);
  const [stopLossPct, setStopLossPct] = useState("7");
  const [useTakeProfit, setUseTakeProfit] = useState(true);
  const [takeProfitPct, setTakeProfitPct] = useState("15");
  const [allowShort, setAllowShort] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const tickerList = tickers.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);
    if (tickerList.length === 0) { setError("Enter at least one ticker."); return; }
    if (tickerList.length > 5) { setError("Up to 5 tickers per backtest."); return; }
    if (new Date(endDate) <= new Date(startDate)) { setError("End date must be after start date."); return; }

    const rule: StrategyBacktestRequest["rule"] =
      ruleType === "rsi"
        ? { type: "rsi", period: Number(rsiPeriod), buy_below: Number(rsiBuyBelow), sell_above: Number(rsiSellAbove) }
        : { type: "ma_crossover", fast_period: Number(fastPeriod), slow_period: Number(slowPeriod), ma_type: maType };

    onRun({
      tickers: tickerList,
      start_date: startDate,
      end_date: endDate,
      frequency,
      initial_capital: Number(initialCapital),
      max_position_pct: Number(maxPositionPct) / 100,
      commission_pct: Number(commissionPct) / 100,
      slippage_pct: Number(slippagePct) / 100,
      rule,
      stop_loss_pct: useStopLoss ? Number(stopLossPct) / 100 : null,
      take_profit_pct: useTakeProfit ? Number(takeProfitPct) / 100 : null,
      allow_short: allowShort,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && (
        <div className="rounded-lg border border-aureus-red bg-red-950/20 p-3 text-aureus-red text-xs">{error}</div>
      )}

      {/* Assets & timeframe */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-aureus-gold uppercase tracking-wider">Assets &amp; Timeframe</h4>
        <div>
          <label className={FIELD_LABEL}>Ticker(s) — comma-separated, up to 5</label>
          <input value={tickers} onChange={(e) => setTickers(e.target.value)}
                 placeholder="AAPL, MSFT" className={FIELD_INPUT} style={FIELD_STYLE} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={FIELD_LABEL}>Start Date</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                   className={FIELD_INPUT} style={FIELD_STYLE} />
          </div>
          <div>
            <label className={FIELD_LABEL}>End Date</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                   className={FIELD_INPUT} style={FIELD_STYLE} />
          </div>
        </div>
        <div>
          <label className={FIELD_LABEL}>Candle Interval</label>
          <select value={frequency} onChange={(e) => setFrequency(e.target.value as typeof frequency)}
                  className={FIELD_INPUT} style={FIELD_STYLE}>
            <option value="1d">Daily</option>
            <option value="1h">1 Hour</option>
            <option value="5m">5 Minute</option>
          </select>
        </div>
      </div>

      {/* Strategy rule */}
      <div className="space-y-3 pt-1 border-t border-aureus-border/50">
        <h4 className="text-xs font-semibold text-aureus-gold uppercase tracking-wider pt-3">Entry / Exit Rule</h4>
        <div className="flex gap-2">
          {(["rsi", "ma_crossover"] as const).map((rt) => (
            <button key={rt} type="button" onClick={() => setRuleType(rt)}
                    className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                      ruleType === rt
                        ? "border-aureus-gold text-aureus-gold bg-aureus-gold/10"
                        : "border-aureus-border text-aureus-muted hover:text-white"
                    }`}>
              {rt === "rsi" ? "RSI Threshold" : "MA Crossover"}
            </button>
          ))}
        </div>

        {ruleType === "rsi" ? (
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={FIELD_LABEL}>RSI Period</label>
              <input type="number" value={rsiPeriod} onChange={(e) => setRsiPeriod(e.target.value)}
                     min={2} max={100} className={FIELD_INPUT} style={FIELD_STYLE} />
            </div>
            <div>
              <label className={FIELD_LABEL}>Buy Below</label>
              <input type="number" value={rsiBuyBelow} onChange={(e) => setRsiBuyBelow(e.target.value)}
                     min={0} max={100} className={FIELD_INPUT} style={FIELD_STYLE} />
            </div>
            <div>
              <label className={FIELD_LABEL}>Sell Above</label>
              <input type="number" value={rsiSellAbove} onChange={(e) => setRsiSellAbove(e.target.value)}
                     min={0} max={100} className={FIELD_INPUT} style={FIELD_STYLE} />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={FIELD_LABEL}>Fast Period</label>
              <input type="number" value={fastPeriod} onChange={(e) => setFastPeriod(e.target.value)}
                     min={2} max={200} className={FIELD_INPUT} style={FIELD_STYLE} />
            </div>
            <div>
              <label className={FIELD_LABEL}>Slow Period</label>
              <input type="number" value={slowPeriod} onChange={(e) => setSlowPeriod(e.target.value)}
                     min={3} max={400} className={FIELD_INPUT} style={FIELD_STYLE} />
            </div>
            <div>
              <label className={FIELD_LABEL}>MA Type</label>
              <select value={maType} onChange={(e) => setMaType(e.target.value as typeof maType)}
                      className={FIELD_INPUT} style={FIELD_STYLE}>
                <option value="sma">SMA</option>
                <option value="ema">EMA</option>
              </select>
            </div>
          </div>
        )}

        <label className="flex items-center gap-2 text-xs text-aureus-muted pt-1">
          <input type="checkbox" checked={allowShort} onChange={(e) => setAllowShort(e.target.checked)}
                 className="accent-aureus-gold" />
          Allow short positions (sell signal opens a short, not just exits a long)
        </label>
      </div>

      {/* Risk management */}
      <div className="space-y-3 pt-1 border-t border-aureus-border/50">
        <h4 className="text-xs font-semibold text-aureus-gold uppercase tracking-wider pt-3">Risk Management</h4>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="flex items-center gap-2 text-xs text-aureus-muted mb-1">
              <input type="checkbox" checked={useStopLoss} onChange={(e) => setUseStopLoss(e.target.checked)}
                     className="accent-aureus-gold" />
              Stop-Loss %
            </label>
            <input type="number" value={stopLossPct} onChange={(e) => setStopLossPct(e.target.value)}
                   disabled={!useStopLoss} min={0.1} max={100} step="any"
                   className={FIELD_INPUT + " disabled:opacity-40"} style={FIELD_STYLE} />
          </div>
          <div>
            <label className="flex items-center gap-2 text-xs text-aureus-muted mb-1">
              <input type="checkbox" checked={useTakeProfit} onChange={(e) => setUseTakeProfit(e.target.checked)}
                     className="accent-aureus-gold" />
              Take-Profit %
            </label>
            <input type="number" value={takeProfitPct} onChange={(e) => setTakeProfitPct(e.target.value)}
                   disabled={!useTakeProfit} min={0.1} max={500} step="any"
                   className={FIELD_INPUT + " disabled:opacity-40"} style={FIELD_STYLE} />
          </div>
        </div>
      </div>

      {/* Capital & sizing */}
      <div className="space-y-3 pt-1 border-t border-aureus-border/50">
        <h4 className="text-xs font-semibold text-aureus-gold uppercase tracking-wider pt-3">Capital &amp; Sizing</h4>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={FIELD_LABEL}>Initial Capital ($)</label>
            <input type="number" value={initialCapital} onChange={(e) => setInitialCapital(e.target.value)}
                   min={100} className={FIELD_INPUT} style={FIELD_STYLE} />
          </div>
          <div>
            <label className={FIELD_LABEL}>Max Position Size (%)</label>
            <input type="number" value={maxPositionPct} onChange={(e) => setMaxPositionPct(e.target.value)}
                   min={1} max={100} className={FIELD_INPUT} style={FIELD_STYLE} />
          </div>
          <div>
            <label className={FIELD_LABEL}>Commission (% per side)</label>
            <input type="number" value={commissionPct} onChange={(e) => setCommissionPct(e.target.value)}
                   min={0} max={5} step="any" className={FIELD_INPUT} style={FIELD_STYLE} />
          </div>
          <div>
            <label className={FIELD_LABEL}>Slippage (%)</label>
            <input type="number" value={slippagePct} onChange={(e) => setSlippagePct(e.target.value)}
                   min={0} max={5} step="any" className={FIELD_INPUT} style={FIELD_STYLE} />
          </div>
        </div>
      </div>

      <Button type="submit" disabled={running} size="lg" className="w-full">
        {running ? "Running Backtest…" : "Run Backtest"}
      </Button>
    </form>
  );
}
