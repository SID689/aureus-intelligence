"use client";
/**
 * VARIANT C — "Ledger"
 *
 * The middle path on brightness and the most deliberately tactile of the
 * three. Everything sits on a warm graphite ground (#1b1e15) and the
 * content lives on raised "sheets" (#272a20) with a gold hairline along
 * their top edge and a real shadow underneath — so the page reads as
 * physical layers rather than as outlined rectangles on a flat plane.
 *
 * Where the other two differ from today's dashboard structurally, this one
 * differs materially:
 *   · Section labels float ABOVE their sheet rather than sitting inside a
 *     card header. The sheet then has no internal chrome and its whole
 *     surface belongs to the content.
 *   · The four stat cards collapse into one statement sheet — the way an
 *     account statement puts the balance and its components on one page.
 *   · Positions are ledger rows: generous height, a hairline between each,
 *     and a gold edge tick that appears on the row under the cursor.
 *   · Allocation is a ruled ledger of weights, matching the positions
 *     treatment rather than introducing a pie.
 */
import { ArrowUpRight, Plus } from "lucide-react";
import Logo from "@/components/brand/Logo";
import {
  AllocationRows, Figure, LEDGER as p, PreviewChart, Sparkline, StatusDot,
  clockTime, firstSentence, marketPhase, money, pnlOf, sentimentTone, signed,
  signedMoney, useBars, useClock, useMounted, useTodaysLesson, useWire,
} from "./kit";
import type { VariantProps } from "./kit";

/** A raised sheet: gold top edge, warm surface, soft cast shadow. */
function Sheet({
  children, className = "", accent = false,
}: {
  children: React.ReactNode; className?: string; accent?: boolean;
}) {
  return (
    <div
      className={`rounded-[10px] ${accent ? "guilloche-corner" : ""} ${className}`}
      style={{
        background: p.sheet,
        border: `1px solid ${p.rule}`,
        borderTop: `1px solid ${p.accentSoft}`,
        boxShadow: "0 1px 0 rgba(255,255,255,0.02) inset, 0 10px 28px -12px rgba(0,0,0,0.7)",
      }}
    >
      {children}
    </div>
  );
}

/** Floating small-caps label that sits above a sheet, not inside it. */
function Label({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 mb-2.5 px-1">
      <span className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.2em" }}>
        {children}
      </span>
      {right}
    </div>
  );
}

export default function Ledger({
  userId, holdings, totals, loading, tickers, activeTicker, onSelectTicker, onAdd, onEdit,
}: VariantProps) {
  const { bars, provider, stats } = useBars(activeTicker);
  const { items: wire } = useWire(userId, 10);
  const lesson = useTodaysLesson(userId);
  const now = useClock();
  const mounted = useMounted();
  const phase = marketPhase(now);

  const up = totals.pnl >= 0;
  const invested = totals.totalValue - totals.pnl;

  return (
    <div
      className="-mx-6 -my-6 px-8 py-8 min-h-[calc(100vh-2.25rem)]"
      style={{ background: p.ground, color: p.text }}
    >
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="pb-5 mb-7" style={{ borderBottom: `1px solid ${p.accentSoft}` }}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <Logo size={34} />
            <div>
              <h1 className="font-display text-[26px] leading-none" style={{ fontWeight: 600, letterSpacing: "-0.015em" }}>
                Portfolio
              </h1>
              <div className="flex items-center gap-2 mt-1.5 text-[11px]" style={{ color: p.muted }}>
                <StatusDot p={p} on={phase.open} />
                <span>{phase.label}</span>
                <span style={{ color: p.rule }}>·</span>
                <span>
                  {mounted
                    ? now.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                    : " "}
                </span>
                {provider && (<><span style={{ color: p.rule }}>·</span><span>{provider}</span></>)}
              </div>
            </div>
          </div>
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-1.5 px-4 h-9 rounded-md text-[13px] font-medium transition-colors"
            style={{ background: p.accent, color: p.ground }}
          >
            <Plus className="w-4 h-4" strokeWidth={2.25} /> Add position
          </button>
        </div>
      </header>

      {/* ── The statement ──────────────────────────────────────────── */}
      <section className="mb-8">
        <Label right={<span className="text-[10px]" style={{ color: p.muted }}>Marked at last close</span>}>
          Statement of account
        </Label>
        <Sheet accent>
          <div className="grid lg:grid-cols-[1.15fr_1.6fr]">
            {/* Flex column so the sparkline pins to the bottom edge and
                sits level with the last composition row beside it. */}
            <div className="p-7 flex flex-col min-w-0" style={{ borderRight: `1px solid ${p.rule}` }}>
              <div className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.2em" }}>
                Net value
              </div>
              <div
                className="font-display leading-none mt-3"
                style={{ fontWeight: 600, fontSize: "clamp(2.5rem,5vw,3.6rem)", letterSpacing: "-0.03em" }}
              >
                {loading ? "—" : money(totals.totalValue)}
              </div>
              <div className="flex items-baseline gap-3 mt-4">
                <Figure value={loading ? "—" : signedMoney(totals.pnl)} p={p} tone={up ? "up" : "down"} className="text-xl" />
                <Figure value={loading ? "" : `${signed(totals.pnlPct)}%`} p={p} tone={up ? "up" : "down"} className="text-sm" />
                <span className="text-[12px]" style={{ color: p.muted }}>unrealised</span>
              </div>
              {stats && (
                <div className="mt-auto pt-6" style={{ borderTop: `1px solid ${p.rule}` }}>
                  <div className="text-[10px] uppercase mb-2.5" style={{ color: p.muted, letterSpacing: "0.16em" }}>
                    {activeTicker} · last 90 sessions
                  </div>
                  <Sparkline
                    values={stats.closes.slice(-90)}
                    color={stats.changePct >= 0 ? p.up : p.down}
                    width={200}
                    height={40}
                  />
                </div>
              )}
            </div>

            {/* Ruled components of the balance — one sheet, not four cards */}
            <div className="p-7">
              <div className="text-[10px] uppercase mb-1" style={{ color: p.muted, letterSpacing: "0.2em" }}>
                Composition
              </div>
              <dl>
                {[
                  { k: "Cost basis", d: "what you paid in", v: loading ? "—" : money(invested), tone: undefined as "up" | "down" | undefined },
                  { k: "Market value", d: "at the latest price on file", v: loading ? "—" : money(totals.totalValue), tone: undefined },
                  { k: "Gain / loss", d: "market value less cost basis", v: loading ? "—" : signedMoney(totals.pnl), tone: up ? ("up" as const) : ("down" as const) },
                  { k: "Return on cost", d: "all-time, excluding dividends", v: loading ? "—" : `${signed(totals.pnlPct)}%`, tone: up ? ("up" as const) : ("down" as const) },
                  {
                    k: "Securities held", d: `${holdings.filter((h) => h.current_price != null).length} currently priced`,
                    v: loading ? "—" : String(holdings.length), tone: undefined,
                  },
                ].map((row) => (
                  <div key={row.k} className="flex items-baseline justify-between gap-6 py-3" style={{ borderTop: `1px solid ${p.rule}` }}>
                    <dt>
                      <span className="block text-[13px]" style={{ color: p.textSoft }}>{row.k}</span>
                      <span className="block text-[11px] mt-0.5" style={{ color: p.muted }}>{row.d}</span>
                    </dt>
                    <dd><Figure value={row.v} p={p} tone={row.tone} className="text-[15px]" /></dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </Sheet>
      </section>

      {/* ── Chart + allocation ─────────────────────────────────────── */}
      <section className="grid lg:grid-cols-[1.7fr_1fr] gap-6 mb-8">
        <div className="min-w-0">
          <Label
            right={
              <div className="flex gap-1">
                {tickers.map((t) => (
                  <button
                    key={t}
                    onClick={() => onSelectTicker(t)}
                    className="px-2 py-0.5 rounded text-[11px] font-mono-num transition-colors"
                    style={t === activeTicker
                      ? { background: p.accentSoft, color: p.text }
                      : { color: p.muted }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            }
          >
            Price history
          </Label>
          <Sheet>
            <div className="p-5">
              <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 mb-4">
                <span className="font-display text-2xl" style={{ fontWeight: 600 }}>{activeTicker}</span>
                {stats && (
                  <>
                    <Figure value={`$${stats.last.toFixed(2)}`} p={p} className="text-lg" />
                    <Figure value={`${signed(stats.changePct)}%`} p={p} tone={stats.changePct >= 0 ? "up" : "down"} className="text-[13px]" />
                    <span className="text-[11px]" style={{ color: p.muted }}>
                      range ${stats.low.toFixed(2)} – ${stats.high.toFixed(2)}
                    </span>
                  </>
                )}
              </div>
              <PreviewChart bars={bars} p={p} height={260} />
            </div>
          </Sheet>
        </div>

        <div>
          <Label>Allocation</Label>
          <Sheet>
            <div className="p-5">
              <AllocationRows holdings={holdings} p={p} />
            </div>
          </Sheet>

          {lesson && (
            <div className="mt-6">
              <Label>Today’s lesson · {lesson.tier_label}</Label>
              <Sheet accent>
                <div className="p-5">
                  <h3 className="font-display text-[17px] leading-snug" style={{ fontWeight: 600 }}>
                    {lesson.lesson.title}
                  </h3>
                  <p className="text-[13px] leading-relaxed mt-2" style={{ color: p.muted }}>
                    {firstSentence(lesson.lesson.body)}
                  </p>
                  <a
                    href="/education"
                    className="inline-flex items-center gap-1 text-xs mt-3 hover:underline"
                    style={{ color: p.accent }}
                  >
                    Read the lesson <ArrowUpRight className="w-3 h-3" />
                  </a>
                </div>
              </Sheet>
            </div>
          )}
        </div>
      </section>

      {/* ── Positions ledger ───────────────────────────────────────── */}
      <section className="mb-8">
        <Label right={<span className="text-[10px]" style={{ color: p.muted }}>Select a row to edit or remove</span>}>
          Holdings ledger
        </Label>
        <Sheet>
          {loading ? (
            <p className="p-8 text-sm" style={{ color: p.muted }}>Loading positions…</p>
          ) : holdings.length === 0 ? (
            <p className="p-8 text-sm" style={{ color: p.muted }}>
              The ledger is empty. Add a position and it starts keeping the record.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full" style={{ minWidth: 760 }}>
              <thead>
                <tr className="text-[10px] uppercase" style={{ color: p.muted, letterSpacing: "0.16em" }}>
                  <th className="text-left  py-3 px-6 font-medium">Security</th>
                  <th className="text-right py-3 px-4 font-medium">Units</th>
                  <th className="text-right py-3 px-4 font-medium">Book cost</th>
                  <th className="text-right py-3 px-4 font-medium">Last price</th>
                  <th className="text-right py-3 px-4 font-medium">Gain / loss</th>
                  <th className="text-right py-3 px-4 font-medium">Weight</th>
                  <th className="text-right py-3 px-6 font-medium">Beta</th>
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
                      className="cursor-pointer group transition-colors"
                      style={{ borderTop: `1px solid ${p.rule}`, boxShadow: "inset 3px 0 0 transparent" }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = p.sheetAlt;
                        e.currentTarget.style.boxShadow = `inset 3px 0 0 ${p.accent}`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.boxShadow = "inset 3px 0 0 transparent";
                      }}
                    >
                      <td className="py-4 px-6">
                        <span className="font-display text-[17px]" style={{ fontWeight: 600 }}>{h.ticker}</span>
                      </td>
                      <td className="py-4 px-4 text-right"><Figure value={h.quantity.toLocaleString()} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-4 px-4 text-right"><Figure value={money(h.average_cost_basis * h.quantity)} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-4 px-4 text-right"><Figure value={h.current_price != null ? `$${h.current_price.toFixed(2)}` : "—"} p={p} className="text-[13px]" /></td>
                      <td className="py-4 px-4 text-right">
                        {abs != null ? (
                          <>
                            <Figure value={signedMoney(abs)} p={p} tone={pos ? "up" : "down"} className="text-[13px]" />
                            <Figure value={` ${signed(pct!, 1)}%`} p={p} tone={pos ? "up" : "down"} className="text-[11px]" style={{ opacity: 0.7 }} />
                          </>
                        ) : <Figure value="—" p={p} tone="muted" className="text-[13px]" />}
                      </td>
                      <td className="py-4 px-4 text-right"><Figure value={h.current_weight != null ? `${h.current_weight.toFixed(1)}%` : "—"} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-4 px-6 text-right"><Figure value={h.beta != null ? h.beta.toFixed(2) : "—"} p={p} tone="muted" className="text-[13px]" /></td>
                    </tr>
                  );
                })}
              </tbody>
              </table>
            </div>
          )}
        </Sheet>
      </section>

      {/* ── Wire ───────────────────────────────────────────────────── */}
      <section>
        <Label right={<span className="flex items-center gap-1.5 text-[10px]" style={{ color: p.muted }}><StatusDot p={p} on /> live</span>}>
          Recent coverage
        </Label>
        <Sheet>
          <div className="grid md:grid-cols-2">
            {wire.length === 0 ? (
              <p className="p-8 text-sm md:col-span-2" style={{ color: p.muted }}>
                Nothing on the wire yet. The pipeline polls sources on a schedule.
              </p>
            ) : (
              wire.map((a, i) => (
                <a
                  key={a.id}
                  href={a.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-5 group transition-colors"
                  // Two columns: a rule above everything past the first row,
                  // and a rule down the gutter for the right-hand column.
                  style={{
                    borderTop: i >= 2 ? `1px solid ${p.rule}` : "none",
                    borderLeft: i % 2 === 1 ? `1px solid ${p.rule}` : "none",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = p.sheetAlt)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <span className="flex items-center gap-2.5 mb-1.5">
                    <span className="font-mono-num text-[11px]" style={{ color: p.accent }}>{a.ticker}</span>
                    <Figure value={signed(a.sentiment_score)} p={p} tone={sentimentTone(a.sentiment_score)} className="text-[11px]" />
                    <span className="text-[10px] ml-auto" style={{ color: p.muted }}>{clockTime(a.published_at)}</span>
                  </span>
                  <span className="block text-[13.5px] leading-snug group-hover:underline" style={{ color: p.textSoft }}>
                    {a.headline}
                  </span>
                  <span className="block text-[11px] mt-1.5" style={{ color: p.muted }}>{a.source}</span>
                </a>
              ))
            )}
          </div>
        </Sheet>
      </section>
    </div>
  );
}
