"use client";
import { useReducer, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  ArrowRight, ArrowLeft, Check, ScrollText, LineChart, Newspaper,
  AlertTriangle, Lightbulb, Layers, PenLine, Sparkles,
} from "lucide-react";
import Logo from "@/components/brand/Logo";
import {
  onboardingReducer, initialOnboardingState, buildCompletionPayload,
  allPillarsSeen, orderedSteps, stepIndex, partialScore,
  STEP_LABELS, PILLAR_IDS,
  type OnboardingState, type OnboardingAction, type PillarId, type OnboardingStep,
} from "./stateMachine";
import {
  METHODOLOGIES, SYNTHESIS_NOTE, SOPHISTICATION_QUESTIONS, TIER_RESULT,
} from "./content";

/**
 * Onboarding.
 *
 * ── WHY IT NO LONGER LOOKS LIKE A FORM ──────────────────────────────
 * The previous version was eight centred rectangles, each a wall of
 * prose with Back and Continue at the bottom. It taught the material and
 * nobody finished it.
 *
 * Three structural changes:
 *
 *  1. The three pillar screens collapsed into ONE lateral explorer. The
 *     learner picks a pillar, and a composite meter fills as each is
 *     opened — so the ensemble idea is demonstrated by the interface
 *     rather than explained on a fourth screen afterwards.
 *
 *  2. Detail moved behind tabs. The gist is always visible; "what it
 *     depends on" and "where it breaks" are one tap away. Progressive
 *     disclosure, so the page is short for the impatient and complete
 *     for the curious.
 *
 *  3. The diagnostic asks ONE question per screen, full width, with a
 *     calibration meter that moves as you answer. Answering advances
 *     automatically — a Continue tap per question doubles the
 *     interaction cost and adds nothing.
 *
 * The persistent left rail replaces the anonymous progress bar: you can
 * see the whole flow, where you are in it, and that it is short.
 */

const PILLAR_ICON: Record<PillarId, typeof ScrollText> = {
  fundamental: ScrollText,
  technical: LineChart,
  sentiment: Newspaper,
};

export default function OnboardingWizard() {
  const router = useRouter();
  const { data: session } = useSession();
  const [state, dispatch] = useReducer(onboardingReducer, initialOnboardingState);
  const [submitting, setSubmitting] = useState(false);

  const handleFinish = async () => {
    if (!session?.user?.id) { router.push("/"); return; }
    const payload = buildCompletionPayload(session.user.id, state);
    if (!payload) return;
    setSubmitting(true);
    try {
      // Persisted via consent_records (Phase 1 schema) — best-effort;
      // don't block the user from entering the app if this call fails.
      await fetch("/api/v1/onboarding/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).catch(() => null);
    } finally {
      setSubmitting(false);
      router.push("/");
    }
  };

  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg)" }}>
      <style>{`
        @keyframes fadeSlide { from { opacity: 0; transform: translateY(10px) } to { opacity: 1; transform: none } }
        .panel-in { animation: fadeSlide .45s cubic-bezier(.22,1,.36,1) both; }
        @keyframes popIn { from { opacity: 0; transform: scale(.94) } to { opacity: 1; transform: none } }
        .pop-in { animation: popIn .4s cubic-bezier(.22,1,.36,1) both; }
        .d1{animation-delay:.04s}.d2{animation-delay:.09s}.d3{animation-delay:.14s}.d4{animation-delay:.19s}
        @media (prefers-reduced-motion: reduce) {
          .panel-in, .pop-in { animation: none; opacity: 1; transform: none; }
        }
      `}</style>

      <ProgressRail step={state.step} />

      <main className="flex-1 min-w-0 flex flex-col">
        <MobileProgress step={state.step} />
        <div className="flex-1 flex items-center justify-center px-6 py-10">
          <div className="w-full max-w-3xl">
            {state.step === "welcome" && <WelcomeStep onNext={() => dispatch({ type: "NEXT" })} />}
            {state.step === "pillars" && <PillarsStep state={state} dispatch={dispatch} />}
            {state.step === "diagnostic" && <DiagnosticStep state={state} dispatch={dispatch} />}
            {state.step === "risk_acknowledgment" && (
              <SignatureStep
                onBack={() => dispatch({ type: "BACK" })}
                onSign={(fullName, r, n) => {
                  dispatch({ type: "SIGN", fullName, acknowledgedRisks: r, acknowledgedNotAdvice: n });
                  dispatch({ type: "NEXT" });
                }}
              />
            )}
            {state.step === "complete" && (
              <CompleteStep tier={state.sophisticationTier} onFinish={handleFinish} submitting={submitting} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

// ── Chrome ────────────────────────────────────────────────────────────

function ProgressRail({ step }: { step: OnboardingStep }) {
  const steps = orderedSteps();
  const current = stepIndex(step);
  return (
    <aside className="hidden md:flex w-64 flex-shrink-0 flex-col border-r border-aureus-rule px-7 py-8"
           style={{ background: "var(--panel)" }}>
      <Logo size={30} withWordmark wordmarkClassName="text-lg" />

      <nav className="mt-12 flex-1">
        {steps.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <div key={s} className="flex gap-3.5">
              {/* Rail: dot plus the connector to the next step */}
              <div className="flex flex-col items-center">
                <div className={`w-6 h-6 rounded-full border flex items-center justify-center flex-shrink-0 transition-colors ${
                  done ? "border-aureus-verdigrisdim bg-aureus-verdigris/15"
                    : active ? "border-aureus-gold bg-aureus-gold/15"
                    : "border-aureus-rule"
                }`}>
                  {done
                    ? <Check className="w-3 h-3 text-aureus-verdigris" />
                    : <span className={`text-[10px] font-mono-num ${active ? "text-aureus-gold" : "text-aureus-muted"}`}>{i + 1}</span>}
                </div>
                {i < steps.length - 1 && (
                  <div className={`w-px flex-1 min-h-[34px] my-1 transition-colors ${
                    done ? "bg-aureus-verdigris/40" : "bg-aureus-rule"}`} />
                )}
              </div>
              <div className="pb-2">
                <div className={`text-[13px] leading-6 transition-colors ${
                  active ? "text-aureus-text font-medium" : done ? "text-aureus-muted" : "text-aureus-muted/50"}`}>
                  {STEP_LABELS[s]}
                </div>
              </div>
            </div>
          );
        })}
      </nav>

      <p className="text-[11px] text-aureus-muted/70 leading-relaxed">
        About two minutes. You can change any of this later in Settings.
      </p>
    </aside>
  );
}

/**
 * Small-screen counterpart to the rail.
 *
 * The rail is `hidden md:flex`, which left mobile with no progress
 * indication whatsoever — no logo, no step name, no sense of how long
 * the flow runs. On a narrow screen that is exactly where an unbounded
 * form feels longest, so the mobile case needs the reassurance more than
 * desktop does, not less.
 */
function MobileProgress({ step }: { step: OnboardingStep }) {
  const steps = orderedSteps();
  const current = stepIndex(step);
  const pct = ((current + 1) / steps.length) * 100;
  return (
    <div className="md:hidden border-b border-aureus-rule" style={{ background: "var(--panel)" }}>
      <div className="flex items-center justify-between px-5 py-3.5">
        <Logo size={24} withWordmark wordmarkClassName="text-base" />
        <div className="text-right">
          <div className="text-[12px] text-aureus-text leading-none">{STEP_LABELS[step]}</div>
          <div className="text-[10px] text-aureus-muted font-mono-num mt-1">
            {current + 1} of {steps.length}
          </div>
        </div>
      </div>
      <div className="h-0.5 bg-aureus-rule">
        <div className="h-0.5 bg-aureus-gold transition-all duration-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Nav({ onBack, onNext, nextLabel = "Continue", nextDisabled = false, hint }: {
  onBack?: () => void; onNext?: () => void;
  nextLabel?: string; nextDisabled?: boolean; hint?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 mt-8">
      {onBack ? (
        <button onClick={onBack}
                className="flex items-center gap-1.5 text-aureus-muted hover:text-aureus-text text-sm transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
      ) : <span />}
      <div className="flex items-center gap-4">
        {hint && <span className="text-[11px] text-aureus-muted">{hint}</span>}
        {onNext && (
          <button onClick={onNext} disabled={nextDisabled}
                  className="flex items-center gap-2 bg-aureus-gold text-aureus-ink font-semibold px-6 py-2.5 rounded-lg text-sm hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed transition-opacity">
            {nextLabel} <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Steps ─────────────────────────────────────────────────────────────

function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="panel-in">
      <div className="inline-flex items-center gap-2 text-[11px] text-aureus-gold border border-aureus-gold/30 rounded-full px-3 py-1 mb-7"
           style={{ background: "rgb(var(--gold-rgb) / 0.07)" }}>
        <Sparkles className="w-3 h-3" /> Before your first analysis
      </div>

      <h1 className="font-display text-4xl md:text-5xl text-aureus-text leading-[1.1] mb-6" style={{ fontWeight: 600 }}>
        Every number here comes<br />with its reasoning
      </h1>
      <p className="text-aureus-muted leading-relaxed max-w-xl mb-4">
        Aureus scores a stock three separate ways, then combines them. Each method answers a
        different question, and each is blind to something the others catch.
      </p>
      <p className="text-aureus-muted leading-relaxed max-w-xl mb-9">
        Two minutes here and every score on the platform becomes readable — including the times
        it tells you it isn't sure.
      </p>

      <div className="grid sm:grid-cols-3 gap-3 mb-2">
        {METHODOLOGIES.map((m, i) => {
          const Icon = PILLAR_ICON[m.id];
          return (
            <div key={m.id} className={`pop-in d${i + 1} rounded-xl border border-aureus-rule p-4`}
                 style={{ background: "var(--panel)" }}>
              <Icon className="w-5 h-5 text-aureus-gold mb-2.5" strokeWidth={1.5} />
              <div className="text-aureus-text text-sm font-medium">{m.title}</div>
              <div className="text-[11px] text-aureus-muted mt-0.5 leading-snug">{m.essence}</div>
            </div>
          );
        })}
      </div>

      <Nav onNext={onNext} nextLabel="Show me" />
    </div>
  );
}

/**
 * The three pillars, as one lateral explorer.
 *
 * The composite meter at the top is the real teaching device: it fills as
 * each pillar is opened, so by the time all three are lit the learner has
 * physically assembled the ensemble rather than read a paragraph about it.
 */
function PillarsStep({ state, dispatch }: {
  state: OnboardingState; dispatch: React.Dispatch<OnboardingAction>;
}) {
  const [tab, setTab] = useState<"depends" | "method" | "risks">("depends");
  const m = METHODOLOGIES.find((x) => x.id === state.activePillar)!;
  const Icon = PILLAR_ICON[m.id];
  const ready = allPillarsSeen(state);
  const remaining = PILLAR_IDS.filter((p) => !state.seenPillars.includes(p)).length;

  const select = (p: PillarId) => { dispatch({ type: "VIEW_PILLAR", pillar: p }); setTab("depends"); };

  return (
    <div className="panel-in">
      {/* Assembly meter */}
      <div className="mb-7">
        <div className="flex items-baseline justify-between mb-2.5">
          <h2 className="font-display text-2xl text-aureus-text" style={{ fontWeight: 600 }}>The three pillars</h2>
          <span className="text-[11px] text-aureus-muted">
            {state.seenPillars.length} of 3 explored
          </span>
        </div>
        <div className="flex gap-1.5">
          {PILLAR_IDS.map((p) => (
            <div key={p} className="flex-1 h-1.5 rounded-full overflow-hidden bg-aureus-rule">
              <div className="h-full rounded-full transition-all duration-500"
                   style={{
                     width: state.seenPillars.includes(p) ? "100%" : "0%",
                     background: "var(--gold)",
                   }} />
            </div>
          ))}
        </div>
      </div>

      {/* Pillar selector */}
      <div className="grid grid-cols-3 gap-2.5 mb-6">
        {METHODOLOGIES.map((pm) => {
          const PIcon = PILLAR_ICON[pm.id];
          const active = pm.id === state.activePillar;
          const seen = state.seenPillars.includes(pm.id);
          return (
            <button key={pm.id} onClick={() => select(pm.id)}
                    className={`text-left rounded-xl border p-3.5 transition-all ${
                      active ? "border-aureus-gold" : "border-aureus-rule hover:border-aureus-muted"
                    }`}
                    style={{ background: active ? "rgb(var(--gold-rgb) / 0.07)" : "var(--panel)" }}>
              <div className="flex items-center justify-between mb-1.5">
                <PIcon className={`w-4 h-4 ${active ? "text-aureus-gold" : "text-aureus-muted"}`} strokeWidth={1.5} />
                {seen && <Check className="w-3 h-3 text-aureus-verdigris" />}
              </div>
              <div className={`text-[13px] font-medium ${active ? "text-aureus-gold" : "text-aureus-text"}`}>
                {pm.title}
              </div>
            </button>
          );
        })}
      </div>

      {/* Active pillar */}
      <div key={m.id} className="panel-in rounded-2xl border border-aureus-rule overflow-hidden"
           style={{ background: "var(--panel)" }}>
        <div className="p-6 md:p-7">
          <div className="flex items-start gap-3.5 mb-5">
            <div className="w-11 h-11 rounded-xl border border-aureus-gold/30 flex items-center justify-center flex-shrink-0"
                 style={{ background: "rgb(var(--gold-rgb) / 0.08)" }}>
              <Icon className="w-5 h-5 text-aureus-gold" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <h3 className="font-display text-2xl text-aureus-text leading-tight" style={{ fontWeight: 600 }}>
                {m.title}
              </h3>
              <p className="text-aureus-gold text-[13px] mt-1">{m.tagline}</p>
            </div>
          </div>

          {/* The one sentence to remember */}
          <div className="rounded-xl border border-aureus-gold/25 p-4 mb-5 flex gap-3"
               style={{ background: "rgb(var(--gold-rgb) / 0.05)" }}>
            <Lightbulb className="w-4 h-4 text-aureus-gold flex-shrink-0 mt-0.5" strokeWidth={1.75} />
            <p className="text-[13px] text-aureus-text leading-relaxed">{m.keyIdea}</p>
          </div>

          <p className="text-sm text-aureus-muted leading-relaxed mb-3">{m.whatItIs}</p>
          <p className="text-sm text-aureus-muted/80 leading-relaxed mb-6">{m.whyThisHorizon}</p>

          {/* Weight by horizon — shows why the blend shifts */}
          <div className="rounded-xl border border-aureus-rule p-4 mb-6" style={{ background: "var(--bg)" }}>
            <div className="text-[10px] uppercase tracking-widest text-aureus-muted mb-3">
              How much this pillar counts
            </div>
            <div className="space-y-2">
              {m.weightByHorizon.map((w) => (
                <div key={w.horizon} className="flex items-center gap-3">
                  <span className="w-14 text-[11px] text-aureus-muted">{w.horizon}</span>
                  <div className="flex-1 h-2 rounded-full bg-aureus-rule overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700"
                         style={{ width: `${w.pct}%`, background: "var(--gold)" }} />
                  </div>
                  <span className="w-9 text-right font-mono-num text-[11px] text-aureus-gold">{w.pct}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Detail behind tabs */}
          <div className="flex gap-1 border-b border-aureus-rule mb-4">
            {([
              ["depends", "Depends on"],
              ["method", "Core method"],
              ["risks", "Where it breaks"],
            ] as const).map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                      className={`px-3.5 py-2 text-[12px] border-b-2 -mb-px transition-colors ${
                        tab === id
                          ? "border-aureus-gold text-aureus-gold"
                          : "border-transparent text-aureus-muted hover:text-aureus-text"
                      }`}>
                {label}
              </button>
            ))}
          </div>

          <div key={tab} className="panel-in min-h-[132px]">
            {tab === "depends" && (
              <div className="space-y-2.5">
                {m.dependsOn.map((d) => (
                  <div key={d.label} className="text-[13px]">
                    <span className="text-aureus-text font-medium">{d.label}</span>
                    <span className="text-aureus-muted"> — {d.detail}</span>
                  </div>
                ))}
              </div>
            )}
            {tab === "method" && (
              <div>
                <div className="text-[13px] text-aureus-gold font-medium mb-1.5">{m.coreMethod.name}</div>
                <p className="text-[13px] text-aureus-muted leading-relaxed">{m.coreMethod.explanation}</p>
              </div>
            )}
            {tab === "risks" && (
              <div className="space-y-3">
                {m.risks.map((r) => (
                  <div key={r.label} className="text-[13px]">
                    <span className="text-aureus-oxblood font-medium">{r.label}</span>
                    <span className="text-aureus-muted"> — {r.detail}</span>
                  </div>
                ))}
                <div className="flex gap-2.5 pt-3 border-t border-aureus-rule">
                  <AlertTriangle className="w-4 h-4 text-aureus-oxblood flex-shrink-0 mt-0.5" strokeWidth={1.75} />
                  <p className="text-[13px] text-aureus-muted leading-relaxed">
                    <span className="text-aureus-text font-medium">Blind spot: </span>{m.blindSpot}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* The synthesis, revealed only once all three are explored —
            it is the payoff, and it does not land before then. */}
        {ready && (
          <div className="pop-in border-t border-aureus-rule p-6 md:p-7" style={{ background: "var(--bg)" }}>
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-aureus-verdigris" strokeWidth={1.75} />
              <span className="text-[11px] uppercase tracking-widest text-aureus-verdigris">
                All three explored — here's why they're combined
              </span>
            </div>
            <p className="text-[13px] text-aureus-muted leading-relaxed">{SYNTHESIS_NOTE}</p>
          </div>
        )}
      </div>

      <Nav
        onBack={() => dispatch({ type: "BACK" })}
        onNext={() => dispatch({ type: "NEXT" })}
        nextDisabled={!ready}
        nextLabel={ready ? "Continue" : "Explore all three"}
        hint={ready ? undefined : `${remaining} pillar${remaining === 1 ? "" : "s"} left`}
      />
    </div>
  );
}

/** One question per screen, with a live calibration meter. */
function DiagnosticStep({ state, dispatch }: {
  state: OnboardingState; dispatch: React.Dispatch<OnboardingAction>;
}) {
  const total = SOPHISTICATION_QUESTIONS.length;
  const q = SOPHISTICATION_QUESTIONS[state.questionIndex];
  const answered = SOPHISTICATION_QUESTIONS.filter((x) => state.answers[x.id]).length;
  const allAnswered = answered === total;
  const { score, max } = partialScore(state.answers);
  const selected = state.answers[q.id];

  return (
    <div className="panel-in">
      <div className="flex items-baseline justify-between mb-2.5">
        <h2 className="font-display text-2xl text-aureus-text" style={{ fontWeight: 600 }}>Calibration</h2>
        <span className="text-[11px] text-aureus-muted font-mono-num">
          {state.questionIndex + 1} / {total}
        </span>
      </div>

      {/* Per-question progress, so the length is visible up front */}
      <div className="flex gap-1.5 mb-8">
        {SOPHISTICATION_QUESTIONS.map((x, i) => (
          <div key={x.id} className="flex-1 h-1 rounded-full overflow-hidden bg-aureus-rule">
            <div className="h-full rounded-full transition-all duration-500"
                 style={{
                   width: state.answers[x.id] ? "100%" : i === state.questionIndex ? "35%" : "0%",
                   background: state.answers[x.id] ? "var(--verdigris)" : "var(--gold)",
                 }} />
          </div>
        ))}
      </div>

      <div key={q.id} className="panel-in">
        <h3 className="font-display text-3xl text-aureus-text leading-tight mb-2.5" style={{ fontWeight: 600 }}>
          {q.question}
        </h3>
        <p className="text-[13px] text-aureus-muted mb-7">{q.helper}</p>

        <div className="grid sm:grid-cols-2 gap-3">
          {q.options.map((opt, i) => {
            const active = selected === opt.value;
            return (
              <button key={opt.value}
                      onClick={() => dispatch({ type: "ANSWER_QUESTION", questionId: q.id, value: opt.value })}
                      className={`pop-in d${i + 1} text-left rounded-xl border p-4 transition-all group ${
                        active ? "border-aureus-gold" : "border-aureus-rule hover:border-aureus-muted"
                      }`}
                      style={{ background: active ? "rgb(var(--gold-rgb) / 0.07)" : "var(--panel)" }}>
                <div className="flex items-start justify-between gap-2.5">
                  <div className="min-w-0">
                    <div className={`text-sm font-medium ${active ? "text-aureus-gold" : "text-aureus-text"}`}>
                      {opt.label}
                    </div>
                    <div className="text-[11px] text-aureus-muted mt-1 leading-snug">{opt.detail}</div>
                  </div>
                  <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors ${
                    active ? "border-aureus-gold bg-aureus-gold" : "border-aureus-rule group-hover:border-aureus-muted"
                  }`}>
                    {active && <Check className="w-2.5 h-2.5 text-aureus-ink" strokeWidth={3} />}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Live calibration meter — makes the diagnostic feel like it is
          doing something rather than collecting answers into a void. */}
      <div className="mt-8 rounded-xl border border-aureus-rule p-4" style={{ background: "var(--panel)" }}>
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-[10px] uppercase tracking-widest text-aureus-muted">Detail level</span>
          <span className="text-[11px] text-aureus-gold">
            {answered === 0 ? "Answer to calibrate"
              : score / max >= 0.7 ? "Direct"
              : score / max >= 0.35 ? "Balanced" : "Guided"}
          </span>
        </div>
        <div className="relative h-1.5 rounded-full bg-aureus-rule overflow-hidden">
          <div className="h-full rounded-full transition-all duration-700"
               style={{ width: `${max ? (score / max) * 100 : 0}%`, background: "var(--gold)" }} />
        </div>
        <div className="flex justify-between text-[10px] text-aureus-muted mt-1.5">
          <span>More explanation</span><span>Less explanation</span>
        </div>
      </div>

      <Nav
        onBack={() => dispatch({ type: "BACK" })}
        onNext={() => { dispatch({ type: "COMPLETE_QUIZ" }); dispatch({ type: "NEXT" }); }}
        nextDisabled={!allAnswered}
        nextLabel="See my result"
        hint={allAnswered ? undefined : `${total - answered} to go`}
      />
    </div>
  );
}

function SignatureStep({ onSign, onBack }: {
  onSign: (fullName: string, risks: boolean, notAdvice: boolean) => void;
  onBack: () => void;
}) {
  const [name, setName] = useState("");
  const [risks, setRisks] = useState(false);
  const [notAdvice, setNotAdvice] = useState(false);
  const canSign = name.trim().length > 1 && risks && notAdvice;

  return (
    <div className="panel-in">
      <div className="flex items-center gap-2 text-[11px] text-aureus-gold mb-4">
        <PenLine className="w-3.5 h-3.5" /> Last step
      </div>
      <h2 className="font-display text-3xl text-aureus-text leading-tight mb-2" style={{ fontWeight: 600 }}>
        Risk acknowledgment
      </h2>
      <p className="text-[13px] text-aureus-muted mb-7 max-w-lg">
        Required once, then never again. This is stored with your account and timestamped.
      </p>

      <div className="rounded-xl border border-aureus-rule p-5 space-y-3 text-[13px] text-aureus-muted leading-relaxed mb-5"
           style={{ background: "var(--panel)" }}>
        <p>Aureus Intelligence provides software-generated informational analysis only. Nothing on this
           platform constitutes investment, legal, or tax advice, nor a recommendation to buy, hold, or
           sell any security.</p>
        <p>Past performance, including any backtested results, is not indicative of future results. All
           trading involves risk of loss, including the potential loss of principal.</p>
        <p>Every confidence score and signal you see is a statistical model estimate with inherent
           uncertainty. It is not a guarantee of any outcome. You are solely responsible for your own
           trading and investment decisions.</p>
      </div>

      <div className="space-y-2.5 mb-6">
        {[
          [risks, setRisks, "I understand that all trading involves risk of loss, and that Aureus's analysis carries inherent uncertainty."],
          [notAdvice, setNotAdvice, "I understand that nothing on this platform constitutes personalized financial advice."],
        ].map(([checked, setter, label], i) => (
          <button key={i}
                  onClick={() => (setter as (v: boolean) => void)(!(checked as boolean))}
                  className={`w-full text-left flex items-start gap-3 rounded-xl border p-3.5 transition-colors ${
                    checked ? "border-aureus-gold/50" : "border-aureus-rule hover:border-aureus-muted"
                  }`}
                  style={{ background: checked ? "rgb(var(--gold-rgb) / 0.05)" : "var(--panel)" }}>
            <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors ${
              checked ? "border-aureus-gold bg-aureus-gold" : "border-aureus-rule"
            }`}>
              {(checked as boolean) && <Check className="w-2.5 h-2.5 text-aureus-ink" strokeWidth={3} />}
            </div>
            <span className="text-[13px] text-aureus-muted leading-relaxed">{label as string}</span>
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-aureus-rule p-5" style={{ background: "var(--panel)" }}>
        <label className="text-[10px] uppercase tracking-widest text-aureus-muted">
          Type your full legal name to sign
        </label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Jane A. Trader"
          className="w-full bg-transparent border-b border-aureus-rule focus:border-aureus-gold px-0 py-2.5 mt-2
                     text-aureus-text text-xl font-display italic focus:outline-none transition-colors"
          style={{ fontWeight: 400 }}
        />
        <p className="text-[10px] text-aureus-muted mt-2">
          Constitutes your digital signature, timestamped and stored with your account.
        </p>
      </div>

      <Nav onBack={onBack} onNext={() => onSign(name, risks, notAdvice)}
           nextDisabled={!canSign} nextLabel="Sign and continue" />
    </div>
  );
}

function CompleteStep({ tier, onFinish, submitting }: {
  tier: string | null; onFinish: () => void; submitting: boolean;
}) {
  const result = TIER_RESULT[tier ?? "novice"] ?? TIER_RESULT.novice;
  return (
    <div className="panel-in text-center">
      <div className="pop-in w-16 h-16 rounded-2xl border border-aureus-verdigrisdim/40 flex items-center justify-center mx-auto mb-7"
           style={{ background: "rgb(var(--verdigris-rgb) / 0.1)" }}>
        <Check className="w-8 h-8 text-aureus-verdigris" strokeWidth={2} />
      </div>

      <h2 className="font-display text-4xl text-aureus-text leading-tight mb-3" style={{ fontWeight: 600 }}>
        You're set up
      </h2>
      <p className="text-[13px] text-aureus-muted mb-8">
        Your interface is calibrated to{" "}
        <span className="text-aureus-gold font-medium">{result.title}</span>.
      </p>

      <div className="rounded-2xl border border-aureus-rule p-6 text-left mb-8 max-w-xl mx-auto"
           style={{ background: "var(--panel)" }}>
        <div className="text-[10px] uppercase tracking-widest text-aureus-gold mb-2.5">
          What that means
        </div>
        <p className="text-[13px] text-aureus-muted leading-relaxed">{result.body}</p>
        <p className="text-[11px] text-aureus-muted/70 mt-4 pt-4 border-t border-aureus-rule">
          Change this any time in Settings — it adjusts on its own as you complete lessons.
        </p>
      </div>

      <button onClick={onFinish} disabled={submitting}
              className="inline-flex items-center gap-2 bg-aureus-gold text-aureus-ink font-semibold px-7 py-3 rounded-lg hover:opacity-90 disabled:opacity-40 transition-opacity">
        {submitting ? "Finishing…" : "Enter Aureus"} <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}
