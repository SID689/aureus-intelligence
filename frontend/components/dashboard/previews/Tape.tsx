"use client";
/**
 * VARIANT B — "Tape"
 *
 * Stays dark, but lifts the whole thing: panels go from #14160f to #191d12,
 * body text from #e8e4d8 to #f4f1e6, gold from the muted #b8935a to a
 * confident #d9b478, and the muted grey stops being nearly invisible. Same
 * hues throughout — this is the current theme with the lights turned up,
 * not a different theme.
 *
 * Structurally it abandons the four-equal-tiles row. The moves:
 *   · A live tape across the top — every holding, its last price and its
 *     move, scrolling. It is the one element on the page that says
 *     "financial software" before you've read a word.
 *   · One dominant figure with its own sparkline, then three stat columns
 *     divided by vertical hairlines rather than four bordered boxes.
 *   · Allocation as a single segmented bar, not a donut. A donut with a
 *     legend spends 160×160 pixels to say what one 8px bar says better.
 *   · Positions get an inline weight bar drawn in the row itself, so the
 *     table carries the allocation instead of a separate widget repeating it.
 */
import { Plus } from "lucide-react";
import {
  AllocationStack, Figure, TAPE as p, PreviewChart, RuledLabel, Sparkline, StatusDot,
  clockTime, firstSentence, marketPhase, money, pnlOf, sentimentTone, signed,
  signedMoney, useBars, useClock, useMounted, useTodaysLesson, useWire,
} from "./kit";
import type { Palette, VariantProps } from "./kit";

export default function Tape({
  userId, holdings, totals, loading, tickers, activeTicker, onSelectTicker, onAdd, onEdit,
}: VariantProps) {
  const { bars, provider, stats } = useBars(activeTicker);
  const { items: wire } = useWire(userId, 16);
  const lesson = useTodaysLesson(userId);
  const now = useClock();
  const mounted = useMounted();
  const phase = marketPhase(now);

  const up = totals.pnl >= 0;
  const invested = totals.totalValue - totals.pnl;
  const maxWeight = Math.max(1, ...holdings.map((h) => h.current_weight ?? 0));

  // Doubled so the marquee can loop without a visible seam.
  const tapeItems = holdings.length ? [...holdings, ...holdings] : [];

  return (
    <div
      className="-mx-6 -my-6 min-h-[calc(100vh-2.25rem)]"
      style={{ background: p.ground, color: p.text }}
    >
      {/* Scoped keyframes — kept local rather than added to globals.css so
          this preview stays additive and can be deleted in one move. */}
      <style>{`
        @keyframes aureus-tape-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        .aureus-tape-track { animation: aureus-tape-scroll 42s linear infinite; }
        .aureus-tape:hover .aureus-tape-track { animation-play-state: paused; }
        @media (prefers-reduced-motion: reduce) { .aureus-tape-track { animation: none; } }
      `}</style>

      {/* ── The tape ────────────────────────────────────────────────── */}
      <div
        className="aureus-tape overflow-hidden"
        style={{ background: p.sheet, borderBottom: `1px solid ${p.rule}` }}
      >
        {tapeItems.length > 0 ? (
          <div className="aureus-tape-track flex whitespace-nowrap py-2.5" style={{ width: "max-content" }}>
            {tapeItems.map((h, i) => {
              const { pct } = pnlOf(h);
              const pos = (pct ?? 0) >= 0;
              return (
                <span key={`${h.id}-${i}`} className="flex items-baseline gap-2 px-5" style={{ borderRight: `1px solid ${p.rule}` }}>
                  <span className="text-[12px] font-medium tracking-wide" style={{ color: p.text }}>{h.ticker}</span>
                  <Figure value={h.current_price != null ? h.current_price.toFixed(2) : "—"} p={p} tone="muted" className="text-[12px]" />
                  {pct != null && (
                    <Figure value={`${signed(pct, 2)}%`} p={p} tone={pos ? "up" : "down"} className="text-[12px]" />
                  )}
                </span>
              );
            })}
          </div>
        ) : (
          <div className="py-2.5 px-6 text-[12px]" style={{ color: p.muted }}>
            Tape is empty — add a position and it starts running.
          </div>
        )}
      </div>

      <div className="px-8 py-7 space-y-8">
        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-[28px] leading-none" style={{ fontWeight: 600, letterSpacing: "-0.01em" }}>
              Portfolio
            </h1>
            <div className="flex items-center gap-2 mt-2 text-[11px]" style={{ color: p.muted }}>
              <StatusDot p={p} on={phase.open} />
              <span>{phase.label}</span>
              <span style={{ color: p.rule }}>·</span>
              <span>
                {mounted ? `as of ${now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}` : " "}
              </span>
              {provider && (<><span style={{ color: p.rule }}>·</span><span>{provider}</span></>)}
            </div>
          </div>
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-1.5 px-4 h-9 rounded-md text-[13px] font-medium transition-opacity hover:opacity-90"
            style={{ background: p.accent, color: p.ground }}
          >
            <Plus className="w-4 h-4" strokeWidth={2.25} /> Add position
          </button>
        </div>

        {/* ── Hero figure + stat columns ───────────────────────────── */}
        <div
          className="rounded-lg overflow-hidden"
          style={{ background: p.sheet, border: `1px solid ${p.rule}` }}
        >
          <div className="grid lg:grid-cols-[1.35fr_2fr]">
            {/* flex column with the sparkline pushed to the bottom: the
                stat columns beside it are taller, and left to itself this
                panel ended halfway down with a void underneath. */}
            <div className="p-6 flex flex-col min-w-0" style={{ borderRight: `1px solid ${p.rule}` }}>
              <div className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.2em" }}>
                Portfolio value
              </div>
              <div className="font-mono-num mt-2.5 leading-none" style={{ fontSize: "clamp(2.25rem,4.5vw,3.25rem)", letterSpacing: "-0.03em" }}>
                {loading ? "—" : money(totals.totalValue)}
              </div>
              <div className="flex items-center gap-3 mt-3">
                <Figure value={signedMoney(totals.pnl)} p={p} tone={up ? "up" : "down"} className="text-lg" />
                <span
                  className="font-mono-num text-[12px] px-1.5 py-0.5 rounded"
                  style={{ background: up ? `${p.up}1f` : `${p.down}1f`, color: up ? p.up : p.down }}
                >
                  {loading ? "" : `${signed(totals.pnlPct)}%`}
                </span>
              </div>
              {stats && (
                <div className="mt-auto pt-5" style={{ borderTop: `1px solid ${p.rule}` }}>
                  <div className="text-[10px] uppercase mb-2" style={{ color: p.muted, letterSpacing: "0.16em" }}>
                    {activeTicker} · 120 sessions
                  </div>
                  {/* The sparkline tracks the charted ticker, not the
                      portfolio: there is no portfolio-level time series in
                      the API yet, and inventing one would put a fabricated
                      curve next to real money. Labelled as such above. */}
                  <SparkRow p={p} closes={stats.closes} changePct={stats.changePct} />
                </div>
              )}
            </div>

            {/* Three columns divided by hairlines, not four boxes */}
            <div className="grid sm:grid-cols-3">
              {[
                { k: "Invested", v: loading ? "—" : money(invested), s: "cost basis", tone: undefined as "up" | "down" | undefined },
                {
                  k: "Positions", v: loading ? "—" : String(holdings.length),
                  s: `${holdings.filter((h) => h.current_price != null).length} priced`, tone: undefined,
                },
                {
                  k: "Return on cost", v: loading ? "—" : `${signed(totals.pnlPct)}%`,
                  s: "all-time", tone: up ? ("up" as const) : ("down" as const),
                },
              ].map((c, i) => (
                <div key={c.k} className="p-6" style={{ borderLeft: i === 0 ? "none" : `1px solid ${p.rule}` }}>
                  <div className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.16em" }}>{c.k}</div>
                  <Figure value={c.v} p={p} tone={c.tone} className="block text-2xl mt-2" />
                  <div className="text-[11px] mt-1.5" style={{ color: p.muted }}>{c.s}</div>
                </div>
              ))}
              <div className="sm:col-span-3 p-6" style={{ borderTop: `1px solid ${p.rule}` }}>
                <div className="text-[10px] uppercase mb-3" style={{ color: p.muted, letterSpacing: "0.16em" }}>
                  Allocation
                </div>
                <AllocationStack holdings={holdings} p={p} />
              </div>
            </div>
          </div>
        </div>

        {/* ── Chart + wire ─────────────────────────────────────────── */}
        <div className="grid lg:grid-cols-[1.55fr_1fr] gap-5">
          <div className="rounded-lg min-w-0" style={{ background: p.sheet, border: `1px solid ${p.rule}` }}>
            <div className="flex flex-wrap items-center justify-between gap-3 p-4" style={{ borderBottom: `1px solid ${p.rule}` }}>
              <div className="flex items-baseline gap-3">
                <span className="text-base font-medium">{activeTicker}</span>
                {stats && (
                  <>
                    <Figure value={`$${stats.last.toFixed(2)}`} p={p} className="text-base" />
                    <Figure value={`${signed(stats.changePct)}%`} p={p} tone={stats.changePct >= 0 ? "up" : "down"} className="text-[13px]" />
                  </>
                )}
              </div>
              <div className="flex gap-1">
                {tickers.map((t) => (
                  <button
                    key={t}
                    onClick={() => onSelectTicker(t)}
                    className="px-2 py-1 rounded text-[11px] font-mono-num transition-colors"
                    style={t === activeTicker
                      ? { background: p.accent, color: p.ground }
                      : { color: p.muted, background: p.sheetAlt }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="p-3 pt-4">
              <PreviewChart bars={bars} p={p} height={272} />
            </div>
          </div>

          <div className="rounded-lg flex flex-col min-w-0" style={{ background: p.sheet, border: `1px solid ${p.rule}` }}>
            <div className="flex items-center justify-between p-4" style={{ borderBottom: `1px solid ${p.rule}` }}>
              <span className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.18em" }}>The wire</span>
              <span className="flex items-center gap-1.5 text-[10px]" style={{ color: p.muted }}>
                <StatusDot p={p} on /> live
              </span>
            </div>
            <div className="overflow-y-auto px-4" style={{ maxHeight: 356 }}>
              {wire.length === 0 ? (
                <p className="text-[13px] py-8" style={{ color: p.muted }}>
                  Nothing on the wire yet.
                </p>
              ) : (
                wire.map((a, i) => (
                  <a
                    key={a.id}
                    href={a.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="grid grid-cols-[3rem_1fr] gap-3 py-3 group"
                    style={{ borderTop: i === 0 ? "none" : `1px solid ${p.rule}` }}
                  >
                    <span className="font-mono-num text-[10px] pt-0.5" style={{ color: p.muted }}>
                      {clockTime(a.published_at)}
                    </span>
                    <span>
                      <span className="flex items-center gap-2">
                        <span className="font-mono-num text-[10px]" style={{ color: p.accent }}>{a.ticker}</span>
                        <Figure value={signed(a.sentiment_score)} p={p} tone={sentimentTone(a.sentiment_score)} className="text-[10px]" />
                      </span>
                      <span className="block text-[13px] leading-snug mt-1 group-hover:underline" style={{ color: p.textSoft }}>
                        {a.headline}
                      </span>
                    </span>
                  </a>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ── Positions with inline weight bars ────────────────────── */}
        <div className="rounded-lg overflow-hidden" style={{ background: p.sheet, border: `1px solid ${p.rule}` }}>
          <div className="flex items-center justify-between p-4" style={{ borderBottom: `1px solid ${p.rule}` }}>
            <span className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.18em" }}>Positions</span>
            <span className="text-[10px]" style={{ color: p.muted }}>Click a row to edit</span>
          </div>

          {loading ? (
            <p className="p-8 text-sm" style={{ color: p.muted }}>Loading positions…</p>
          ) : holdings.length === 0 ? (
            <p className="p-8 text-sm" style={{ color: p.muted }}>No holdings yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" style={{ minWidth: 760 }}>
              <thead>
                <tr className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.14em" }}>
                  <th className="text-left  py-2.5 px-4 font-medium">Ticker</th>
                  <th className="text-right py-2.5 px-3 font-medium">Qty</th>
                  <th className="text-right py-2.5 px-3 font-medium">Cost</th>
                  <th className="text-right py-2.5 px-3 font-medium">Last</th>
                  <th className="text-right py-2.5 px-3 font-medium">P&amp;L</th>
                  <th className="text-left  py-2.5 px-3 font-medium w-40">Weight</th>
                  <th className="text-right py-2.5 px-4 font-medium">β</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h) => {
                  const { abs, pct } = pnlOf(h);
                  const pos = (abs ?? 0) >= 0;
                  return (
                    <tr
                      key={h.id || h.ticker}
                      onClick={() => onEdit(h)}
                      className="cursor-pointer transition-colors"
                      style={{ borderTop: `1px solid ${p.rule}` }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = p.sheetAlt)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <td className="py-3 px-4 font-medium">{h.ticker}</td>
                      <td className="py-3 px-3 text-right"><Figure value={h.quantity.toLocaleString()} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-3 px-3 text-right"><Figure value={`$${h.average_cost_basis.toFixed(2)}`} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-3 px-3 text-right"><Figure value={h.current_price != null ? `$${h.current_price.toFixed(2)}` : "—"} p={p} className="text-[13px]" /></td>
                      <td className="py-3 px-3 text-right">
                        {abs != null ? (
                          <>
                            <Figure value={signedMoney(abs)} p={p} tone={pos ? "up" : "down"} className="text-[13px]" />
                            <Figure value={` ${signed(pct!, 1)}%`} p={p} tone={pos ? "up" : "down"} className="text-[11px]" style={{ opacity: 0.7 }} />
                          </>
                        ) : <Figure value="—" p={p} tone="muted" className="text-[13px]" />}
                      </td>
                      <td className="py-3 px-3">
                        <span className="flex items-center gap-2">
                          <span className="flex-1 h-1 rounded-sm overflow-hidden" style={{ background: p.sheetAlt }}>
                            <span
                              className="block h-full"
                              style={{ width: `${((h.current_weight ?? 0) / maxWeight) * 100}%`, background: p.accent }}
                            />
                          </span>
                          <Figure value={h.current_weight != null ? `${h.current_weight.toFixed(1)}%` : "—"} p={p} tone="muted" className="text-[11px] w-11 text-right" />
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right"><Figure value={h.beta != null ? h.beta.toFixed(2) : "—"} p={p} tone="muted" className="text-[13px]" /></td>
                    </tr>
                  );
                })}
              </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Lesson strip ─────────────────────────────────────────── */}
        {lesson && (
          <div
            className="rounded-lg p-5 flex flex-wrap items-center gap-x-6 gap-y-3"
            style={{ background: p.sheet, border: `1px solid ${p.rule}`, borderLeft: `2px solid ${p.accent}` }}
          >
            <div className="flex-1 min-w-[16rem]">
              <span className="text-[10px] uppercase" style={{ color: p.accent, letterSpacing: "0.18em" }}>
                Today’s lesson · {lesson.tier_label}
              </span>
              <h3 className="font-display text-lg mt-1.5" style={{ fontWeight: 600 }}>{lesson.lesson.title}</h3>
              <p className="text-[13px] leading-relaxed mt-1" style={{ color: p.muted }}>
                {firstSentence(lesson.lesson.body)}
              </p>
            </div>
            <a
              href="/education"
              className="px-4 h-9 inline-flex items-center rounded-md text-[13px] transition-colors"
              style={{ border: `1px solid ${p.accentSoft}`, color: p.accent }}
            >
              Read the lesson
            </a>
          </div>
        )}

        <RuledLabel p={p}>Informational only · not financial advice</RuledLabel>
      </div>
    </div>
  );
}

/** Sparkline plus its change caption, kept out of the main tree above. */
function SparkRow({
  p, closes, changePct,
}: {
  p: Palette; closes: number[]; changePct: number;
}) {
  const rising = changePct >= 0;
  return (
    <div className="flex items-end gap-3">
      <Sparkline values={closes.slice(-90)} color={rising ? p.up : p.down} width={150} height={36} />
      <Figure value={`${signed(changePct)}%`} p={p} tone={rising ? "up" : "down"} className="text-xs pb-0.5" />
    </div>
  );
}
