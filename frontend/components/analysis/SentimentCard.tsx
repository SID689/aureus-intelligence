"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Figure } from "@/components/ui/primitives";
import { IconExternal } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { SentimentPillar } from "@/lib/api";

/**
 * The sentiment pillar in detail.
 *
 * A sentiment score is only useful if you can see what produced it, so every
 * sub-stream states its sample size and every catalyst links to its article.
 * Where a stream could not be measured the panel says so, rather than
 * drawing a neutral 50 that looks like a reading.
 */

const BANDS = { bearish: 35, bullish: 66 };

function toneOf(score: number) {
  if (score >= BANDS.bullish) return { text: "text-aureus-emerald", bar: "bg-aureus-emerald", label: "Bullish" };
  if (score <= BANDS.bearish) return { text: "text-aureus-crimson", bar: "bg-aureus-crimson", label: "Bearish" };
  return { text: "text-aureus-gold", bar: "bg-aureus-gold", label: "Neutral" };
}

/** A ruler with the bearish, neutral and bullish zones drawn to scale and the reading marked on it. */
function BandScale({ score }: { score: number }) {
  const x = Math.max(0, Math.min(100, score));
  return (
    <div aria-hidden>
      <div className="relative h-2.5">
        <div className="absolute inset-y-0 left-0 bg-aureus-crimsondim" style={{ width: `${BANDS.bearish}%` }} />
        <div className="absolute inset-y-0 bg-aureus-panelhigh" style={{ left: `${BANDS.bearish}%`, width: `${BANDS.bullish - BANDS.bearish}%` }} />
        <div className="absolute inset-y-0 right-0 bg-aureus-emeralddim" style={{ left: `${BANDS.bullish}%` }} />
        <div className="absolute -top-1.5 -bottom-1.5 w-[2px] bg-aureus-text" style={{ left: `calc(${x}% - 1px)` }} />
      </div>
      <div className="relative h-4 mt-2 font-mono-num text-[10px] text-aureus-muted">
        <span className="absolute left-0">0</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${BANDS.bearish}%` }}>{BANDS.bearish}</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${BANDS.bullish}%` }}>{BANDS.bullish}</span>
        <span className="absolute right-0">100</span>
      </div>
    </div>
  );
}

function SubScore({
  label, score, computed, detail, unavailableNote,
}: { label: string; score: number; computed: boolean; detail: string; unavailableNote: string }) {
  const tone = toneOf(score);
  return (
    <div className="py-3 border-t border-aureus-rulesoft first:border-t-0 first:pt-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] text-aureus-soft">{label}</span>
        {computed
          ? <Figure className={cn("text-[14px]", tone.text)}>{score.toFixed(0)}</Figure>
          : <span className="label-caps">Not measured</span>}
      </div>
      <div className="h-1 bg-aureus-panelhigh mt-2">
        {computed && <div className={cn("h-full", tone.bar)} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />}
      </div>
      <p className="text-[11.5px] text-aureus-muted leading-snug mt-1.5">{computed ? detail : unavailableNote}</p>
    </div>
  );
}

function Velocity({ s }: { s: SentimentPillar }) {
  const v = s.polarity_velocity;
  const tone = v >= 0.15 ? "up" : v <= -0.15 ? "down" : "muted";
  const pct = Math.max(0, Math.min(100, 50 + v * 100));
  return (
    <div className="border-t border-aureus-rule pt-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="label-caps">Sentiment velocity</span>
        <Figure tone={tone} className="text-[12px]">{s.velocity_label}</Figure>
      </div>
      <div className="relative h-1.5 bg-aureus-panelhigh mt-3" aria-hidden>
        <span className="absolute -top-1 -bottom-1 left-1/2 w-px bg-aureus-rulestrong" />
        <div
          className={cn("absolute inset-y-0", v >= 0 ? "bg-aureus-emerald" : "bg-aureus-crimson")}
          style={{ left: v >= 0 ? "50%" : `${pct}%`, width: `${Math.abs(pct - 50)}%` }}
        />
      </div>
      <div className="flex justify-between font-mono-num text-[10.5px] text-aureus-muted mt-2">
        <span>24h tone {v >= 0 ? "+" : ""}{v.toFixed(2)} vs prior</span>
        <span>{s.volume_velocity != null ? `volume ${s.volume_velocity.toFixed(1)}x` : "volume n/a"}</span>
      </div>
    </div>
  );
}

export default function SentimentCard({ sentiment: s }: { sentiment: SentimentPillar }) {
  const [showSources, setShowSources] = useState(false);
  const tone = toneOf(s.score);

  return (
    <Card flat>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Sentiment</CardTitle>
        <span className={cn("label-caps", tone.text)}>{s.overall_label}</span>
      </CardHeader>

      <CardContent className="grid lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] gap-x-10 gap-y-6">
        <div className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <Figure className={cn("text-[44px] leading-none", tone.text)}>{Math.max(0, Math.min(100, s.score)).toFixed(0)}</Figure>
              <p className="text-[12px] text-aureus-muted mt-2">Confidence {(s.sentiment_confidence * 100).toFixed(0)}%</p>
            </div>
            <p className="text-[11.5px] text-aureus-muted text-right max-w-[12rem] leading-snug">
              Below {BANDS.bearish} reads bearish, {BANDS.bullish} and above bullish.
            </p>
          </div>
          <BandScale score={s.score} />
          <Velocity s={s} />
        </div>

        <div>
          <SubScore
            label="News" score={s.news_score} computed={s.news_computed}
            detail={`${s.news_document_count} articles, weighted by publisher authority and recency`}
            unavailableNote="Too few relevant articles were retrievable to score news sentiment."
          />
          <SubScore
            label="Social" score={s.social_score} computed={s.social_computed}
            detail={`${s.social_message_count} retail messages${s.social_polarity ? `, tone ${s.social_polarity >= 0 ? "+" : ""}${s.social_polarity.toFixed(2)}` : ""}`}
            unavailableNote="No retail or social messages were retrievable for this ticker."
          />
          <SubScore
            label={`SEC filing tone: ${s.sec_tone_label}`}
            score={s.sec_tone_score} computed={s.sec_tone_computed}
            detail={(s.sec_tone_detail?.form as string | undefined)
              ? `MD&A of the ${s.sec_tone_detail.form} filed ${s.sec_tone_detail.filing_date}, against the prior filing`
              : "MD&A tone against the prior comparable filing"}
            unavailableNote={s.sec_tone_label === "Computing"
              ? "The latest 10-K or 10-Q is being read in the background. Filings are large, so the reading appears on the next run."
              : "No retrievable 10-K or 10-Q for this issuer, which is common for ADRs and foreign filers."}
          />
        </div>

        <div className="lg:col-span-2 border-t border-aureus-rule pt-5">
          <p className="label-caps">High-impact coverage</p>
          {s.catalysts.length === 0 ? (
            <p className="text-[12.5px] text-aureus-muted mt-3">
              No article in the window scored strongly enough in either direction to qualify.
            </p>
          ) : (
            <ul className="mt-2">
              {s.catalysts.map((c, i) => {
                const pos = c.direction === "positive";
                return (
                  <li key={c.url || c.headline} className={cn("grid grid-cols-[3.5rem_1fr_auto] gap-3 py-2.5 items-start", i > 0 && "border-t border-aureus-rulesoft")}>
                    <Figure tone={pos ? "up" : "down"} className="text-[12px] pt-px" title={c.evidence.length ? `Driven by: ${c.evidence.join(", ")}` : undefined}>
                      {pos ? "+" : ""}{c.polarity.toFixed(2)}
                    </Figure>
                    <div className="min-w-0">
                      <p className="text-[13px] text-aureus-soft leading-snug">{c.headline}</p>
                      <p className="text-[11px] text-aureus-muted mt-0.5">{c.source} · {new Date(c.published_at).toLocaleDateString()}</p>
                    </div>
                    {c.url && (
                      <a href={c.url} target="_blank" rel="noopener noreferrer" className="p-1 text-aureus-muted hover:text-aureus-gold" aria-label="Open article">
                        <IconExternal className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="lg:col-span-2 border-t border-aureus-rule pt-4 space-y-2">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-aureus-muted">
            <span>Model <span className="text-aureus-soft font-mono-num">{s.model_used === "finbert" ? "FinBERT" : "Financial lexicon"}</span></span>
            {Object.entries(s.source_mix).map(([k, v]) => (
              <span key={k}>{k} <span className="text-aureus-soft font-mono-num">{v}</span></span>
            ))}
            {s.unavailable_sources.length > 0 && (
              <button onClick={() => setShowSources((v) => !v)} className="ml-auto text-aureus-gold hover:text-aureus-goldbright">
                {s.unavailable_sources.length} source{s.unavailable_sources.length === 1 ? "" : "s"} unavailable
              </button>
            )}
          </div>
          {showSources && (
            <dl className="border border-aureus-rule bg-aureus-ink px-3 py-2">
              {s.unavailable_sources.map((u) => (
                <div key={u.name} className="py-1.5 text-[11.5px] leading-snug">
                  <dt className="text-aureus-soft">{u.name}</dt>
                  <dd className="text-aureus-muted">{u.reason} {u.to_enable}</dd>
                </div>
              ))}
            </dl>
          )}
          <p className="text-[11px] text-aureus-muted leading-relaxed">
            Sentiment measures how a company is being discussed, not how the business is performing. It is the pillar
            easiest to manipulate, so social input is capped at a minority of this score and each poster’s influence is compressed.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
