"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { LoadingRegion, Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/button";
import WordGrid from "./WordGrid";
import Keyboard from "./Keyboard";
import ResultModal from "./ResultModal";
import { startFinWordle, submitFinWordleGuess } from "@/lib/api";
import type { FinWordleMode, FinWordleSession } from "@/lib/api";

interface Props {
  userId: string;
  currentStreak: number;
  onRoundComplete: () => void;
}

export default function FinWordle({ userId, currentStreak, onRoundComplete }: Props) {
  const [mode, setMode] = useState<FinWordleMode>("daily");
  const [session, setSession] = useState<FinWordleSession | null>(null);
  const [current, setCurrent] = useState("");
  // `current` is mirrored into a ref because handleKey is async and reads the
  // in-progress guess when ENTER fires. Reading React state there would take
  // whatever value was captured when the handler was created, which goes
  // stale if several keypresses land in one batch (fast typing, a held key,
  // or programmatic input). The ref always holds the latest letters.
  // The REF is the source of truth; `current` exists only to trigger a
  // re-render. The ref must be assigned synchronously here rather than
  // inside a setState updater — React defers updaters to the end of the
  // tick, so a burst of keypresses in one tick would all read the same
  // pre-burst value and the ref would never catch up before ENTER fires.
  const currentRef = useRef("");
  const setGuess = useCallback((next: string | ((c: string) => string)) => {
    const v = typeof next === "function" ? next(currentRef.current) : next;
    currentRef.current = v;
    setCurrent(v);
  }, []);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [shake, setShake] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const load = useCallback(async (m: FinWordleMode) => {
    setLoading(true);
    setMessage(null);
    setGuess("");
    try {
      const s = await startFinWordle(userId, m);
      setSession(s);
      // A finished daily round reopens straight to its result, so the
      // educational payload isn't lost to a refresh.
      setShowModal(s.status !== "in_progress");
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : "Could not start the game");
    } finally {
      setLoading(false);
    }
  }, [userId, setGuess]);

  useEffect(() => { if (userId) load(mode); }, [userId, mode, load]);

  const flashError = (msg: string) => {
    setMessage(msg);
    setShake(true);
    setTimeout(() => setShake(false), 420);
    setTimeout(() => setMessage((m) => (m === msg ? null : m)), 2200);
  };

  const handleKey = useCallback(async (key: string) => {
    if (!session || session.status !== "in_progress" || submitting) return;

    if (key === "BACK") { setGuess((c) => c.slice(0, -1)); setMessage(null); return; }

    if (key === "ENTER") {
      const guess = currentRef.current;
      if (guess.length !== session.word_length) {
        flashError(`Needs ${session.word_length} letters`);
        return;
      }
      setSubmitting(true);
      try {
        const updated = await submitFinWordleGuess(userId, session.session_id, guess);
        setSession(updated);
        setGuess("");
        setMessage(null);
        if (updated.status !== "in_progress") {
          onRoundComplete();
          // Let the last row finish flipping before the modal covers it.
          setTimeout(() => setShowModal(true), 5 * 110 + 450);
        }
      } catch (e: unknown) {
        // A rejected word (not in dictionary) is expected user error, not a
        // failure — surface it inline and keep the letters so they can edit.
        flashError(e instanceof Error ? e.message : "Could not submit guess");
      } finally {
        setSubmitting(false);
      }
      return;
    }

    setGuess((c) => (c.length < session.word_length ? c + key : c));
  }, [session, submitting, userId, onRoundComplete, setGuess]);

  if (loading) {
    return (
      <LoadingRegion label="Loading today’s puzzle" className="max-w-xs mx-auto py-6 space-y-1.5">
        {Array.from({ length: 6 }, (_, r) => (
          <div key={r} className="grid grid-cols-5 gap-1.5">
            {Array.from({ length: 5 }, (_, c) => <Skeleton key={c} className="aspect-square" delay={r * 60 + c * 30} />)}
          </div>
        ))}
      </LoadingRegion>
    );
  }
  if (!session) {
    return (
      <div className="py-16 text-center space-y-3">
        <p className="text-aureus-crimson text-sm">{message ?? "Game unavailable"}</p>
        <Button variant="outline" size="sm" onClick={() => load(mode)}>Retry</Button>
      </div>
    );
  }

  const finished = session.status !== "in_progress";

  return (
    <div className="space-y-5">
      {showModal && finished && (
        <ResultModal
          session={session}
          currentStreak={currentStreak}
          onClose={() => setShowModal(false)}
          onPlayPractice={() => { setShowModal(false); setMode("practice"); load("practice"); }}
        />
      )}

      {/* Mode switch */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex gap-1.5">
          {(["daily", "practice"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                mode === m
                  ? "border-aureus-gold text-aureus-gold bg-aureus-gold/10"
                  : "border-aureus-rule text-aureus-muted hover:text-aureus-text"
              }`}
            >
              {m === "daily" ? "Daily Word" : "Unlimited Practice"}
            </button>
          ))}
        </div>
        {mode === "practice" && (
          <Button variant="ghost" size="sm" onClick={() => load("practice")}>New Word</Button>
        )}
      </div>

      {session.puzzle_number != null && mode === "daily" && (
        <p className="text-xs text-aureus-muted text-center font-mono">
          Puzzle #{session.puzzle_number} · same word for everyone today
        </p>
      )}

      {/* Inline message */}
      <div className="h-6 flex items-center justify-center">
        {message && (
          <span className="text-xs rounded-md border border-aureus-gold/50 bg-aureus-gold/10 text-aureus-gold px-3 py-1">
            {message}
          </span>
        )}
      </div>

      <WordGrid
        guesses={session.guesses}
        tiles={session.tiles}
        current={current}
        maxGuesses={session.max_guesses}
        wordLength={session.word_length}
        shake={shake}
      />

      {finished ? (
        <div className="text-center space-y-2 pt-2">
          <p className="text-sm text-aureus-muted">
            {session.status === "won" ? "Solved" : "Round over"}, {" "}
            <button onClick={() => setShowModal(true)} className="text-aureus-gold hover:underline">
              see what {session.answer} means
            </button>
          </p>
          {mode === "daily" && (
            <p className="text-xs text-aureus-muted">
              Next daily word tomorrow · try Unlimited Practice in the meantime
            </p>
          )}
        </div>
      ) : (
        <Keyboard keyStates={session.keyboard} onKey={handleKey} disabled={submitting} />
      )}
    </div>
  );
}
