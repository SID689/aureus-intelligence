"use client";
/**
 * The button behind a scanned QR code.
 *
 * It signs in immediately on mount rather than waiting for a tap. That is
 * the whole point of the link: somebody has already pointed a camera at a
 * code and chosen to open it, and making them then find a button on a
 * phone in a dark room is friction with no purpose. The disclosure below
 * stays on screen while it happens, so nobody is signed in to something
 * they were not told about.
 *
 * If provisioning fails the automatic attempt stops there and a manual
 * button appears with the reason. An auto-retry loop would hammer the
 * endpoint from every phone in the room at once.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { ErrorNote } from "@/components/ui/primitives";
import { IconArrowRight } from "@/components/ui/icons";
import { deviceToken } from "@/lib/demo";

type State = "idle" | "entering" | "failed";

export default function DemoEntry({ auto = true }: { auto?: boolean }) {
  const [state, setState] = useState<State>(auto ? "entering" : "idle");
  const [error, setError] = useState<string | null>(null);
  const attempted = useRef(false);

  const enter = useCallback(async () => {
    setState("entering");
    setError(null);
    const res = await signIn("demo", {
      device: deviceToken(),
      redirect: false,
      callbackUrl: "/",
    });
    if (res?.ok) {
      // A full navigation, not router.push: the dashboard is a server
      // component tree that reads the session cookie, and a client-side
      // transition can render it against the pre-sign-in session.
      window.location.href = "/";
      return;
    }
    setState("failed");
    setError(
      res?.error === "CredentialsSignin"
        ? "The showcase environment did not issue a session. Demo mode may be switched off on this deployment."
        : res?.error || "The showcase session could not be started.",
    );
  }, []);

  useEffect(() => {
    if (!auto || attempted.current) return;
    attempted.current = true;
    void enter();
  }, [auto, enter]);

  return (
    <div className="space-y-4">
      <Button
        onClick={() => void enter()}
        disabled={state === "entering"}
        size="lg"
        className="w-full min-h-[48px]"
      >
        {state === "entering" ? "Opening the showcase environment" : "Enter Institutional Demo"}
        {state !== "entering" && <IconArrowRight className="w-4 h-4" />}
      </Button>

      {state === "entering" && (
        <p className="text-[12px] text-aureus-muted" role="status" aria-live="polite">
          Provisioning a private showcase account on the Institutional plan.
        </p>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
    </div>
  );
}
