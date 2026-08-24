"use client";
/**
 * VARIANT A — "Broadsheet"
 *
 * The brightest of the three by a wide margin: a warm paper ground with
 * ink text, using the same gold / verdigris / oxblood as accents rather
 * than as light sources. The reference is a printed financial daily or a
 * shareholder annual report — a nameplate, ruled columns, figures set in
 * tabular monospace, and nothing enclosed in a box unless the box earns it.
 *
 * The specific moves that keep it from reading as generated:
 *   · No stat-card row. The headline figure is set once, large, in Fraunces,
 *     and the supporting numbers hang off a ruled list beside it.
 *   · Rules do the dividing, not borders. There are exactly two filled
 *     surfaces on the page.
 *   · The wire uses hanging timestamps in a left gutter — a newspaper
 *     convention — instead of one card per headline.
 *   · Copy is dated and specific ("as of 4:00 PM"), never "Last updated".
 */
import { ArrowUpRight, Plus } from "lucide-react";
import {
  AllocationRows, Figure, PAPER as p, PreviewChart, RuledLabel, clockTime,
  firstSentence, marketPhase, money, moneyCompact, pnlOf, sentimentTone,
  signed, signedMoney, useBars, useClock, useMounted, useTodaysLesson, useWire,
} from "./kit";
import type { VariantProps } from "./kit";

export default function Broadsheet({
  userId, holdings, totals, loading, tickers, activeTicker, onSelectTicker, onAdd, onEdit,
}: VariantProps) {
  const { bars, provider, stats } = useBars(activeTicker);
  // Deliberately short. The wire and the positions table share a row, and
  // a twelve-item wire runs a full screen past the end of a four-position
  // table — leaving a column of blank paper that reads as a mistake.
  const { items: wire } = useWire(userId, 7);
  const lesson = useTodaysLesson(userId);
  const now = useClock();
  const mounted = useMounted();
  const phase = marketPhase(now);

  const up = totals.pnl >= 0;
  const invested = totals.totalValue - totals.pnl;
  const priced = holdings.filter((h) => h.current_price != null).length;
  const best = [...holdings].sort((a, b) => (pnlOf(b).pct ?? -Infinity) - (pnlOf(a).pct ?? -Infinity))[0];

  return (
    <div
      className="-mx-6 -my-6 px-10 py-9 min-h-[calc(100vh-2.25rem)]"
      style={{ background: p.ground, color: p.text }}
    >
      {/* ── Nameplate ───────────────────────────────────────────────── */}
      <header>
        <div className="h-[3px]" style={{ background: p.ruleStrong }} />
        <div className="flex items-end justify-between gap-6 pt-4 pb-3">
          <h1
            className="font-display leading-[0.95]"
            style={{ fontWeight: 600, fontSize: "clamp(2rem,4.2vw,3.1rem)", letterSpacing: "-0.02em" }}
          >
            Portfolio Intelligence
          </h1>
          <button
            onClick={onAdd}
            className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 text-xs uppercase transition-colors"
            style={{ border: `1px solid ${p.ruleStrong}`, color: p.text, letterSpacing: "0.14em" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = p.accent; e.currentTarget.style.color = p.sheet; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = p.text; }}
          >
            <Plus className="w-3.5 h-3.5" strokeWidth={2} /> Add position
          </button>
        </div>
        <div
          className="flex flex-wrap items-center gap-x-5 gap-y-1 py-2 text-[11px] uppercase"
          style={{ borderTop: `1px solid ${p.ruleStrong}`, borderBottom: `1px solid ${p.rule}`, color: p.muted, letterSpacing: "0.16em" }}
        >
          <span>
            {mounted
              ? now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })
              : " "}
          </span>
          <span style={{ color: p.rule }}>│</span>
          <span style={{ color: phase.open ? p.up : p.muted }}>{phase.label}</span>
          <span style={{ color: p.rule }}>│</span>
          <span>{holdings.length} positions · {priced} priced</span>
          <span className="ml-auto normal-case" style={{ letterSpacing: "0.05em" }}>
            {provider ? `Prices via ${provider}` : " "}
          </span>
        </div>
      </header>

      {/* ── Lead ─────────────────────────────────────────────────────
          Three columns, the broadsheet idiom: the figure gets the width,
          the supporting material runs beside it in narrower measures. A
          two-column version left a column of dead paper under the lead
          paragraph, because the ruled list and the column together are
          taller than the figure. */}
      <section className="grid lg:grid-cols-[1.45fr_1fr_1fr] gap-x-10 gap-y-8 pt-8 pb-9">
        <div className="min-w-0">
          <div className="text-[11px] uppercase mb-3" style={{ color: p.muted, letterSpacing: "0.2em" }}>
            Total portfolio value
          </div>
          <div
            className="font-display leading-none"
            style={{ fontWeight: 600, fontSize: "clamp(3rem,7.5vw,5.5rem)", letterSpacing: "-0.035em" }}
          >
            {loading ? "—" : money(totals.totalValue)}
          </div>

          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mt-5">
            <span className="font-mono-num text-2xl" style={{ color: up ? p.up : p.down }}>
              {loading ? "—" : signedMoney(totals.pnl)}
            </span>
            <span className="font-mono-num text-lg" style={{ color: up ? p.up : p.down }}>
              {loading ? "" : `${signed(totals.pnlPct)}%`}
            </span>
            <span className="text-sm" style={{ color: p.muted }}>
              unrealised, against {money(invested)} invested
            </span>
          </div>

          <p className="mt-6 text-[13px] leading-relaxed max-w-xl" style={{ color: p.textSoft }}>
            Every figure on this page is computed from live pricing and your own cost basis —
            nothing here is a projection. Positions are marked at the last close reported by
            the data chain, and the allocation weights update with them.
          </p>
        </div>

        {/* Ruled key-figures list — no cards */}
        <div className="lg:pl-9 min-w-0" style={{ borderLeft: `1px solid ${p.rule}` }}>
          <RuledLabel p={p}>Key figures</RuledLabel>
          <dl className="mt-1">
            {[
              { k: "Invested capital", v: loading ? "—" : moneyCompact(invested), tone: undefined as "up" | "down" | undefined },
              { k: "Unrealised P&L", v: loading ? "—" : signedMoney(totals.pnl), tone: up ? ("up" as const) : ("down" as const) },
              { k: "Return on cost", v: loading ? "—" : `${signed(totals.pnlPct)}%`, tone: up ? ("up" as const) : ("down" as const) },
              { k: "Positions held", v: loading ? "—" : String(holdings.length), tone: undefined },
              {
                k: "Largest holding",
                v: holdings.length
                  ? [...holdings].sort((a, b) => (b.current_weight ?? 0) - (a.current_weight ?? 0))[0].ticker
                  : "—",
                tone: undefined,
              },
              {
                k: "Best performer",
                v: best && pnlOf(best).pct != null ? `${best.ticker} ${signed(pnlOf(best).pct!, 1)}%` : "—",
                tone: best && (pnlOf(best).pct ?? 0) >= 0 ? ("up" as const) : ("down" as const),
              },
            ].map((row, i) => (
              <div
                key={row.k}
                className="flex items-baseline justify-between gap-4 py-2.5"
                style={{ borderTop: i === 0 ? "none" : `1px solid ${p.rule}` }}
              >
                <dt className="text-[13px]" style={{ color: p.textSoft }}>{row.k}</dt>
                <dd><Figure value={row.v} p={p} tone={row.tone} className="text-sm" /></dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Third column — the standing editorial slot */}
        <div className="lg:pl-9 min-w-0" style={{ borderLeft: `1px solid ${p.rule}` }}>
          <RuledLabel p={p}>Today’s column</RuledLabel>
          {lesson ? (
            <div className="mt-4">
              <span className="text-[10px] uppercase" style={{ color: p.accent, letterSpacing: "0.2em" }}>
                {lesson.tier_label} · {lesson.lesson.category}
              </span>
              <h3 className="font-display text-[22px] mt-2 leading-tight" style={{ fontWeight: 600 }}>
                {lesson.lesson.title}
              </h3>
              <p className="text-[13px] leading-relaxed mt-2.5" style={{ color: p.textSoft }}>
                {firstSentence(lesson.lesson.body, 240)}
              </p>
              <a
                href="/education"
                className="inline-flex items-center gap-1 text-xs mt-3 hover:underline"
                style={{ color: p.accent }}
              >
                Continue reading <ArrowUpRight className="w-3 h-3" />
              </a>
              <div className="mt-5 pt-4 text-[11px]" style={{ borderTop: `1px solid ${p.rule}`, color: p.muted }}>
                {lesson.lessons_completed_count} lessons completed
                {lesson.lessons_to_next_tier != null && ` · ${lesson.lessons_to_next_tier} more to the next level`}
              </div>
            </div>
          ) : (
            <p className="text-[13px] mt-4" style={{ color: p.muted }}>
              Today’s column will appear here once the curriculum loads.
            </p>
          )}
        </div>
      </section>

      {/* ── Market action ───────────────────────────────────────────── */}
      <section className="pb-9">
        <RuledLabel
          p={p}
          right={
            <div className="flex gap-0.5">
              {tickers.map((t) => (
                <button
                  key={t}
                  onClick={() => onSelectTicker(t)}
                  className="px-2.5 py-1 text-[11px] font-mono-num transition-colors"
                  style={
                    t === activeTicker
                      ? { background: p.ruleStrong, color: p.sheet }
                      : { color: p.muted }
                  }
                >
                  {t}
                </button>
              ))}
            </div>
          }
        >
          Market action
        </RuledLabel>

        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 mt-4 mb-1">
          <span className="font-display text-3xl" style={{ fontWeight: 600 }}>{activeTicker}</span>
          {stats && (
            <>
              <Figure value={`$${stats.last.toFixed(2)}`} p={p} className="text-2xl" />
              <Figure
                value={`${signed(stats.changePct)}%`}
                p={p} tone={stats.changePct >= 0 ? "up" : "down"} className="text-base"
              />
              <span className="text-xs" style={{ color: p.muted }}>
                over 120 sessions · range ${stats.low.toFixed(2)}–${stats.high.toFixed(2)}
              </span>
            </>
          )}
        </div>

        <div style={{ borderTop: `1px solid ${p.rule}`, paddingTop: 8 }}>
          <PreviewChart bars={bars} p={p} height={280} />
        </div>
      </section>

      {/* ── Ledger + wire ──────────────────────────────────────────── */}
      <section className="grid lg:grid-cols-[1.75fr_1fr] gap-x-12 gap-y-10 pb-6">
        <div className="min-w-0">
          <RuledLabel p={p} right={<span className="text-[10px]" style={{ color: p.muted }}>Select a row to edit</span>}>
            Positions
          </RuledLabel>

          {loading ? (
            <p className="py-10 text-sm" style={{ color: p.muted }}>Loading positions…</p>
          ) : holdings.length === 0 ? (
            <p className="py-10 text-sm" style={{ color: p.muted }}>
              No positions on file. Add one and this page starts reporting on it.
            </p>
          ) : (
            <div className="overflow-x-auto mt-3">
              <table className="w-full" style={{ borderCollapse: "collapse", minWidth: 640 }}>
              <thead>
                <tr
                  className="text-[10px] uppercase"
                  style={{ color: p.muted, letterSpacing: "0.14em", borderBottom: `1.5px solid ${p.ruleStrong}` }}
                >
                  <th className="text-left  pb-2 pr-3 font-medium">Security</th>
                  <th className="text-right pb-2 px-3 font-medium">Qty</th>
                  <th className="text-right pb-2 px-3 font-medium">Cost</th>
                  <th className="text-right pb-2 px-3 font-medium">Last</th>
                  <th className="text-right pb-2 px-3 font-medium">Gain / loss</th>
                  <th className="text-right pb-2 pl-3 font-medium">Weight</th>
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
                      style={{ borderBottom: `1px solid ${p.rule}` }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = p.sheet)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <td className="py-3 pr-3">
                        <span className="font-display text-base" style={{ fontWeight: 600 }}>{h.ticker}</span>
                        {h.beta != null && (
                          <span className="ml-2 text-[11px]" style={{ color: p.muted }}>β {h.beta.toFixed(2)}</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right"><Figure value={h.quantity.toLocaleString()} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-3 px-3 text-right"><Figure value={`$${h.average_cost_basis.toFixed(2)}`} p={p} tone="muted" className="text-[13px]" /></td>
                      <td className="py-3 px-3 text-right"><Figure value={h.current_price != null ? `$${h.current_price.toFixed(2)}` : "—"} p={p} className="text-[13px]" /></td>
                      <td className="py-3 px-3 text-right">
                        {abs != null ? (
                          <>
                            <Figure value={signedMoney(abs)} p={p} tone={pos ? "up" : "down"} className="text-[13px]" />
                            <Figure value={` (${signed(pct!, 1)}%)`} p={p} tone={pos ? "up" : "down"} className="text-[11px]" style={{ opacity: 0.7 }} />
                          </>
                        ) : <Figure value="—" p={p} tone="muted" className="text-[13px]" />}
                      </td>
                      <td className="py-3 pl-3 text-right"><Figure value={h.current_weight != null ? `${h.current_weight.toFixed(1)}%` : "—"} p={p} tone="muted" className="text-[13px]" /></td>
                    </tr>
                  );
                })}
              </tbody>
              </table>
            </div>
          )}

          <div className="mt-8">
            <RuledLabel p={p}>Allocation</RuledLabel>
            <div className="mt-2"><AllocationRows holdings={holdings} p={p} /></div>
          </div>
        </div>

        {/* The wire — hanging timestamps, no card per item */}
        <div className="min-w-0">
          <RuledLabel p={p}>The wire</RuledLabel>
          <div className="mt-3">
            {wire.length === 0 ? (
              <p className="text-sm py-6" style={{ color: p.muted }}>
                Nothing on the wire yet. The pipeline polls sources on a schedule.
              </p>
            ) : (
              wire.map((a, i) => (
                <a
                  key={a.id}
                  href={a.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="grid grid-cols-[3.25rem_1fr] gap-3 py-3 group"
                  style={{ borderTop: i === 0 ? "none" : `1px solid ${p.rule}` }}
                >
                  <span className="font-mono-num text-[11px] pt-0.5" style={{ color: p.muted }}>
                    {clockTime(a.published_at)}
                  </span>
                  <span>
                    <span className="flex items-center gap-2 mb-1">
                      <span className="font-mono-num text-[11px]" style={{ color: p.accent }}>{a.ticker}</span>
                      <Figure
                        value={signed(a.sentiment_score)}
                        p={p} tone={sentimentTone(a.sentiment_score)} className="text-[11px]"
                      />
                    </span>
                    <span className="block text-[13px] leading-snug group-hover:underline" style={{ color: p.text }}>
                      {a.headline}
                    </span>
                    <span className="block text-[11px] mt-1" style={{ color: p.muted }}>{a.source}</span>
                  </span>
                </a>
              ))
            )}
            {wire.length > 0 && (
              <a
                href="/analysis"
                className="inline-flex items-center gap-1 text-xs mt-4 hover:underline"
                style={{ color: p.accent }}
              >
                More coverage <ArrowUpRight className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>
      </section>

      <footer
        className="pt-4 text-[10px] uppercase flex justify-between"
        style={{ borderTop: `2px solid ${p.ruleStrong}`, color: p.muted, letterSpacing: "0.18em" }}
      >
        <span>Aureus Intelligence</span>
        <span>Informational only · Not financial advice</span>
      </footer>
    </div>
  );
}
