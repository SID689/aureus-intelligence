"use client";
import { useState } from "react";
import { ExternalLink, TrendingUp, TrendingDown, Minus, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SentimentPillar } from "@/lib/api";

/**
 * The Sentiment pillar's detail panel — the third primary pillar alongside
 * Fundamental and Technical.
 *
 * Design intent: a sentiment score is only useful if you can see what
 * produced it. A bare "62/100" invites either blind trust or dismissal, so
 * every number here is one click from the articles behind it, and each
 * sub-stream states its own sample size. Where a stream could not be
 * measured, the card says so explicitly rather than rendering a neutral 50
 * that looks like a real reading.
 */

interface Props {
  sentiment: SentimentPillar;
}

const BANDS = { bullish: 66, bearish: 35 };

function toneOf(score: number) {
  if (score >= BANDS.bullish) return { color: "var(--verdigris)", text: "text-aureus-verdigris", label: "Bullish" };
  if (score <= BANDS.bearish) return { color: "var(--oxblood)", text: "text-aureus-oxblood", label: "Bearish" };
  return { color: "var(--gold)", text: "text-aureus-gold", label: "Neutral" };
}

/** Semicircular gauge with the 0-35 / 36-65 / 66-100 bands drawn in. */
function SentimentGauge({ score, label }: { score: number; label: string }) {
  const clamped = Math.max(0, Math.min(100, score));
  const tone = toneOf(score);
  // Semicircle from 180° to 360°; needle angle follows the score.
  const angle = 180 + (clamped / 100) * 180;
  const rad = (angle * Math.PI) / 180;
  const cx = 100, cy = 90, r = 68;
  const nx = cx + Math.cos(rad) * (r - 12);
  const ny = cy + Math.sin(rad) * (r - 12);

  const arc = (from: number, to: number, color: string) => {
    const a0 = 180 + (from / 100) * 180;
    const a1 = 180 + (to / 100) * 180;
    const p = (a: number) => {
      const t = (a * Math.PI) / 180;
      return [cx + Math.cos(t) * r, cy + Math.sin(t) * r];
    };
    const [x0, y0] = p(a0);
    const [x1, y1] = p(a1);
    return (
      <path d={`M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`}
            fill="none" stroke={color} strokeWidth="11" strokeLinecap="butt" />
    );
  };

  return (
    <div className="relative">
      <svg width="200" height="112" viewBox="0 0 200 112">
        {arc(0, BANDS.bearish, "var(--oxblood-dim)")}
        {arc(BANDS.bearish, BANDS.bullish, "var(--gold-dim)")}
        {arc(BANDS.bullish, 100, "var(--verdigris-dim)")}
        <line x1={cx} y1={cy} x2={nx} y2={ny}
              stroke={tone.color} strokeWidth="3" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="5" fill={tone.color} />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className={`text-2xl font-bold ${tone.text} leading-none`}>{clamped.toFixed(0)}</div>
        <div className="text-[10px] uppercase tracking-widest text-aureus-muted mt-1">{label}</div>
      </div>
    </div>
  );
}

/** Horizontal sub-score bar; renders an explicit "not measured" state. */
function SubScore({
  label, score, computed, detail, unavailableNote,
}: {
  label: string; score: number; computed: boolean;
  detail: string; unavailableNote: string;
}) {
  const tone = toneOf(score);
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wider text-aureus-muted">{label}</span>
        {computed
          ? <span className={`text-sm font-mono font-semibold ${tone.text}`}>{score.toFixed(0)}</span>
          : <span className="text-[10px] text-aureus-muted italic">not measured</span>}
      </div>
      <div className="h-1.5 rounded-full bg-aureus-rule overflow-hidden">
        {computed && (
          <div className="h-full rounded-full transition-all"
               style={{ width: `${Math.max(0, Math.min(100, score))}%`, background: tone.color }} />
        )}
      </div>
      <p className="text-[10px] text-aureus-muted leading-snug">
        {computed ? detail : unavailableNote}
      </p>
    </div>
  );
}

function VelocityMeter({ s }: { s: SentimentPillar }) {
  const v = s.polarity_velocity;
  const Icon = v >= 0.15 ? TrendingUp : v <= -0.15 ? TrendingDown : Minus;
  const tone = v >= 0.15 ? "text-aureus-verdigris" : v <= -0.15 ? "text-aureus-oxblood" : "text-aureus-muted";
  // Map -0.5..+0.5 onto 0..100% for the centre-anchored bar.
  const pct = Math.max(0, Math.min(100, 50 + v * 100));
  return (
    <div className="rounded-lg border border-aureus-rule p-3" style={{ background: "var(--bg)" }}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wider text-aureus-muted">Sentiment Velocity</span>
        <span className={`flex items-center gap-1 text-xs font-semibold ${tone}`}>
          <Icon className="w-3.5 h-3.5" />
          {s.velocity_label}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-aureus-rule mt-2 overflow-hidden">
        <div className="absolute inset-y-0 left-1/2 w-px bg-aureus-muted/50" />
        <div
          className="absolute inset-y-0 rounded-full"
          style={{
            left: v >= 0 ? "50%" : `${pct}%`,
            width: `${Math.abs(pct - 50)}%`,
            background: v >= 0 ? "var(--verdigris)" : "var(--oxblood)",
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-aureus-muted mt-1.5 font-mono">
        <span>24h tone {v >= 0 ? "+" : ""}{v.toFixed(2)} vs prior</span>
        {s.volume_velocity != null
          ? <span>volume {s.volume_velocity.toFixed(1)}×</span>
          : <span className="italic">volume n/a</span>}
      </div>
    </div>
  );
}

export default function SentimentCard({ sentiment: s }: Props) {
  const [showSources, setShowSources] = useState(false);
  const tone = toneOf(s.score);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Sentiment Analysis</CardTitle>
        <span className={`rounded px-2 py-0.5 text-[10px] font-bold tracking-wider border ${tone.text}`}
              style={{ borderColor: tone.color, background: `${tone.color}14` }}>
          {s.overall_label.toUpperCase()}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── Gauge + sub-scores ────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row gap-5 items-center sm:items-start">
          <div className="flex-shrink-0">
            <SentimentGauge score={s.score} label={s.overall_label} />
            <p className="text-[10px] text-aureus-muted text-center mt-2">
              Confidence {(s.sentiment_confidence * 100).toFixed(0)}%
            </p>
          </div>

          <div className="flex-1 w-full space-y-3">
            <SubScore
              label="News Sentiment" score={s.news_score} computed={s.news_computed}
              detail={`${s.news_document_count} articles, weighted by publisher authority and recency`}
              unavailableNote="Too few relevant articles were retrievable to score news sentiment."
            />
            <SubScore
              label="Social Sentiment" score={s.social_score} computed={s.social_computed}
              detail={`${s.social_message_count} retail messages${
                s.social_polarity ? `, tone ${s.social_polarity >= 0 ? "+" : ""}${s.social_polarity.toFixed(2)}` : ""
              }`}
              unavailableNote="No retail/social messages were retrievable for this ticker."
            />
            <SubScore
              label={`SEC Filing Tone — ${s.sec_tone_label}`}
              score={s.sec_tone_score} computed={s.sec_tone_computed}
              detail={
                (s.sec_tone_detail?.form as string | undefined)
                  ? `MD&A of the ${s.sec_tone_detail.form} filed ${s.sec_tone_detail.filing_date}, versus the prior filing`
                  : "MD&A tone versus the prior comparable filing"
              }
              unavailableNote={
                s.sec_tone_label === "Computing"
                  ? "Reading the latest 10-K/10-Q in the background — filings are large, so this appears on the next run."
                  : "No retrievable 10-K/10-Q for this issuer (common for ADRs and foreign filers)."
              }
            />
          </div>
        </div>

        <VelocityMeter s={s} />

        {/* ── Catalysts ─────────────────────────────────────────── */}
        <div>
          <h4 className="text-[11px] uppercase tracking-wider text-aureus-muted mb-2">
            High-Impact Catalysts
          </h4>
          {s.catalysts.length === 0 ? (
            <p className="text-[11px] text-aureus-muted">
              No article in the window scored strongly enough in either direction to qualify as a catalyst.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {s.catalysts.map((c) => {
                const pos = c.direction === "positive";
                return (
                  <li key={c.url || c.headline}
                      className="flex items-start gap-2 rounded-md border border-aureus-rule p-2"
                      style={{ background: "var(--bg)" }}>
                    <span
                      className={`mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold font-mono flex-shrink-0 ${
                        pos ? "bg-aureus-verdigris/10 text-aureus-verdigris" : "bg-aureus-oxblood/10 text-aureus-oxblood"
                      }`}
                      title={c.evidence.length ? `Driven by: ${c.evidence.join(", ")}` : undefined}
                    >
                      {pos ? "+" : ""}{c.polarity.toFixed(2)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] text-aureus-text leading-snug">{c.headline}</p>
                      <p className="text-[10px] text-aureus-muted mt-0.5">
                        {c.source} · {new Date(c.published_at).toLocaleDateString()}
                      </p>
                    </div>
                    {c.url && (
                      <a href={c.url} target="_blank" rel="noopener noreferrer"
                         className="text-aureus-muted hover:text-aureus-gold flex-shrink-0"
                         aria-label="Open article">
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* ── Provenance ────────────────────────────────────────── */}
        <div className="pt-2 border-t border-aureus-rule space-y-2">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-aureus-muted">
            <span>
              Model:{" "}
              <span className="text-aureus-text font-mono">
                {s.model_used === "finbert" ? "FinBERT" : "Financial lexicon"}
              </span>
            </span>
            {Object.entries(s.source_mix).map(([k, v]) => (
              <span key={k}>{k}: <span className="text-aureus-text font-mono">{v}</span></span>
            ))}
            {s.unavailable_sources.length > 0 && (
              <button onClick={() => setShowSources((v) => !v)}
                      className="flex items-center gap-1 text-aureus-gold hover:underline ml-auto">
                <Info className="w-3 h-3" />
                {s.unavailable_sources.length} source
                {s.unavailable_sources.length === 1 ? "" : "s"} unavailable
              </button>
            )}
          </div>

          {showSources && (
            <div className="space-y-1.5 rounded-md border border-aureus-rule p-2"
                 style={{ background: "var(--bg)" }}>
              {s.unavailable_sources.map((u) => (
                <div key={u.name} className="text-[10px] leading-snug">
                  <span className="text-aureus-text font-medium">{u.name}</span>
                  <span className="text-aureus-muted"> — {u.reason}</span>
                  <div className="text-aureus-muted/70 italic">{u.to_enable}</div>
                </div>
              ))}
            </div>
          )}

          <p className="text-[10px] text-aureus-muted leading-relaxed">
            Sentiment measures how a company is being discussed, not how the business is performing.
            It is the most easily manipulated of the three pillars, so social input is capped at a
            minority of this score and per-poster influence is compressed.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
