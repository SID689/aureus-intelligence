// components/onboarding/stateMachine.ts
//
// A plain reducer-based state machine (no external library) that drives
// the onboarding wizard. Each step is an explicit state; transitions are
// explicit actions. This is intentionally simple and dependency-free —
// legible enough that the whole flow can be audited in one file, which
// matters for something that ends in a compliance-relevant signature.
//
// ── FLOW REDESIGN ───────────────────────────────────────────────────
// The original flow was eight linear screens, three of which were a full
// page of prose about one pillar each, plus a fourth explaining how they
// combine. It read as homework, and the drop-off risk was obvious.
//
// The three pillar screens are now ONE step with a lateral explorer: the
// learner moves between pillars themselves and a composite meter fills as
// each is visited. Same material, a third of the scrolling, and the
// blend is demonstrated by the interface instead of described on a
// separate screen afterwards.
//
// `pillars` cannot be left until all three have been opened — see
// `allPillarsSeen`. That guard lives here rather than in the component so
// the flow cannot be skipped by a stray keypress, same reasoning as the
// signature guard below.

import { SOPHISTICATION_QUESTIONS } from "./content";

export type OnboardingStep =
  | "welcome"
  | "pillars"
  | "diagnostic"
  | "risk_acknowledgment"
  | "complete";

const STEP_ORDER: OnboardingStep[] = [
  "welcome",
  "pillars",
  "diagnostic",
  "risk_acknowledgment",
  "complete",
];

/** Labels for the progress rail. */
export const STEP_LABELS: Record<OnboardingStep, string> = {
  welcome: "Start",
  pillars: "The three pillars",
  diagnostic: "Calibration",
  risk_acknowledgment: "Acknowledgment",
  complete: "Done",
};

export type PillarId = "fundamental" | "technical" | "sentiment";
export const PILLAR_IDS: PillarId[] = ["fundamental", "technical", "sentiment"];

export type SophisticationTier = "novice" | "intermediate" | "advanced";

export interface RiskSignature {
  fullName: string;
  signedAt: string;       // ISO-8601
  acknowledgedRisks: boolean;
  acknowledgedNotAdvice: boolean;
}

export interface OnboardingState {
  step: OnboardingStep;
  /** Which pillar the explorer is showing. */
  activePillar: PillarId;
  /** Pillars the learner has actually opened. Gates leaving the step. */
  seenPillars: PillarId[];
  /** Index into SOPHISTICATION_QUESTIONS — the diagnostic asks one at a time. */
  questionIndex: number;
  answers: Record<string, string>;
  sophisticationScore: number | null;
  sophisticationTier: SophisticationTier | null;
  signature: RiskSignature | null;
}

export type OnboardingAction =
  | { type: "NEXT" }
  | { type: "BACK" }
  | { type: "VIEW_PILLAR"; pillar: PillarId }
  | { type: "ANSWER_QUESTION"; questionId: string; value: string }
  | { type: "PREV_QUESTION" }
  | { type: "COMPLETE_QUIZ" }
  | { type: "SIGN"; fullName: string; acknowledgedRisks: boolean; acknowledgedNotAdvice: boolean }
  | { type: "RESET" };

export const initialOnboardingState: OnboardingState = {
  step: "welcome",
  activePillar: "fundamental",
  seenPillars: ["fundamental"],   // the first one is open on arrival
  questionIndex: 0,
  answers: {},
  sophisticationScore: null,
  sophisticationTier: null,
  signature: null,
};

function scoreToTier(score: number, maxScore: number): SophisticationTier {
  const pct = score / maxScore;
  if (pct >= 0.7) return "advanced";
  if (pct >= 0.35) return "intermediate";
  return "novice";
}

export function allPillarsSeen(state: OnboardingState): boolean {
  return PILLAR_IDS.every((p) => state.seenPillars.includes(p));
}

export function onboardingReducer(
  state: OnboardingState,
  action: OnboardingAction
): OnboardingState {
  switch (action.type) {
    case "NEXT": {
      const idx = STEP_ORDER.indexOf(state.step);

      // Guard: all three pillars must have been opened. The whole point
      // of the step is that each pillar has a blind spot the others
      // cover, which is unlearnable from one of them.
      if (state.step === "pillars" && !allPillarsSeen(state)) return state;

      // Guard: cannot leave risk_acknowledgment without a valid signature —
      // this is the compliance-critical transition, enforced here, not
      // just in the UI, so it can't be bypassed by a stray keypress.
      if (state.step === "risk_acknowledgment") {
        const sig = state.signature;
        const valid = sig && sig.fullName.trim().length > 1 && sig.acknowledgedRisks && sig.acknowledgedNotAdvice;
        if (!valid) return state;
      }

      const nextStep = STEP_ORDER[Math.min(idx + 1, STEP_ORDER.length - 1)];
      return { ...state, step: nextStep };
    }

    case "BACK": {
      // Inside the diagnostic, Back walks the questions before it walks
      // the steps — otherwise a mis-tap on question three throws away all
      // three answers, which is the most annoying possible behaviour.
      if (state.step === "diagnostic" && state.questionIndex > 0) {
        return { ...state, questionIndex: state.questionIndex - 1 };
      }
      const idx = STEP_ORDER.indexOf(state.step);
      const prevStep = STEP_ORDER[Math.max(idx - 1, 0)];
      return { ...state, step: prevStep };
    }

    case "VIEW_PILLAR": {
      return {
        ...state,
        activePillar: action.pillar,
        seenPillars: state.seenPillars.includes(action.pillar)
          ? state.seenPillars
          : [...state.seenPillars, action.pillar],
      };
    }

    case "ANSWER_QUESTION": {
      const answers = { ...state.answers, [action.questionId]: action.value };
      // Answering advances automatically. A separate Continue tap per
      // question doubles the interaction cost for no added clarity, and
      // Back still reverses it.
      const isLast = state.questionIndex >= SOPHISTICATION_QUESTIONS.length - 1;
      return {
        ...state,
        answers,
        questionIndex: isLast ? state.questionIndex : state.questionIndex + 1,
      };
    }

    case "PREV_QUESTION": {
      return { ...state, questionIndex: Math.max(0, state.questionIndex - 1) };
    }

    case "COMPLETE_QUIZ": {
      let total = 0;
      let max = 0;
      for (const q of SOPHISTICATION_QUESTIONS) {
        const maxPoints = Math.max(...q.options.map((o) => o.points));
        max += maxPoints;
        const answer = state.answers[q.id];
        const selected = q.options.find((o) => o.value === answer);
        if (selected) total += selected.points;
      }
      const tier = scoreToTier(total, max);
      return { ...state, sophisticationScore: total, sophisticationTier: tier };
    }

    case "SIGN": {
      return {
        ...state,
        signature: {
          fullName: action.fullName,
          signedAt: new Date().toISOString(),
          acknowledgedRisks: action.acknowledgedRisks,
          acknowledgedNotAdvice: action.acknowledgedNotAdvice,
        },
      };
    }

    case "RESET":
      return initialOnboardingState;

    default:
      return state;
  }
}

export function stepIndex(step: OnboardingStep): number {
  return STEP_ORDER.indexOf(step);
}

export function stepCount(): number {
  return STEP_ORDER.length;
}

export function stepProgress(step: OnboardingStep): number {
  return Math.round(((STEP_ORDER.indexOf(step) + 1) / STEP_ORDER.length) * 100);
}

export function orderedSteps(): OnboardingStep[] {
  return [...STEP_ORDER];
}

export function isSignatureValid(sig: RiskSignature | null): boolean {
  return !!sig && sig.fullName.trim().length > 1 && sig.acknowledgedRisks && sig.acknowledgedNotAdvice;
}

/** Running diagnostic score, for the live calibration meter. */
export function partialScore(answers: Record<string, string>): { score: number; max: number } {
  let score = 0;
  let max = 0;
  for (const q of SOPHISTICATION_QUESTIONS) {
    max += Math.max(...q.options.map((o) => o.points));
    const selected = q.options.find((o) => o.value === answers[q.id]);
    if (selected) score += selected.points;
  }
  return { score, max };
}

// Payload shape sent to the backend on completion — maps directly onto
// the Phase 1 schema's consent_records table (consent_type='risk_disclosure')
// plus profiles.risk_disclosure_acknowledged_at / accredited_investor_self_attested.
export interface OnboardingCompletionPayload {
  user_id: string;
  sophistication_tier: SophisticationTier;
  sophistication_score: number;
  signature_full_name: string;
  signed_at: string;
  terms_version: string;
}

export function buildCompletionPayload(
  userId: string,
  state: OnboardingState,
  termsVersion = "v1.0"
): OnboardingCompletionPayload | null {
  if (!state.signature || !state.sophisticationTier || state.sophisticationScore === null) {
    return null;
  }
  return {
    user_id: userId,
    sophistication_tier: state.sophisticationTier,
    sophistication_score: state.sophisticationScore,
    signature_full_name: state.signature.fullName,
    signed_at: state.signature.signedAt,
    terms_version: termsVersion,
  };
}
