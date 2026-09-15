"use client";
/**
 * The Hottest Stocks board.
 *
 * Laid out as a blotter, not a grid of cards: the reader's questions are
 * comparative (which is strongest, which is newest, what is coming for
 * each), and a table answers comparative questions at a glance where cards
 * make you hold numbers in your head.
 *
 * The page is candid about emptiness. A board that always has ten names
 * would be a board with a quota, and the whole value of this one is that
 * a name only appears when a verified score clears a published bar.
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { IconArrowDownRight, IconArrowUpRight, IconChevronDown } from "@/components/ui/icons";
import { LoadingRegion, SkeletonSheet, SkeletonTable } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/button";
import {
  CapsLabel, EmptyState, ErrorNote, Figure, Note, PageHeader, RuledLabel, ScoreMeter, Segmented, Sheet, StatusDot,
} from "@/components/ui/primitives";
import PushToggle from "@/components/notifications/PushToggle";
import { cn } from "@/lib/utils";
import { price, relativeTime, shortDate } from "@/lib/format";
import { PlanRequiredError, getLeaderboard, getLeaderboardEvents, subscribeMarketAlerts } from "@/lib/realtime";
import type {
  BoardCatalyst, Horizon, LeaderboardBoard, LeaderboardCandidate, LeaderboardEvent, LeaderboardMember, Pillar, SocketStatus,
} from "@/lib/realtime";

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: "short_term", label: "Short" },
  { value: "medium_term", label: "Medium" },
  { value: "long_term", label: "Long" },
];

const DRIVER: Record<Pillar, string> = { fundamental: "fundamentals", technical: "price action", sentiment: "sentiment" };

const LIVE_LABEL: Record<SocketStatus, string> = {
  idle: "Alerts idle", connecting: "Connecting", live: "Live alerts", reconnecting: "Reconnecting", denied: "Alerts unavailable",
};

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function dayLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function daysText(d?: number): string {
  if (d == null) return "";
  if (d === 0) return "today";
  return d > 0 ? `in ${d}d` : `${-d}d ago`;
}

function StrongBuyBadge() {
  // Solid and inverted: the one filled chip on the board, so it reads at a
  // glance without a glow or a pulse.
  return (
    <span className="inline-flex items-center border border-aureus-emerald bg-aureus-emerald px-1.5 py-[3px] font-mono-num text-[9.5px] font-medium uppercase tracking-[0.14em] text-aureus-ink whitespace-nowrap">
      Strong Buy
    </span>
  );
}

function CatalystCell({ c }: { c: BoardCatalyst | null }) {
  if (!c) return <span className="text-[12px] text-aureus-muted">No dated event</span>;
  const dot = c.direction === "positive" ? "bg-aureus-emerald"
    : c.direction === "negative" ? "bg-aureus-crimson"
    : c.impact === "high" ? "bg-aureus-gold" : "bg-aureus-muted";
  const soon = c.relation === "upcoming" && c.impact === "high" && (c.days_until ?? 99) <= 14;
  return (
    <span className="flex items-start gap-2 min-w-0">
      <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", dot, soon && "pulse-gold")} />
      <span className="min-w-0">
        <span className="block text-[13px] text-aureus-soft truncate max-w-[15rem]">{c.title}</span>
        <span className="block text-[11px] text-aureus-muted">
          <span className="font-mono-num">{dayLabel(c.date)}</span>
          {c.days_until != null && ` · ${daysText(c.days_until)}`} · {c.type_label}
        </span>
      </span>
    </span>
  );
}

function PillarMeters({ pillars }: { pillars: LeaderboardMember["pillars"] }) {
  return (
    <div className="space-y-2">
      {(["fundamental", "technical", "sentiment"] as Pillar[]).map((p) => (
        <div key={p} className="grid grid-cols-[6.5rem_1fr_2.5rem] items-center gap-3">
          <span className="text-[12px] text-aureus-muted capitalize">{p}</span>
          <ScoreMeter score={pillars[p] ?? 0} />
          <Figure tone={pillars[p] == null ? "muted" : "flat"} className="text-[12px] text-right">
            {pillars[p] == null ? "—" : pillars[p]!.toFixed(0)}
          </Figure>
        </div>
      ))}
    </div>
  );
}

function MemberDetail({ m, horizon }: { m: LeaderboardMember; horizon: Horizon }) {
  const stats: [string, string][] = [
    ["Conviction", m.conviction == null ? "—" : m.conviction.toFixed(0)],
    ["Pillar agreement", pct(m.agreement)],
    ["Data completeness", pct(m.data_completeness)],
    ["Peak composite", m.peak_composite == null ? "—" : m.peak_composite.toFixed(1)],
  ];
  return (
    <div className="grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-x-10 gap-y-5 rise-in">
      <div>
        <CapsLabel>Pillar scores</CapsLabel>
        <div className="mt-3"><PillarMeters pillars={m.pillars} /></div>
      </div>
      <div className="space-y-4">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
          {stats.map(([k, v]) => (
            <div key={k}>
              <dt className="label-caps">{k}</dt>
              <dd><Figure className="text-[15px]">{v}</Figure></dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-aureus-muted">
          <span>Verified {relativeTime(m.last_verified_at)}</span>
          {m.sector && <span>{m.sector}</span>}
          <Link href={`/analysis/${m.ticker}?horizon=${horizon}`} className="text-aureus-gold hover:text-aureus-goldbright">
            Full analysis →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LeaderboardView() {
  const router = useRouter();
  const params = useSearchParams();
  const urlHorizon = params.get("horizon");
  const horizon: Horizon = HORIZONS.some((h) => h.value === urlHorizon) ? (urlHorizon as Horizon) : "medium_term";

  const [board, setBoard] = useState<LeaderboardBoard | null>(null);
  const [events, setEvents] = useState<LeaderboardEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<SocketStatus>("idle");
  const [flash, setFlash] = useState<string | null>(null);
  const [sort, setSort] = useState<"composite" | "newest">("composite");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showRules, setShowRules] = useState(false);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [b, e] = await Promise.all([getLeaderboard(horizon), getLeaderboardEvents(horizon, 12)]);
      setBoard(b);
      setEvents(e.events);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof PlanRequiredError) {
        router.replace("/upgrade?feature=leaderboard&required_tier=elite");
        return;
      }
      setError(err instanceof Error ? err.message : "The board could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [horizon, router]);

  useEffect(() => { void load(); }, [load]);

  // "Added 3h ago" and the scan clock go stale on an open tab; refresh quietly.
  useEffect(() => {
    const id = setInterval(() => void load(true), 5 * 60_000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => subscribeMarketAlerts({
    onStatus: setLive,
    onAlert: (a) => {
      void load(true);
      if (a.horizon === horizon) {
        setFlash(a.ticker);
        setTimeout(() => setFlash((t) => (t === a.ticker ? null : t)), 8000);
      }
    },
  }), [horizon, load]);

  const members = useMemo(() => {
    const list = [...(board?.members ?? [])];
    return sort === "newest"
      ? list.sort((a, b) => b.entered_at.localeCompare(a.entered_at))
      : list.sort((a, b) => b.composite - a.composite);
  }, [board, sort]);

  const setHorizon = (h: Horizon) => router.replace(`/leaderboard?horizon=${h}`, { scroll: false });
  const openTicker = (t: string) => router.push(`/analysis/${t}?horizon=${horizon}`);

  const scan = board?.last_scan;
  const rules = board?.rules;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hottest Stocks"
        lead="Every S&P 500 stock, scored on all three pillars by the same engine as the analysis page. A stock
              joins this board only when a verified score clears the Strong Buy line with its pillars in agreement."
        actions={<Segmented options={HORIZONS} value={horizon} onChange={setHorizon} size="md" />}
        meta={
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11.5px] text-aureus-muted">
            <span className="flex items-center gap-1.5">
              <StatusDot on={live === "live"} />
              {LIVE_LABEL[live]}
            </span>
            {scan && (
              <span className={cn(scan.status === "failed" && "text-aureus-amber")}>
                {scan.status === "failed" ? "Last scan failed" : "Last scan"} {relativeTime(scan.finished_at ?? scan.started_at)}
              </span>
            )}
            {board && (
              <span>
                <Figure tone="muted" className="text-[11.5px]">{board.coverage.verified_24h}</Figure>
                /<Figure tone="muted" className="text-[11.5px]">{board.coverage.universe}</Figure> verified in 24h
              </span>
            )}
            <button onClick={() => setShowRules(!showRules)} className="text-aureus-gold hover:text-aureus-goldbright">
              {showRules ? "Hide the rules" : "How the board works"}
            </button>
          </div>
        }
      />

      {showRules && rules && (
        <Sheet className="p-5 rise-in">
          <div className="grid md:grid-cols-2 gap-x-10 gap-y-4 text-[12.5px] text-aureus-soft leading-relaxed">
            <div>
              <CapsLabel>Entry</CapsLabel>
              <p className="mt-1.5">
                On a verified score: composite of at least <Figure>{rules.entry.composite}</Figure>, pillar agreement of at
                least <Figure>{pct(rules.entry.agreement)}</Figure>, and data completeness of at least{" "}
                <Figure>{pct(rules.entry.data_completeness)}</Figure>.
              </p>
            </div>
            <div>
              <CapsLabel>Exit</CapsLabel>
              <p className="mt-1.5">
                Composite below <Figure>{rules.exit.composite}</Figure>, agreement below <Figure>{pct(rules.exit.agreement)}</Figure>,
                completeness below <Figure>{pct(rules.exit.data_completeness)}</Figure>, or no verification for{" "}
                <Figure>{rules.exit.stale_hours}</Figure> hours. The gap between the entry and exit lines stops names
                flickering on and off the board.
              </p>
            </div>
            <div>
              <CapsLabel>Verified</CapsLabel>
              <p className="mt-1.5">
                Prices from the latest pass, sentiment under three hours old, fundamentals under seven days old. Estimates
                decide what the scanner refreshes next. They never put a stock on the board.
              </p>
            </div>
            <div>
              <CapsLabel>Alerts and cadence</CapsLabel>
              <p className="mt-1.5">
                An alert means a stock crossed the line, so it needs an earlier verified score that did not qualify; a
                stock verified for the first time joins silently. At most one alert per stock per{" "}
                <Figure>{rules.alert_cooldown_hours}</Figure> hours, across all horizons. The index is rescored every 15
                minutes while the US market is open and hourly otherwise.
              </p>
            </div>
          </div>
        </Sheet>
      )}

      {error && (
        <div className="space-y-3">
          <ErrorNote>{error}</ErrorNote>
          <Button variant="outline" size="sm" onClick={() => load()}>Retry</Button>
        </div>
      )}

      {loading && !board && (
        <LoadingRegion label="Loading the board">
          <SkeletonSheet><SkeletonTable rows={7} columns={[1, 4, 2, 3, 4, 2]} /></SkeletonSheet>
        </LoadingRegion>
      )}

      {board && (
        <>
          {/* ── The board ─────────────────────────────────────────── */}
          <Sheet lift className="overflow-hidden">
            <div className="px-5 pt-4 pb-3">
              <RuledLabel
                right={members.length > 1 ? (
                  <Segmented
                    options={[{ value: "composite", label: "Score" }, { value: "newest", label: "Newest" }]}
                    value={sort}
                    onChange={(v) => setSort(v as "composite" | "newest")}
                  />
                ) : undefined}
              >
                Strong Buy · {board.horizon_label} · {members.length}
              </RuledLabel>
            </div>

            {members.length === 0 ? (
              board.coverage.scored === 0 ? (
                <EmptyState title="The scanner is building coverage">
                  The first passes score prices for the whole index at once, then add fundamentals and sentiment a few
                  dozen names at a time within the data providers&apos; rate limits. Full coverage takes about a day.
                  Nothing is shown until it is verified.
                </EmptyState>
              ) : (
                <EmptyState title="No stock clears the bar right now">
                  Of {board.coverage.scored} stocks scored, none currently has a verified composite of{" "}
                  {board.rules.entry.composite} or more with its pillars in agreement. That is the board doing its job:
                  most stocks, most of the time, are not Strong Buys.
                  {board.candidates.length > 0 ? " The closest are below." : ""}
                </EmptyState>
              )
            ) : (
              <>
              {/* Stacked list below lg. With the sidebar open, a tablet leaves
                  ~500px for this table; as a table it scrolled sideways and hid
                  the composite column, the one figure the board is about. */}
              <ul className="lg:hidden border-t border-aureus-rule divide-y divide-aureus-rulesoft">
                {members.map((m, i) => (
                  <li key={m.ticker} className={cn(flash === m.ticker && "bg-aureus-emerald/[0.09] rise-in")}>
                    <div className="flex items-stretch">
                      <button onClick={() => openTicker(m.ticker)}
                              className="flex-1 min-w-0 text-left px-4 py-3.5 hover:bg-aureus-panellift transition-colors">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-baseline gap-2">
                              <Figure tone="muted" className="text-[11px]">{i + 1}</Figure>
                              <span className="font-mono-num text-[15px] text-aureus-text">{m.ticker}</span>
                              <Figure className="text-[12.5px] text-aureus-soft">{price(m.price)}</Figure>
                            </div>
                            <div className="text-[11.5px] text-aureus-muted truncate">{m.company_name}</div>
                          </div>
                          <div className="text-right shrink-0">
                            <div className="flex items-center justify-end gap-2.5">
                              <Figure className="text-[17px] text-aureus-text">{m.composite.toFixed(1)}</Figure>
                              <StrongBuyBadge />
                            </div>
                            <div className="text-[11px] text-aureus-muted mt-0.5">added {relativeTime(m.entered_at)}</div>
                          </div>
                        </div>
                        <div className="mt-2"><CatalystCell c={m.primary_catalyst} /></div>
                      </button>
                      <button
                        onClick={() => setExpanded(expanded === m.ticker ? null : m.ticker)}
                        className="px-3.5 border-l border-aureus-rulesoft text-aureus-muted hover:text-aureus-text hover:bg-aureus-panellift"
                        aria-label={`${expanded === m.ticker ? "Hide" : "Show"} detail for ${m.ticker}`}
                        aria-expanded={expanded === m.ticker}
                      >
                        <IconChevronDown className={cn("w-4 h-4 transition-transform", expanded === m.ticker && "rotate-180")} />
                      </button>
                    </div>
                    {expanded === m.ticker && (
                      <div className="px-4 pb-5 pt-2 bg-aureus-ink/40"><MemberDetail m={m} horizon={horizon} /></div>
                    )}
                  </li>
                ))}
              </ul>
              <div className="hidden lg:block overflow-x-auto">
                <table className="w-full min-w-[780px] text-left">
                  <thead>
                    <tr className="border-y border-aureus-rule bg-aureus-ink/30">
                      {["#", "Ticker", "Price", "Composite", "Primary catalyst", "Added", ""].map((h) => (
                        <th key={h || "expand"} className="label-caps font-normal px-4 py-2.5">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m, i) => (
                      <Fragment key={m.ticker}>
                        <tr
                          onClick={() => openTicker(m.ticker)}
                          className={cn(
                            "group border-b border-aureus-rulesoft cursor-pointer transition-colors hover:bg-aureus-panellift",
                            flash === m.ticker && "bg-aureus-emerald/[0.09] rise-in",
                          )}
                        >
                          <td className="px-4 py-3.5 w-10"><Figure tone="muted" className="text-[12px]">{i + 1}</Figure></td>
                          <td className="px-4 py-3.5">
                            <div className="font-mono-num text-[15px] text-aureus-text group-hover:text-aureus-gold transition-colors">{m.ticker}</div>
                            <div className="text-[11.5px] text-aureus-muted truncate max-w-[13rem]">{m.company_name}</div>
                          </td>
                          <td className="px-4 py-3.5"><Figure className="text-[13.5px]">{price(m.price)}</Figure></td>
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <Figure className="text-[19px] text-aureus-text">{m.composite.toFixed(1)}</Figure>
                              <StrongBuyBadge />
                            </div>
                            {m.driver_pillar && <div className="text-[11px] text-aureus-muted mt-0.5">led by {DRIVER[m.driver_pillar]}</div>}
                          </td>
                          <td className="px-4 py-3.5"><CatalystCell c={m.primary_catalyst} /></td>
                          <td className="px-4 py-3.5" title={new Date(m.entered_at).toLocaleString()}>
                            <div className="text-[12.5px] text-aureus-soft">{relativeTime(m.entered_at)}</div>
                            <div className="text-[11px] text-aureus-muted font-mono-num">{shortDate(m.entered_at)}</div>
                          </td>
                          <td
                            className="px-2 py-3.5 w-12 cursor-default"
                            onClick={(e) => { e.stopPropagation(); setExpanded(expanded === m.ticker ? null : m.ticker); }}
                          >
                            <button
                              onClick={(e) => { e.stopPropagation(); setExpanded(expanded === m.ticker ? null : m.ticker); }}
                              className="p-1.5 rounded text-aureus-muted hover:text-aureus-text hover:bg-aureus-panelhigh"
                              aria-label={`${expanded === m.ticker ? "Hide" : "Show"} detail for ${m.ticker}`}
                              aria-expanded={expanded === m.ticker}
                            >
                              <IconChevronDown className={cn("w-4 h-4 transition-transform", expanded === m.ticker && "rotate-180")} />
                            </button>
                          </td>
                        </tr>
                        {expanded === m.ticker && (
                          <tr className="border-b border-aureus-rulesoft bg-aureus-ink/40">
                            <td colSpan={7} className="px-5 py-5"><MemberDetail m={m} horizon={horizon} /></td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              </>
            )}
          </Sheet>

          {/* ── On the verge ──────────────────────────────────────── */}
          {board.candidates.length > 0 && (
            <Sheet className="overflow-hidden">
              <div className="px-5 pt-4 pb-3">
                <RuledLabel right={<span className="text-[11px] text-aureus-muted">verified, composite {board.rules.candidate_floor}+</span>}>
                  On the verge
                </RuledLabel>
              </div>
              <ul className="lg:hidden border-t border-aureus-rule divide-y divide-aureus-rulesoft">
                {board.candidates.map((c) => (
                  <li key={c.ticker}>
                    <button onClick={() => openTicker(c.ticker)} className="w-full text-left px-4 py-3 hover:bg-aureus-panellift transition-colors">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="min-w-0 truncate">
                          <span className="font-mono-num text-[14px] text-aureus-text">{c.ticker}</span>
                          <span className="text-[11.5px] text-aureus-muted"> {c.company_name}</span>
                        </span>
                        <Figure className="text-[15px] shrink-0">{c.composite.toFixed(1)}</Figure>
                      </div>
                      <div className="text-[12px] text-aureus-soft mt-0.5">{c.blocked_by}</div>
                      <div className="mt-1.5"><CatalystCell c={c.primary_catalyst} /></div>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="hidden lg:block overflow-x-auto">
                <table className="w-full min-w-[720px] text-left">
                  <thead>
                    <tr className="border-y border-aureus-rule bg-aureus-ink/30">
                      {["Ticker", "Composite", "Still missing", "Primary catalyst", "Verified"].map((h) => (
                        <th key={h} className="label-caps font-normal px-4 py-2.5">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {board.candidates.map((c: LeaderboardCandidate) => (
                      <tr key={c.ticker} onClick={() => openTicker(c.ticker)}
                          className="group border-b border-aureus-rulesoft cursor-pointer hover:bg-aureus-panellift transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-mono-num text-[14px] text-aureus-text group-hover:text-aureus-gold">{c.ticker}</div>
                          <div className="text-[11.5px] text-aureus-muted truncate max-w-[13rem]">{c.company_name}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Figure className="text-[15px]">{c.composite.toFixed(1)}</Figure>
                          <ScoreMeter score={c.composite} className="w-20 mt-1.5" />
                        </td>
                        <td className="px-4 py-3 text-[12.5px] text-aureus-soft">{c.blocked_by}</td>
                        <td className="px-4 py-3"><CatalystCell c={c.primary_catalyst} /></td>
                        <td className="px-4 py-3 text-[12px] text-aureus-muted">{relativeTime(c.verified_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Sheet>
          )}

          <div className="grid lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-6 items-start">
            {/* ── Recent moves ──────────────────────────────────────── */}
            <Sheet className="p-5">
              <RuledLabel>Recent moves</RuledLabel>
              {events.length === 0 ? (
                <p className="text-[12.5px] text-aureus-muted mt-4">No entries or exits on this horizon yet.</p>
              ) : (
                <ul className="mt-2">
                  {events.map((e) => (
                    <li key={e.id} className="flex items-start gap-3 py-2.5 border-b border-aureus-rulesoft last:border-0">
                      {e.event === "entered"
                        ? <IconArrowUpRight className="w-4 h-4 text-aureus-emerald shrink-0 mt-0.5" />
                        : <IconArrowDownRight className="w-4 h-4 text-aureus-crimson shrink-0 mt-0.5" />}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="text-[13px] text-aureus-text">
                            <Link href={`/analysis/${e.ticker}?horizon=${horizon}`} className="font-mono-num hover:text-aureus-gold">{e.ticker}</Link>
                            <span className="text-aureus-muted"> {e.event === "entered" ? "entered" : "left"}</span>
                          </span>
                          <span className="text-[11px] text-aureus-muted shrink-0">{relativeTime(e.created_at)}</span>
                        </div>
                        {e.reason && <p className="text-[12px] text-aureus-muted leading-relaxed mt-0.5">{e.reason}</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Sheet>

            {/* ── Alerts ────────────────────────────────────────────── */}
            <Sheet className="p-5 space-y-4">
              <RuledLabel>Alerts</RuledLabel>
              <p className="text-[12.5px] text-aureus-soft leading-relaxed">
                When a stock enters the board you are alerted once: in the app if you have it open, as a push notification
                if you don&apos;t. Every alert is kept behind the bell at the top of the page.
              </p>
              <PushToggle />
            </Sheet>
          </div>

          <Note>
            The board ranks what the scoring engine measures. It is not a recommendation to buy anything, and a Strong
            Buy score says nothing about position size, your circumstances, or what the market does next.
          </Note>
        </>
      )}
    </div>
  );
}
