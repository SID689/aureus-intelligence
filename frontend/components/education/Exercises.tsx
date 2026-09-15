"use client";
/**
 * Interactive calculators embedded in lessons.
 *
 * Some ideas are about a RELATIONSHIP rather than a fact. "Fees compound
 * too" is a sentence you nod at; watching a 1% fee eat a quarter of a
 * forty-year balance as you drag a slider is a thing you remember. These
 * exist for the ideas in that second category.
 *
 * Design rules, so they teach rather than merely compute:
 *   · Every widget shows its WORKING, not just its answer. A number with
 *     no derivation is a magic box, and a magic box teaches nothing.
 *   · Defaults come from the lesson (Exercise.params), so the same widget
 *     opens at 30 years in a retirement lesson and 3 in a fee one.
 *   · Nothing is graded. These are for exploring; the drills are for
 *     testing, and mixing the two makes people afraid to experiment.
 */
import { useMemo, useState } from "react";
import { Figure } from "@/components/ui/primitives";
import { money, signed } from "@/lib/format";
import type { LessonExercise } from "@/lib/api";

// ── Shared controls ─────────────────────────────────────────────────────

function Slider({
  label, value, onChange, min, max, step = 1, format,
}: {
  label: string; value: number; onChange: (v: number) => void;
  min: number; max: number; step?: number; format: (v: number) => string;
}) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-3 mb-1.5">
        <span className="label-caps">{label}</span>
        <Figure className="text-[13px]">{format(value)}</Figure>
      </span>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--gold)] cursor-pointer"
        aria-label={label}
      />
    </label>
  );
}

/** The derivation. Without it a widget is a magic box. */
function Working({ lines }: { lines: string[] }) {
  return (
    <div className="mt-4 pt-3 border-t border-aureus-rulesoft space-y-1">
      {lines.map((l, i) => (
        <p key={i} className="text-[11px] text-aureus-muted font-mono-num leading-relaxed">{l}</p>
      ))}
    </div>
  );
}

function Readout({
  label, value, tone = "flat", sub,
}: {
  label: string; value: string; tone?: "up" | "down" | "flat"; sub?: string;
}) {
  return (
    <div>
      <div className="label-caps">{label}</div>
      <Figure tone={tone} className="block text-2xl mt-1">{value}</Figure>
      {sub && <div className="text-[11px] text-aureus-muted mt-0.5">{sub}</div>}
    </div>
  );
}

/** Tiny inline chart. Recharts would be heavier than the whole widget. */
function MiniCurve({ series, height = 90 }: { series: { values: number[]; color: string }[]; height?: number }) {
  const all = series.flatMap((s) => s.values);
  if (all.length < 2) return null;
  const max = Math.max(...all);
  const min = Math.min(...all, 0);
  const span = max - min || 1;
  const w = 100;

  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="w-full mt-3" style={{ height }}>
      {series.map((s, si) => {
        const step = w / (s.values.length - 1);
        const d = s.values
          .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(2)},${(height - ((v - min) / span) * (height - 4) - 2).toFixed(2)}`)
          .join(" ");
        return <path key={si} d={d} fill="none" stroke={s.color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />;
      })}
    </svg>
  );
}

// ── compounding ─────────────────────────────────────────────────────────

function Compounding({ p }: { p: Record<string, number> }) {
  const [principal, setPrincipal] = useState(p.principal ?? 10000);
  const [rate, setRate] = useState(p.rate ?? 7);
  const [years, setYears] = useState(p.years ?? 30);

  const path = useMemo(
    () => Array.from({ length: years + 1 }, (_, y) => principal * Math.pow(1 + rate / 100, y)),
    [principal, rate, years]
  );
  const final = path[path.length - 1];
  const contributed = principal;
  const growth = final - contributed;

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4">
        <Slider label="Starting amount" value={principal} onChange={setPrincipal} min={1000} max={200000} step={1000} format={(v) => money(v)} />
        <Slider label="Annual return" value={rate} onChange={setRate} min={0} max={15} step={0.5} format={(v) => `${v}%`} />
        <Slider label="Years" value={years} onChange={setYears} min={1} max={50} format={(v) => `${v}`} />
      </div>
      <MiniCurve series={[{ values: path, color: "var(--gold)" }]} />
      <div className="grid sm:grid-cols-3 gap-4">
        <Readout label="Final value" value={money(final)} />
        <Readout label="You put in" value={money(contributed)} sub="never changes" />
        <Readout label="Growth" value={money(growth)} tone="up" sub={`${(growth / contributed * 100).toFixed(0)}% of the total`} />
      </div>
      <Working lines={[
        `${money(principal)} x (1 + ${rate}%)^${years} = ${money(final)}`,
        `Doubling time ≈ 72 / ${rate} = ${rate > 0 ? (72 / rate).toFixed(1) : "—"} years`,
      ]} />
    </div>
  );
}

// ── fee_drag ────────────────────────────────────────────────────────────

function FeeDrag({ p }: { p: Record<string, number> }) {
  const [balance, setBalance] = useState(p.balance ?? 10000);
  const [ret, setRet] = useState(p.annual_return ?? 7);
  const [years, setYears] = useState(p.years ?? 30);
  const [feeA, setFeeA] = useState(p.fee_a ?? 0.03);
  const [feeB, setFeeB] = useState(p.fee_b ?? 0.75);

  const grow = (fee: number) =>
    Array.from({ length: years + 1 }, (_, y) => balance * Math.pow(1 + (ret - fee) / 100, y));

  const a = useMemo(() => grow(feeA), [balance, ret, years, feeA]);
  const b = useMemo(() => grow(feeB), [balance, ret, years, feeB]);
  const gap = a[a.length - 1] - b[b.length - 1];
  const gapPct = (gap / a[a.length - 1]) * 100;

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4">
        <Slider label="Balance" value={balance} onChange={setBalance} min={1000} max={500000} step={1000} format={(v) => money(v)} />
        <Slider label="Gross return" value={ret} onChange={setRet} min={1} max={12} step={0.5} format={(v) => `${v}%`} />
        <Slider label="Years" value={years} onChange={setYears} min={1} max={50} format={(v) => `${v}`} />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <Slider label="Fee A" value={feeA} onChange={setFeeA} min={0} max={2} step={0.01} format={(v) => `${v.toFixed(2)}%`} />
        <Slider label="Fee B" value={feeB} onChange={setFeeB} min={0} max={2} step={0.01} format={(v) => `${v.toFixed(2)}%`} />
      </div>
      <MiniCurve series={[
        { values: a, color: "var(--emerald)" },
        { values: b, color: "var(--crimson)" },
      ]} />
      <div className="grid sm:grid-cols-3 gap-4">
        <Readout label={`At ${feeA.toFixed(2)}%`} value={money(a[a.length - 1])} tone="up" />
        <Readout label={`At ${feeB.toFixed(2)}%`} value={money(b[b.length - 1])} tone="down" />
        <Readout label="Cost of the difference" value={money(gap)} tone="down"
                 sub={`${gapPct.toFixed(1)}% of the final balance`} />
      </div>
      <Working lines={[
        `A fee is subtracted from the return, then the remainder compounds:`,
        `(1 + ${ret}% − fee)^${years}`,
        `The ${(feeB - feeA).toFixed(2)}pp fee difference costs ${gapPct.toFixed(1)}% of the ending balance, not ${(feeB - feeA).toFixed(2)}%.`,
      ]} />
    </div>
  );
}

// ── drawdown_recovery ───────────────────────────────────────────────────

function DrawdownRecovery({ p }: { p: Record<string, number> }) {
  const [loss, setLoss] = useState(p.loss_pct ?? 25);
  const remaining = 1 - loss / 100;
  const required = remaining > 0 ? (1 / remaining - 1) * 100 : Infinity;

  return (
    <div className="space-y-4">
      <Slider label="Loss taken" value={loss} onChange={setLoss} min={1} max={90} format={(v) => `${v}%`} />
      <div className="grid sm:grid-cols-2 gap-4">
        <Readout label="You lose" value={`${loss}%`} tone="down" />
        <Readout label="Gain needed to break even"
                 value={Number.isFinite(required) ? `${required.toFixed(1)}%` : "—"} tone="up"
                 sub={required > loss * 1.5 ? "far more than the loss" : "roughly the loss"} />
      </div>
      {/* The asymmetry made visual: two bars, one clearly longer. */}
      <div className="space-y-2 pt-1">
        <div className="flex items-center gap-3">
          <span className="w-24 text-[11px] text-aureus-muted shrink-0">Loss</span>
          <span className="flex-1 h-2 rounded-sm bg-aureus-panelhigh overflow-hidden">
            <span className="block h-full bg-aureus-crimson" style={{ width: `${Math.min(100, loss)}%` }} />
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="w-24 text-[11px] text-aureus-muted shrink-0">Recovery</span>
          <span className="flex-1 h-2 rounded-sm bg-aureus-panelhigh overflow-hidden">
            <span className="block h-full bg-aureus-emerald"
                  style={{ width: `${Math.min(100, Number.isFinite(required) ? required : 100)}%` }} />
          </span>
        </div>
      </div>
      <Working lines={[
        `$100 − ${loss}% = ${(remaining * 100).toFixed(1)} remaining`,
        `100 / ${(remaining * 100).toFixed(1)} = ${Number.isFinite(required) ? (1 / remaining).toFixed(3) : "—"}, a ${Number.isFinite(required) ? required.toFixed(1) : "—"}% gain`,
        `The relationship is not linear: it accelerates sharply past 50%.`,
      ]} />
    </div>
  );
}

// ── position_size ───────────────────────────────────────────────────────

function PositionSize({ p }: { p: Record<string, number> }) {
  const [account, setAccount] = useState(p.account ?? 100000);
  const [riskPct, setRiskPct] = useState(p.risk_pct ?? 1);
  const [entry, setEntry] = useState(p.entry ?? 50);
  const [stop, setStop] = useState(p.stop ?? 45);

  const riskDollars = account * (riskPct / 100);
  const perShare = Math.max(0.01, entry - stop);
  const shares = Math.floor(riskDollars / perShare);
  const positionValue = shares * entry;
  const positionPct = (positionValue / account) * 100;

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <Slider label="Account value" value={account} onChange={setAccount} min={5000} max={1000000} step={5000} format={(v) => money(v)} />
        <Slider label="Risk per trade" value={riskPct} onChange={setRiskPct} min={0.25} max={5} step={0.25} format={(v) => `${v}%`} />
        <Slider label="Entry price" value={entry} onChange={setEntry} min={5} max={300} step={1} format={(v) => `$${v}`} />
        <Slider label="Stop price" value={stop} onChange={setStop} min={1} max={299} step={1} format={(v) => `$${v}`} />
      </div>
      <div className="grid sm:grid-cols-3 gap-4">
        <Readout label="Shares to buy" value={shares.toLocaleString()} />
        <Readout label="Position value" value={money(positionValue)}
                 sub={`${positionPct.toFixed(1)}% of the account`} />
        <Readout label="At risk if stopped" value={money(shares * perShare)} tone="down"
                 sub={`target was ${money(riskDollars)}`} />
      </div>
      {stop >= entry && (
        <p className="text-[12px] text-aureus-amber">
          The stop is at or above the entry: for a long position it belongs below.
        </p>
      )}
      <Working lines={[
        `Risk budget: ${money(account)} x ${riskPct}% = ${money(riskDollars)}`,
        `Risk per share: $${entry} − $${stop} = $${perShare.toFixed(2)}`,
        `Shares: ${money(riskDollars)} / $${perShare.toFixed(2)} = ${shares.toLocaleString()}`,
        `A TIGHTER stop permits a larger position at identical risk: size follows the stop, not conviction.`,
      ]} />
    </div>
  );
}

// ── expected_value ──────────────────────────────────────────────────────

function ExpectedValue({ p }: { p: Record<string, number> }) {
  const [winRate, setWinRate] = useState(p.win_rate ?? 70);
  const [avgWin, setAvgWin] = useState(p.avg_win ?? 1);
  const [avgLoss, setAvgLoss] = useState(p.avg_loss ?? 3);

  const ev = (winRate / 100) * avgWin - (1 - winRate / 100) * avgLoss;
  const breakEvenRate = (avgLoss / (avgWin + avgLoss)) * 100;

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4">
        <Slider label="Win rate" value={winRate} onChange={setWinRate} min={5} max={95} format={(v) => `${v}%`} />
        <Slider label="Average win" value={avgWin} onChange={setAvgWin} min={0.1} max={10} step={0.1} format={(v) => `${v.toFixed(1)}R`} />
        <Slider label="Average loss" value={avgLoss} onChange={setAvgLoss} min={0.1} max={10} step={0.1} format={(v) => `${v.toFixed(1)}R`} />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <Readout label="Expected value per trade" value={`${signed(ev, 2)}R`} tone={ev >= 0 ? "up" : "down"}
                 sub={ev >= 0 ? "profitable over many trades" : "loses money over many trades"} />
        <Readout label="Win rate needed to break even" value={`${breakEvenRate.toFixed(1)}%`}
                 sub={winRate >= breakEvenRate ? "you are above it" : "you are below it"} />
      </div>
      <Working lines={[
        `EV = (${winRate}% x ${avgWin.toFixed(1)}R) − (${(100 - winRate)}% x ${avgLoss.toFixed(1)}R) = ${ev.toFixed(2)}R`,
        `Break-even win rate = ${avgLoss.toFixed(1)} / (${avgWin.toFixed(1)} + ${avgLoss.toFixed(1)}) = ${breakEvenRate.toFixed(1)}%`,
        `A 70% win rate loses money whenever the average loss is more than 2.33x the average win.`,
      ]} />
    </div>
  );
}

// ── risk_of_ruin ────────────────────────────────────────────────────────

function RiskOfRuin({ p }: { p: Record<string, number> }) {
  const [winRate, setWinRate] = useState(p.win_rate ?? 55);
  const [betPct, setBetPct] = useState(p.bet_pct ?? 5);
  const [trades, setTrades] = useState(p.trades ?? 200);

  // Median outcome of repeatedly staking a fixed FRACTION. The geometric
  // mean, not the arithmetic one, is what a compounding path actually
  // realises — which is the entire lesson.
  const { median, ruinPct } = useMemo(() => {
    const w = winRate / 100, f = betPct / 100;
    const logG = w * Math.log(1 + f) + (1 - w) * Math.log(1 - f);
    const med = 100 * Math.exp(logG * trades);
    // Rough Monte Carlo for the chance of ever dropping below 20% of stake.
    let ruined = 0;
    const RUNS = 400;
    for (let r = 0; r < RUNS; r++) {
      let bal = 1;
      for (let t = 0; t < trades; t++) {
        bal *= Math.random() < w ? 1 + f : 1 - f;
        if (bal < 0.2) { ruined++; break; }
      }
    }
    return { median: med, ruinPct: (ruined / RUNS) * 100 };
  }, [winRate, betPct, trades]);

  const edge = winRate - 50;

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4">
        <Slider label="Win rate" value={winRate} onChange={setWinRate} min={35} max={70} format={(v) => `${v}%`} />
        <Slider label="Stake per trade" value={betPct} onChange={setBetPct} min={1} max={40} format={(v) => `${v}%`} />
        <Slider label="Number of trades" value={trades} onChange={setTrades} min={20} max={500} step={10} format={(v) => `${v}`} />
      </div>
      <div className="grid sm:grid-cols-3 gap-4">
        <Readout label="Your edge" value={`${signed(edge, 1)}pp`} tone={edge >= 0 ? "up" : "down"}
                 sub="above a coin flip" />
        <Readout label="Median ending balance" value={`${median.toFixed(0)}`}
                 tone={median >= 100 ? "up" : "down"} sub="starting from 100" />
        <Readout label="Chance of losing 80%" value={`${ruinPct.toFixed(0)}%`} tone="down"
                 sub="simulated over 400 runs" />
      </div>
      <Working lines={[
        `Staking a fixed FRACTION compounds, so the geometric mean governs:`,
        `g = ${winRate}%·ln(1+${betPct}%) + ${100 - winRate}%·ln(1−${betPct}%)`,
        `A positive edge with too large a stake still has a negative geometric mean: the median path loses even though the average bet is favourable.`,
      ]} />
    </div>
  );
}

// ── dollar_cost_average ─────────────────────────────────────────────────

const DCA_PATHS: Record<string, number[]> = {
  // Twelve monthly prices, normalised to start at 100.
  dip_then_recover: [100, 94, 88, 79, 72, 68, 74, 81, 88, 94, 99, 104],
  steady_rise:      [100, 102, 104, 107, 109, 112, 114, 117, 120, 123, 126, 130],
  steady_fall:      [100, 97, 95, 92, 89, 86, 84, 81, 79, 76, 74, 71],
  choppy:           [100, 108, 96, 105, 92, 101, 94, 107, 97, 103, 95, 102],
};

function DollarCostAverage({ p }: { p: Record<string, unknown> }) {
  const [amount, setAmount] = useState((p.amount as number) ?? 12000);
  const [scenario, setScenario] = useState<string>((p.scenario as string) ?? "dip_then_recover");

  const prices = DCA_PATHS[scenario] ?? DCA_PATHS.dip_then_recover;
  const perMonth = amount / prices.length;

  // Lump sum: everything at the first price. DCA: equal amounts monthly.
  const lumpShares = amount / prices[0];
  const dcaShares = prices.reduce((s, px) => s + perMonth / px, 0);
  const finalPx = prices[prices.length - 1];
  const lumpValue = lumpShares * finalPx;
  const dcaValue = dcaShares * finalPx;
  const diff = lumpValue - dcaValue;

  return (
    <div className="space-y-4">
      <Slider label="Amount to deploy" value={amount} onChange={setAmount} min={1200} max={120000} step={1200} format={(v) => money(v)} />
      <div>
        <span className="label-caps block mb-2">Price path over 12 months</span>
        <div className="flex flex-wrap gap-1.5">
          {Object.keys(DCA_PATHS).map((k) => (
            <button
              key={k}
              onClick={() => setScenario(k)}
              className={`px-2.5 py-1 rounded text-[11px] transition-colors ${
                scenario === k ? "bg-aureus-gold text-aureus-ink font-semibold" : "bg-aureus-panellift text-aureus-muted hover:text-aureus-text"
              }`}
            >
              {k.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>
      <MiniCurve series={[{ values: prices, color: "var(--gold)" }]} height={70} />
      <div className="grid sm:grid-cols-3 gap-4">
        <Readout label="All at once" value={money(lumpValue)} tone={lumpValue >= amount ? "up" : "down"} />
        <Readout label="Spread over 12 months" value={money(dcaValue)} tone={dcaValue >= amount ? "up" : "down"} />
        <Readout label="Difference" value={`${diff >= 0 ? "+" : "−"}${money(Math.abs(diff))}`}
                 tone={diff >= 0 ? "up" : "down"}
                 sub={diff >= 0 ? "lump sum ahead" : "spreading ahead"} />
      </div>
      <Working lines={[
        `Lump sum buys ${lumpShares.toFixed(1)} shares at ${prices[0]}.`,
        `Spreading buys ${dcaShares.toFixed(1)} shares at an average of ${(amount / dcaShares).toFixed(1)}.`,
        `Spreading wins when the path dips and recovers, and loses when it simply rises, and you cannot know which you are in beforehand.`,
      ]} />
    </div>
  );
}

// ── Dispatcher ──────────────────────────────────────────────────────────

const WIDGETS: Record<string, (props: { p: Record<string, never> }) => React.JSX.Element> = {
  compounding: Compounding as never,
  fee_drag: FeeDrag as never,
  drawdown_recovery: DrawdownRecovery as never,
  position_size: PositionSize as never,
  expected_value: ExpectedValue as never,
  risk_of_ruin: RiskOfRuin as never,
  dollar_cost_average: DollarCostAverage as never,
};

export default function LessonExerciseCard({ exercise }: { exercise: LessonExercise }) {
  const Widget = WIDGETS[exercise.kind];
  if (!Widget) {
    // An unknown kind means the curriculum is ahead of the frontend. Say
    // so quietly rather than crashing the lesson around it.
    return (
      <div className="rounded-sm border border-aureus-rule bg-aureus-panel p-5">
        <p className="text-[13px] text-aureus-muted">
          This lesson includes an interactive exercise ({exercise.kind}) that this version of the
          app cannot display yet.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-sm border border-aureus-rule border-t-aureus-golddim bg-aureus-panel overflow-hidden">
      <div className="px-5 py-3.5 border-b border-aureus-rule">
        <div className="label-caps">Try it</div>
        <h4 className="font-display text-[17px] text-aureus-text mt-1">{exercise.title}</h4>
        <p className="text-[13px] text-aureus-muted mt-1.5 leading-relaxed">{exercise.prompt}</p>
      </div>
      <div className="p-5">
        <Widget p={(exercise.params ?? {}) as Record<string, never>} />
      </div>
    </div>
  );
}
