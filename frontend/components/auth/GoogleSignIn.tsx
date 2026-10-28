"use client";
/**
 * "Continue with Google", shown only where Google is actually configured.
 *
 * lib/auth.ts registers the provider conditionally on GOOGLE_CLIENT_ID,
 * so on a deployment without that variable the provider does not exist.
 * Both auth pages nonetheless hardcoded the button, which is how this
 * shipped: a live site offering a sign-in method that silently went
 * nowhere, with no error on the page and nothing in the build log.
 *
 * getProviders() asks the server what it really has, so the button
 * follows the configuration rather than assuming it. That makes the
 * deployment the single source of truth and needs no second environment
 * variable kept in step with the first.
 *
 * It renders nothing until the answer arrives. Appearing a moment late is
 * a smaller fault than offering a dead control, and a button that
 * vanished after a click would be worse than either.
 */
import { useEffect, useState } from "react";
import { getProviders, signIn } from "next-auth/react";
import { GoogleMark } from "@/components/auth/AuthFrame";

export default function GoogleSignIn() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let alive = true;
    getProviders()
      .then((providers) => { if (alive) setEnabled(!!providers?.google); })
      .catch(() => { /* unreachable endpoint means no Google, which is the default */ });
    return () => { alive = false; };
  }, []);

  if (!enabled) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => signIn("google", { callbackUrl: "/" })}
        className="w-full h-10 border border-aureus-rulestrong rounded-sm text-[13.5px] text-aureus-text hover:border-aureus-gold transition-colors flex items-center justify-center gap-2.5"
      >
        <GoogleMark /> Continue with Google
      </button>

      <div className="flex items-center gap-3 my-6 label-caps">
        <span className="flex-1 h-px bg-aureus-rule" />or with email<span className="flex-1 h-px bg-aureus-rule" />
      </div>
    </>
  );
}
