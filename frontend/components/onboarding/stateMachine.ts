// components/onboarding/stateMachine.ts
//
// A plain reducer-based state machine (no external library) that drives
// the onboarding wizard. Each step is an explicit state; transitions are
// explicit actions. This is intentionally simple and dependency-free —
// legible enough that the whole flow can be audited in one file, which
// matters for something that ends in a compliance-relevant signature.

import { SOPHISTICATION_QUESTIONS } from "./content";

export type OnboardingStep =
  | "welcome"
  | "fundamental"
  | "technical"
  | "sentiment"
  | "synthesis"
  | "sophistication_quiz"
  | "risk_acknowledgment"
  | "complete";

const STEP_ORDER: OnboardingStep[] = [
  "welcome",
  "fundamental",
  "technical",
  "sentiment",
  "synthesis",
  "sophistication_quiz",
  "risk_acknowledgment",
  "complete",
];

export type SophisticationTier = "novice" | "intermediate" | "advanced";

export interface RiskSignature {
  fullName: string;
  signedAt: string;       // ISO-8601
  acknowledgedRisks: boolean;
  acknowledgedNotAdvice: boolean;
}

export interface OnboardingState {
  step: OnboardingStep;
  answers: Record<string, string>;
  sophisticationScore: number | null;
  sophisticationTier: SophisticationTier | null;
  signature: RiskSignature | null;
}

export type OnboardingAction =
  | { type: "NEXT" }
  | { type: "BACK" }
  | { type: "ANSWER_QUESTION"; questionId: string; value: string }
  | { type: "COMPLETE_QUIZ" }
  | { type: "SIGN"; fullName: string; acknowledgedRisks: boolean; acknowledgedNotAdvice: boolean }
  | { type: "RESET" };

export const initialOnboardingState: OnboardingState = {
  step: "welcome",
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

export function onboardingReducer(
  state: OnboardingState,
  action: OnboardingAction
): OnboardingState {
  switch (action.type) {
    case "NEXT": {
      const idx = STEP_ORDER.indexOf(state.step);
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
      const idx = STEP_ORDER.indexOf(state.step);
      const prevStep = STEP_ORDER[Math.max(idx - 1, 0)];
      return { ...state, step: prevStep };
    }

    case "ANSWER_QUESTION": {
      return {
        ...state,
        answers: { ...state.answers, [action.questionId]: action.value },
      };
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

export function stepProgress(step: OnboardingStep): number {
  return Math.round(((STEP_ORDER.indexOf(step) + 1) / STEP_ORDER.length) * 100);
}

export function isSignatureValid(sig: RiskSignature | null): boolean {
  return !!sig && sig.fullName.trim().length > 1 && sig.acknowledgedRisks && sig.acknowledgedNotAdvice;
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
