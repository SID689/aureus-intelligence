"use client";
/**
 * Catalyst timeline for the ticker being analysed.
 *
 * A list of dates is easy to produce and slow to read. The useful facts are
 * where today sits among the events and how much is coming inside the
 * horizon you picked, so the top of this is a strip scaled to that window.
 * The past is compressed into the left third: what already happened is
 * context, what is coming is the risk. Lists underneath are for reading.
 *
 * Catalysts never change the score. They feed the bull and bear cases
 * below as dated evidence and dated tests.
 */
import { useEffect, useMemo, useState } from "react";
import { CalendarClock, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CapsLabel, Figure, RuledLabel, Sheet } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { moneyCompact, signedPct } from "@/lib/format";
import { getCatalystTimeline } from "@/lib/api";
import type { CatalystGroup, CatalystItem, CatalystTimelineData } from "@/lib/api";

type Horizon = "short_term" | "medium_term" | "long_term";

interface Props {
  ticker: string;
  horizon: Horizon;
  userId: string;
  initial?: CatalystTimelineData;
}

const GROUP_LABEL: Record<CatalystGroup, string> = {
  earnings: "Earnings", deals: "Deals", regulatory: "Regulatory", corporate: "Corporate", macro: "Macro",
};
const IMPACT_RANK = { high: 0, medium: 1, low: 2 } as const;
const DOT_SIZE = { high: "w-3.5 h-3.5", medium: "w-2.5 h-2.5", low: "w-2 h-2" } as const;
const SOURCE_LABEL: Record<string, string> = {
  earnings: "Earnings calendar", sec_8k: "SEC 8-K filings", dividends: "Dividends",
};
const PAST_SHARE = 30;      // percent of the strip given to the lookback window
const URGENT_DAYS = 14;
const LIST_LIMIT = 6;

/** Catalyst dates are calendar dates in New York. Parsed as UTC so a reader in Sydney sees the same day. */
function dayLabel(iso: string, withYear = false): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short", day: "numeric", timeZone: "UTC", ...(withYear ? { year: "numeric" } : {}),
  });
}

function countdown(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  return days > 0 ? `in ${days} days` : `${-days} days ago`;
}

function sessionLabel(t: string | null): string | null {
  if (!t) return null;
  if (t === "bmo") return "before the open";
  if (t === "amc") return "after the close";
  if (t === "dmh") return "during market hours";
  return t;
}

function position(days: number, lookback: number, forward: number): number {
  if (days < 0) return PAST_SHARE * (1 - Math.min(1, -days / lookback));
  return PAST_SHARE + (100 - PAST_SHARE) * Math.min(1, days / forward);
}

function dotTone(c: CatalystItem): string {
  if (c.direction === "positive") return "bg-aureus-verdigris border-aureus-verdigris";
  if (c.direction === "negative") return "bg-aureus-oxblood border-aureus-oxblood";
  if (c.timing === "upcoming") {
    return c.impact === "high" ? "bg-aureus-gold border-aureus-goldbright" : "bg-aureus-golddim border-aureus-gold";
  }
  return "bg-aureus-panelhigh border-aureus-rulestrong";
}

function statusText(v: string): string {
  if (v === "cached") return "up to date";
  if (v === "pending") return "still loading";
  if (v.startsWith("refreshed")) return "just refreshed";
  if (v.startsWith("unavailable")) return "unavailable right now";
  return v;
}

function facts(c: CatalystItem): [string, string][] {
  const d = c.details as Record<string, unknown>;
  const out: [string, string][] = [];
  const num = (k: string) => (typeof d[k] === "number" ? (d[k] as number) : null);
  if (c.type === "earnings") {
    if (num("eps_estimate") != null) out.push(["Consensus EPS", num("eps_estimate")!.toFixed(2)]);
    if (num("eps_actual") != null) out.push(["Reported EPS", num("eps_actual")!.toFixed(2)]);
    if (num("revenue_estimate") != null) out.push(["Revenue estimate", moneyCompact(num("revenue_estimate")!)]);
    if (num("revenue_actual") != null) out.push(["Revenue reported", moneyCompact(num("revenue_actual")!)]);
    if (num("surprise_pct") != null) out.push(["EPS surprise", signedPct(num("surprise_pct")!, 1)]);
  }
  if (typeof d.item === "string") out.push(["8-K item", d.item]);
  if (num("report_count") != null && num("report_count")! > 1) out.push(["Outlets reporting", String(num("report_count"))]);
  if (num("cash_amount") != null) out.push(["Amount per share", `$${num("cash_amount")!.toFixed(2)}`]);
  return out;
}

function EventDetail({ c }: { c: CatalystItem }) {
  const session = sessionLabel(c.time);
  const rows = facts(c);
  return (
    <div className="rounded-md border border-aureus-rule bg-aureus-panellift px-4 py-3.5 rise-in" key={c.id}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="muted">{c.type_label}</Badge>
        <Badge variant={c.impact === "high" ? "default" : "muted"}>{c.impact} impact</Badge>
        {c.direction === "positive" && <Badge variant="green">positive</Badge>}
        {c.direction === "negative" && <Badge variant="red">negative</Badge>}
        {c.scope !== "company" && <Badge variant="amber">{c.scope === "macro" ? "market-wide" : `${c.sector} sector`}</Badge>}
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 mt-2.5">
        <h4 className="text-[14.5px] text-aureus-text">{c.title}</h4>
        <span className="text-[12px] text-aureus-muted">
          <Figure className="text-[12px] text-aureus-soft">{dayLabel(c.date, true)}</Figure>
          {" · "}{countdown(c.days_until)}{session ? ` · ${session}` : ""}
        </span>
      </div>
      {c.description && <p className="text-[12.5px] text-aureus-soft leading-relaxed mt-1.5">{c.description}</p>}
      {rows.length > 0 && (
        <dl className="flex flex-wrap gap-x-6 gap-y-2 mt-3">
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt className="label-caps">{k}</dt>
              <dd><Figure className="text-[13px]">{v}</Figure></dd>
            </div>
          ))}
        </dl>
      )}
      {c.type === "earnings" && typeof c.details.surprise_pct === "number" && Math.abs(c.details.surprise_pct) > 50 && (
        <p className="text-[11px] text-aureus-amber leading-relaxed mt-2.5">
          A surprise this large usually means the reported figure and the estimate are on different bases (GAAP
          against adjusted, or a one-off gain). Treat it as unverified; the bull and bear cases do not argue from it.
        </p>
      )}
      {c.timing === "upcoming" && c.type === "earnings" && c.date_confirmed !== true && (
        <p className="text-[11px] text-aureus-muted mt-2.5">Date from the consensus calendar. Companies confirm a few weeks ahead and occasionally move it.</p>
      )}
      {c.source_url && (
        <a href={c.source_url} target="_blank" rel="noopener noreferrer"
           className="inline-flex items-center gap-1 text-[11.5px] text-aureus-gold hover:text-aureus-goldbright mt-2.5">
          Source <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </div>
  );
}

function EventList({
  title, items, total, selectedId, onSelect, expanded, onToggle, empty,
}: {
  title: string; items: CatalystItem[]; total: number; selectedId: string | null;
  onSelect: (id: string) => void; expanded: boolean; onToggle: () => void; empty: string;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between">
        <CapsLabel>{title}</CapsLabel>
        <Figure tone="muted" className="text-[11px]">{total}</Figure>
      </div>
      {items.length === 0 ? (
        <p className="text-[12px] text-aureus-muted mt-2.5">{empty}</p>
      ) : (
        <ul className="mt-1.5">
          {items.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => onSelect(c.id)}
                className={cn(
                  "w-full text-left flex items-start gap-3 py-2 pl-2.5 pr-2 border-l-2 transition-colors",
                  c.id === selectedId ? "border-aureus-gold bg-aureus-gold/[0.06]" : "border-transparent hover:bg-aureus-panellift",
                )}
              >
                <Figure tone="muted" className="text-[11.5px] w-12 shrink-0 pt-px">{dayLabel(c.date)}</Figure>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] text-aureus-soft truncate">{c.title}</span>
                  <span className="block text-[11px] text-aureus-muted">
                    {c.scope === "company" ? c.type_label : c.scope === "macro" ? "Market-wide" : "Sector"} · {countdown(c.days_until)}
                  </span>
                </span>
                <span className={cn("mt-1.5 rounded-full shrink-0 border", DOT_SIZE[c.impact], dotTone(c))} aria-label={`${c.impact} impact`} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {total > LIST_LIMIT && (
        <button onClick={onToggle} className="text-[11.5px] text-aureus-gold hover:text-aureus-goldbright mt-1.5 pl-2.5">
          {expanded ? "Show fewer" : `Show all ${total}`}
        </button>
      )}
    </div>
  );
}

export default function CatalystTimeline({ ticker, horizon, userId, initial }: Props) {
  const [data, setData] = useState<CatalystTimelineData | null>(initial ?? null);
  const [loading, setLoading] = useState(!initial);
  const [error, setError] = useState<string | null>(null);
  const [group, setGroup] = useState<CatalystGroup | "all">("all");
  const [highOnly, setHighOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandAhead, setExpandAhead] = useState(false);
  const [expandBehind, setExpandBehind] = useState(false);

  useEffect(() => {
    setData(initial ?? null);
    setSelectedId(null);
  }, [initial]);

  // The analysis came back without a timeline (it never fails the analysis
  // for want of one), so fetch it directly.
  useEffect(() => {
    if (initial || !userId) return;
    let cancelled = false;
    setLoading(true);
    getCatalystTimeline(ticker, userId, horizon, true)
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e: unknown) => { if (!cancelled) setError(e instanceof Error ? e.message : "Catalysts unavailable"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [initial, ticker, horizon, userId]);

  // Sources still running when the analysis returned: look once more.
  const pending = !!data && Object.values(data.sources).includes("pending");
  useEffect(() => {
    if (!pending || !userId) return;
    const id = setTimeout(() => {
      getCatalystTimeline(ticker, userId, horizon, false)
        .then((fresh) => setData((prev) => ({
          ...fresh,
          sources: Object.fromEntries(Object.entries(prev?.sources ?? {}).map(
            ([k, v]) => [k, v === "pending" ? "refreshed" : v],
          )),
        })))
        .catch(() => {});
    }, 9000);
    return () => clearTimeout(id);
  }, [pending, ticker, horizon, userId]);

  const all = useMemo(() => (data ? [...data.recent, ...data.upcoming] : []), [data]);
  const groupsPresent = useMemo(
    () => (Object.keys(GROUP_LABEL) as CatalystGroup[]).filter((g) => all.some((c) => c.group === g)),
    [all],
  );
  const visible = useMemo(
    () => all.filter((c) => (group === "all" || c.group === group) && (!highOnly || c.impact === "high")),
    [all, group, highOnly],
  );
  const ahead = useMemo(() => visible.filter((c) => c.timing === "upcoming").sort((a, b) => a.days_until - b.days_until), [visible]);
  const behind = useMemo(() => visible.filter((c) => c.timing === "recent").sort((a, b) => b.days_until - a.days_until), [visible]);

  const selected = useMemo(() => (
    visible.find((c) => c.id === selectedId)
    ?? visible.find((c) => c.id === data?.primary?.id)
    ?? ahead.find((c) => c.impact === "high") ?? ahead[0] ?? behind[0] ?? null
  ), [visible, selectedId, data, ahead, behind]);

  // Same-day events share one marker, so a busy day doesn't stack dots into an unreadable blob.
  const lanes = useMemo(() => {
    const build = (items: CatalystItem[]) => {
      const byDay = new Map<string, CatalystItem[]>();
      for (const c of items) byDay.set(c.date, [...(byDay.get(c.date) ?? []), c]);
      return [...byDay.values()].map((cs) => cs.sort((a, b) => IMPACT_RANK[a.impact] - IMPACT_RANK[b.impact]));
    };
    return {
      company: build(visible.filter((c) => c.scope === "company")),
      context: build(visible.filter((c) => c.scope !== "company")),
    };
  }, [visible]);

  if (loading) {
    return (
      <Sheet className="p-5">
        <RuledLabel>Catalysts</RuledLabel>
        <p className="text-[13px] text-aureus-muted py-8 text-center">Loading dated events for {ticker}…</p>
      </Sheet>
    );
  }
  if (error || !data) {
    return (
      <Sheet className="p-5">
        <RuledLabel>Catalysts</RuledLabel>
        <p className="text-[13px] text-aureus-muted py-6">{error ?? "The catalyst timeline is unavailable for this ticker right now."}</p>
      </Sheet>
    );
  }

  const { lookback_days: lookback, forward_days: forward } = data.window;
  const primary = data.primary;
  const primaryUrgent = !!primary && primary.relation === "upcoming" && primary.impact === "high" && primary.days_until <= URGENT_DAYS;

  const pick = (cluster: CatalystItem[]) => {
    const idx = cluster.findIndex((c) => c.id === selected?.id);
    // Clicking a selected multi-event marker steps through its events.
    setSelectedId(idx >= 0 ? cluster[(idx + 1) % cluster.length].id : cluster[0].id);
  };

  const marker = (cluster: CatalystItem[], lane: "company" | "context") => {
    const lead = cluster[0];
    const isSelected = cluster.some((c) => c.id === selected?.id);
    const urgent = lane === "company" && lead.timing === "upcoming" && lead.days_until <= URGENT_DAYS && lead.impact === "high";
    return (
      <button
        key={`${lane}-${lead.date}`}
        onClick={() => pick(cluster)}
        className={cn(
          "absolute -translate-x-1/2 -translate-y-1/2 p-1.5 rounded-full focus:outline-none focus-visible:ring-1 focus-visible:ring-aureus-gold",
          lane === "company" ? "top-[40px]" : "top-[72px]",
        )}
        style={{ left: `${position(lead.days_until, lookback, forward)}%` }}
        aria-label={`${lead.title}, ${dayLabel(lead.date)}${cluster.length > 1 ? `, and ${cluster.length - 1} more` : ""}`}
        title={cluster.map((c) => `${dayLabel(c.date)} — ${c.title}`).join("\n")}
      >
        {urgent && <span aria-hidden className="absolute inset-0 rounded-full bg-aureus-gold/35 pulse-gold" />}
        {lane === "company" ? (
          <span className={cn("relative block rounded-full border", DOT_SIZE[lead.impact], dotTone(lead),
            isSelected && "ring-2 ring-aureus-text ring-offset-2 ring-offset-aureus-panel")} />
        ) : (
          <span className={cn("relative block w-2 h-2 rotate-45",
            lead.scope === "macro" ? "bg-aureus-soft/70" : "bg-aureus-amber/80",
            isSelected && "ring-2 ring-aureus-text ring-offset-2 ring-offset-aureus-panel")} />
        )}
        {cluster.length > 1 && (
          <span className="absolute -top-1.5 -right-1.5 font-mono-num text-[9px] text-aureus-text">{cluster.length}</span>
        )}
      </button>
    );
  };

  return (
    <Sheet className="p-5 space-y-4">
      <RuledLabel
        right={
          <span className="text-[11px] text-aureus-muted">
            <Figure tone={data.counts.high_impact_upcoming > 0 ? "flat" : "muted"} className="text-[11px]">
              {data.counts.high_impact_upcoming}
            </Figure>{" "}high-impact ahead · next {forward} days
          </span>
        }
      >
        Catalysts
      </RuledLabel>

      {primary && (
        <div className={cn(
          "flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border px-4 py-3",
          primaryUrgent ? "border-aureus-gold/50 bg-aureus-gold/[0.06] shadow-[0_0_24px_rgba(217,180,120,0.08)]" : "border-aureus-rule bg-aureus-panellift",
        )}>
          <CalendarClock className={cn("w-4 h-4 shrink-0", primaryUrgent ? "text-aureus-gold" : "text-aureus-muted")} />
          <div className="min-w-0 flex-1">
            <CapsLabel className={primaryUrgent ? "text-aureus-gold" : undefined}>
              {primary.relation === "upcoming"
                ? (primary.impact === "high" ? "Next high-impact event" : "Next notable event")
                : "Most recent significant event"}
            </CapsLabel>
            <button onClick={() => setSelectedId(primary.id)} className="block text-left text-[14px] text-aureus-text hover:text-aureus-gold mt-0.5">
              {primary.title}
            </button>
          </div>
          <div className="text-right">
            <Figure className="text-[15px] text-aureus-text">{dayLabel(primary.date)}</Figure>
            <div className="text-[11px] text-aureus-muted">
              {countdown(primary.days_until)}{sessionLabel(primary.time) ? ` · ${sessionLabel(primary.time)}` : ""}
            </div>
          </div>
        </div>
      )}

      {all.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {(["all", ...groupsPresent] as (CatalystGroup | "all")[]).map((g) => (
            <button
              key={g}
              onClick={() => setGroup(g)}
              className={cn(
                "rounded px-2 py-1 text-[11px] border transition-colors",
                group === g ? "border-aureus-gold/60 bg-aureus-gold/10 text-aureus-gold" : "border-aureus-rule text-aureus-muted hover:text-aureus-text",
              )}
            >
              {g === "all" ? "All" : GROUP_LABEL[g]}
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-[11px] text-aureus-muted cursor-pointer">
            <input type="checkbox" checked={highOnly} onChange={(e) => setHighOnly(e.target.checked)} className="accent-[#d9b478]" />
            High impact only
          </label>
        </div>
      )}

      {/* The strip */}
      <div className="relative h-[104px] select-none" aria-label="Catalyst timeline">
        <div className="absolute left-0 right-0 top-[40px] h-px bg-aureus-rule" />
        <div className="absolute left-0 right-0 top-[72px] h-px bg-aureus-rulesoft" />
        <div className="absolute top-3 bottom-7 rounded-sm bg-aureus-gold/[0.035]" style={{ left: `${PAST_SHARE}%`, right: 0 }} />
        <div className="absolute top-1 bottom-7 w-px bg-aureus-gold/80" style={{ left: `${PAST_SHARE}%` }}>
          <span className="absolute -top-0.5 left-1.5 label-caps text-aureus-gold whitespace-nowrap">Today</span>
        </div>
        <span className="hidden sm:block absolute right-0 top-[46px] label-caps text-[9px]">Company</span>
        <span className="hidden sm:block absolute right-0 top-[78px] label-caps text-[9px]">Market</span>
        {lanes.company.map((cl) => marker(cl, "company"))}
        {lanes.context.map((cl) => marker(cl, "context"))}
        <div className="absolute left-0 right-0 bottom-0 h-4 font-mono-num text-[10px] text-aureus-muted">
          <span className="absolute left-0">−{lookback}d</span>
          <span className="absolute -translate-x-1/2" style={{ left: `${PAST_SHARE + (100 - PAST_SHARE) / 2}%` }}>+{Math.round(forward / 2)}d</span>
          <span className="absolute right-0">+{forward}d</span>
        </div>
      </div>

      {all.length === 0 ? (
        <p className="text-[13px] text-aureus-muted">
          No dated events found for {ticker} in this window. That is itself information: nothing is scheduled that
          the sources below know about.
        </p>
      ) : visible.length === 0 ? (
        <p className="text-[13px] text-aureus-muted">Nothing matches these filters.</p>
      ) : (
        <>
          {selected && <EventDetail c={selected} />}
          <div className="grid md:grid-cols-2 gap-x-8 gap-y-5">
            <EventList title="Ahead" items={expandAhead ? ahead : ahead.slice(0, LIST_LIMIT)} total={ahead.length}
                       selectedId={selected?.id ?? null} onSelect={setSelectedId}
                       expanded={expandAhead} onToggle={() => setExpandAhead(!expandAhead)}
                       empty="Nothing scheduled in this window." />
            <EventList title="Behind" items={expandBehind ? behind : behind.slice(0, LIST_LIMIT)} total={behind.length}
                       selectedId={selected?.id ?? null} onSelect={setSelectedId}
                       expanded={expandBehind} onToggle={() => setExpandBehind(!expandBehind)}
                       empty={`Nothing in the last ${lookback} days.`} />
          </div>
        </>
      )}

      <div className="pt-3 border-t border-aureus-rulesoft space-y-1.5 text-[11px] text-aureus-muted">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {Object.entries(data.sources).map(([k, v]) => (
            <span key={k}><span className="text-aureus-soft">{SOURCE_LABEL[k] ?? k}</span> · {statusText(v)}</span>
          ))}
          <span>plus the FOMC and FDA advisory calendars and classified news</span>
        </div>
        <p>These events shape the bull and bear cases below. They do not move the score.</p>
        {data.unavailable.length > 0 && (
          <details>
            <summary className="cursor-pointer hover:text-aureus-text w-fit">What this timeline does not cover</summary>
            <ul className="mt-1.5 space-y-1">
              {data.unavailable.map((u) => (
                <li key={u.name}><span className="text-aureus-soft">{u.name}.</span> {u.reason}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </Sheet>
  );
}
