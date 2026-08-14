"use client";
import { useReducer, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";
import {
  onboardingReducer, initialOnboardingState, stepProgress,
  isSignatureValid, buildCompletionPayload,
} from "./stateMachine";
import { METHODOLOGIES, SYNTHESIS_NOTE, SOPHISTICATION_QUESTIONS } from "./content";

export default function OnboardingWizard() {
  const router = useRouter();
  const { data: session } = useSession();
  const [state, dispatch] = useReducer(onboardingReducer, initialOnboardingState);
  const [nameInput, setNameInput] = useState("");
  const [ackRisks, setAckRisks] = useState(false);
  const [ackNotAdvice, setAckNotAdvice] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const progress = stepProgress(state.step);

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
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      {/* Progress bar */}
      <div className="w-full h-1 bg-aureus-border">
        <div className="h-1 bg-aureus-gold transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-2xl">

          {state.step === "welcome" && (
            <WelcomeStep onNext={() => dispatch({ type: "NEXT" })} />
          )}

          {(state.step === "fundamental" || state.step === "technical" || state.step === "sentiment") && (
            <MethodologyStep
              methodology={METHODOLOGIES.find((m) => m.id === state.step)!}
              onNext={() => dispatch({ type: "NEXT" })}
              onBack={() => dispatch({ type: "BACK" })}
            />
          )}

          {state.step === "synthesis" && (
            <SynthesisStep onNext={() => dispatch({ type: "NEXT" })} onBack={() => dispatch({ type: "BACK" })} />
          )}

          {state.step === "sophistication_quiz" && (
            <QuizStep
              answers={state.answers}
              onAnswer={(id, value) => dispatch({ type: "ANSWER_QUESTION", questionId: id, value })}
              onNext={() => { dispatch({ type: "COMPLETE_QUIZ" }); dispatch({ type: "NEXT" }); }}
              onBack={() => dispatch({ type: "BACK" })}
            />
          )}

          {state.step === "risk_acknowledgment" && (
            <SignatureStep
              nameInput={nameInput} setNameInput={setNameInput}
              ackRisks={ackRisks} setAckRisks={setAckRisks}
              ackNotAdvice={ackNotAdvice} setAckNotAdvice={setAckNotAdvice}
              onBack={() => dispatch({ type: "BACK" })}
              onSign={() => {
                dispatch({ type: "SIGN", fullName: nameInput, acknowledgedRisks: ackRisks, acknowledgedNotAdvice: ackNotAdvice });
                dispatch({ type: "NEXT" });
              }}
              canSign={nameInput.trim().length > 1 && ackRisks && ackNotAdvice}
            />
          )}

          {state.step === "complete" && (
            <CompleteStep
              tier={state.sophisticationTier}
              onFinish={handleFinish}
              submitting={submitting}
            />
          )}

        </div>
      </div>
    </div>
  );
}

// ── Step components ─────────────────────────────────────────────────────────

function StepShell({ children, onNext, onBack, nextLabel = "Continue", nextDisabled = false }: {
  children: React.ReactNode; onNext?: () => void; onBack?: () => void;
  nextLabel?: string; nextDisabled?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-aureus-border p-8 space-y-6" style={{ background: "var(--surface)" }}>
      {children}
      <div className="flex items-center justify-between pt-4 border-t border-aureus-border">
        {onBack ? (
          <button onClick={onBack} className="flex items-center gap-1 text-aureus-muted hover:text-white text-sm transition-colors">
            <ChevronLeft className="w-4 h-4" /> Back
          </button>
        ) : <span />}
        {onNext && (
          <button onClick={onNext} disabled={nextDisabled}
                  className="flex items-center gap-1 bg-aureus-gold text-black font-semibold px-5 py-2 rounded-lg text-sm hover:opacity-90 disabled:opacity-40 transition-opacity">
            {nextLabel} <ChevronRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <StepShell onNext={onNext} nextLabel="Let's begin">
      <div className="text-center space-y-3">
        <div className="font-display text-aureus-gold text-2xl tracking-wide" style={{ fontWeight: 600 }}>Aureus Intelligence</div>
        <h1 className="text-white text-xl font-semibold">Before we start, a few minutes on how this actually works</h1>
        <p className="text-aureus-muted text-sm leading-relaxed max-w-lg mx-auto">
          Aureus combines three distinct analytical methodologies into every score you'll see —
          fundamental, technical, and sentiment. Each one answers a different question and has
          different blind spots. Understanding what each one can and can't tell you will make every
          number on this platform far more useful. This takes about four minutes.
        </p>
      </div>
    </StepShell>
  );
}

function MethodologyStep({ methodology, onNext, onBack }: {
  methodology: (typeof METHODOLOGIES)[number]; onNext: () => void; onBack: () => void;
}) {
  return (
    <StepShell onNext={onNext} onBack={onBack}>
      <div className="space-y-4">
        <div>
          <h2 className="text-white text-xl font-bold">{methodology.title}</h2>
          <p className="text-aureus-gold text-sm mt-1">{methodology.tagline}</p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-aureus-muted">Typical time horizon:</span>
          <span className="text-white font-medium">{methodology.timeHorizon}</span>
        </div>

        <p className="text-gray-300 text-sm leading-relaxed">{methodology.whatItIs}</p>
        <p className="text-gray-400 text-sm leading-relaxed italic">{methodology.whyThisHorizon}</p>

        <div className="rounded-lg border border-aureus-border p-4 space-y-2" style={{ background: "var(--bg)" }}>
          <div className="text-xs font-semibold text-aureus-gold uppercase tracking-wide">Depends on</div>
          {methodology.dependsOn.map((d) => (
            <div key={d.label} className="text-sm">
              <span className="text-white font-medium">{d.label}:</span>{" "}
              <span className="text-gray-400">{d.detail}</span>
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-aureus-border p-4" style={{ background: "var(--bg)" }}>
          <div className="text-xs font-semibold text-aureus-gold uppercase tracking-wide mb-1">
            Core method: {methodology.coreMethod.name}
          </div>
          <p className="text-sm text-gray-400 leading-relaxed">{methodology.coreMethod.explanation}</p>
        </div>

        <div className="rounded-lg border border-aureus-red/30 bg-red-950/10 p-4 space-y-2">
          <div className="text-xs font-semibold text-aureus-red uppercase tracking-wide">Where it breaks down</div>
          {methodology.risks.map((r) => (
            <div key={r.label} className="text-sm">
              <span className="text-white font-medium">{r.label}:</span>{" "}
              <span className="text-gray-400">{r.detail}</span>
            </div>
          ))}
          <p className="text-sm text-gray-400 pt-1 border-t border-aureus-red/20 mt-2">
            <span className="text-white font-medium">Blind spot: </span>{methodology.blindSpot}
          </p>
        </div>
      </div>
    </StepShell>
  );
}

function SynthesisStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  return (
    <StepShell onNext={onNext} onBack={onBack} nextLabel="Continue to sophistication check">
      <div className="space-y-4">
        <h2 className="text-white text-xl font-bold">Why Aureus blends all three</h2>
        <p className="text-gray-300 text-sm leading-relaxed">{SYNTHESIS_NOTE}</p>
        <div className="rounded-lg border border-aureus-gold/30 bg-amber-950/10 p-4">
          <p className="text-sm text-gray-300">
            When you see a score on this platform, check the weighting breakdown — if a module's
            weight is lower than the standard split, it means that module didn't have complete data
            for that specific stock, and the score leans more on the modules that did.
          </p>
        </div>
      </div>
    </StepShell>
  );
}

function QuizStep({ answers, onAnswer, onNext, onBack }: {
  answers: Record<string, string>; onAnswer: (id: string, value: string) => void;
  onNext: () => void; onBack: () => void;
}) {
  const allAnswered = SOPHISTICATION_QUESTIONS.every((q) => answers[q.id]);
  return (
    <StepShell onNext={onNext} onBack={onBack} nextDisabled={!allAnswered} nextLabel="See my results">
      <div className="space-y-6">
        <div>
          <h2 className="text-white text-xl font-bold">A quick sophistication check</h2>
          <p className="text-aureus-muted text-sm mt-1">
            This helps calibrate how much explanatory detail we show you by default — you can always
            change it later in Settings.
          </p>
        </div>
        {SOPHISTICATION_QUESTIONS.map((q) => (
          <div key={q.id} className="space-y-2">
            <p className="text-white text-sm font-medium">{q.question}</p>
            <div className="grid grid-cols-1 gap-2">
              {q.options.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => onAnswer(q.id, opt.value)}
                  className={`text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
                    answers[q.id] === opt.value
                      ? "border-aureus-gold bg-aureus-gold/10 text-white"
                      : "border-aureus-border text-gray-400 hover:border-aureus-muted"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </StepShell>
  );
}

function SignatureStep({
  nameInput, setNameInput, ackRisks, setAckRisks, ackNotAdvice, setAckNotAdvice, onSign, onBack, canSign,
}: {
  nameInput: string; setNameInput: (v: string) => void;
  ackRisks: boolean; setAckRisks: (v: boolean) => void;
  ackNotAdvice: boolean; setAckNotAdvice: (v: boolean) => void;
  onSign: () => void; onBack: () => void; canSign: boolean;
}) {
  return (
    <StepShell onNext={onSign} onBack={onBack} nextLabel="Sign & Continue" nextDisabled={!canSign}>
      <div className="space-y-5">
        <div>
          <h2 className="text-white text-xl font-bold">Risk acknowledgment</h2>
          <p className="text-aureus-muted text-sm mt-1">One last step before you get full access.</p>
        </div>

        <div className="rounded-lg border border-aureus-border p-4 space-y-3 text-sm text-gray-300 leading-relaxed max-h-48 overflow-y-auto"
             style={{ background: "var(--bg)" }}>
          <p>Aureus Intelligence provides software-generated informational analysis only. Nothing on this
             platform constitutes investment, legal, or tax advice, nor a recommendation to buy, hold, or
             sell any security.</p>
          <p>Past performance, including any backtested results, is not indicative of future results. All
             trading involves risk of loss, including the potential loss of principal.</p>
          <p>Every confidence score and signal you see is a statistical model estimate with inherent
             uncertainty. It is not a guarantee of any outcome. You are solely responsible for your own
             trading and investment decisions.</p>
        </div>

        <label className="flex items-start gap-2 text-sm text-gray-300 cursor-pointer">
          <input type="checkbox" checked={ackRisks} onChange={(e) => setAckRisks(e.target.checked)}
                 className="mt-0.5 accent-aureus-gold" />
          I understand that all trading involves risk of loss, and that Aureus's analysis carries
          inherent uncertainty.
        </label>
        <label className="flex items-start gap-2 text-sm text-gray-300 cursor-pointer">
          <input type="checkbox" checked={ackNotAdvice} onChange={(e) => setAckNotAdvice(e.target.checked)}
                 className="mt-0.5 accent-aureus-gold" />
          I understand that nothing on this platform constitutes personalized financial advice.
        </label>

        <div className="space-y-1">
          <label className="text-xs text-aureus-muted">Type your full legal name to sign</label>
          <input
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="Jane A. Trader"
            className="w-full bg-transparent border border-aureus-border rounded px-3 py-2 text-white text-sm font-serif italic focus:outline-none focus:border-aureus-gold"
          />
          <p className="text-xs text-aureus-muted">
            This constitutes your digital signature, timestamped and stored with your account.
          </p>
        </div>
      </div>
    </StepShell>
  );
}

function CompleteStep({ tier, onFinish, submitting }: {
  tier: string | null; onFinish: () => void; submitting: boolean;
}) {
  return (
    <StepShell onNext={onFinish} nextLabel={submitting ? "Finishing..." : "Enter Aureus Intelligence"} nextDisabled={submitting}>
      <div className="text-center space-y-4 py-4">
        <CheckCircle2 className="w-14 h-14 text-aureus-green mx-auto" />
        <h2 className="text-white text-xl font-bold">You're all set</h2>
        <p className="text-aureus-muted text-sm max-w-md mx-auto">
          Based on your answers, we've calibrated your experience level as{" "}
          <span className="text-aureus-gold font-semibold capitalize">{tier ?? "novice"}</span>.
          You can adjust this anytime in Settings.
        </p>
      </div>
    </StepShell>
  );
}
