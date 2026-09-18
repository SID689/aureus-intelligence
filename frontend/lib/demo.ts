/**
 * lib/demo.ts — the presentation environment, client and server side.
 *
 * `NEXT_PUBLIC_DEMO_MODE` is inlined at build time like every other
 * NEXT_PUBLIC_* value, so a demo build and a real build are different
 * artefacts. That is deliberate: whether this deployment hands out free
 * Institutional accounts should not be flippable at runtime.
 */

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const DEMO_BANNER_TEXT = "Institutional Demo Mode Active";
export const DEMO_BANNER_NOTE = "Unlocked Showcase Environment";

/** Tickers with a captured snapshot behind them, so they answer instantly. */
export const SHOWCASE_TICKERS = ["AAPL", "NVDA", "WMT", "TSLA"] as const;

const DEVICE_KEY = "aureus.demo.device";

/**
 * A stable per-browser token, so each visitor gets their own showcase
 * account rather than everyone editing one shared portfolio.
 *
 * Stored in localStorage and regenerated when it is unavailable — a
 * private window, or storage the browser refuses. A fresh token on every
 * visit costs one extra demo account, which is the right failure: the
 * alternative is two people in the same room sharing a book.
 */
export function deviceToken(): string {
  const fresh = () =>
    // Not security-sensitive: this names a throwaway demo account. It only
    // has to be unlikely to collide across a room of phones.
    `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;

  if (typeof window === "undefined") return fresh();
  try {
    const existing = window.localStorage.getItem(DEVICE_KEY);
    if (existing) return existing;
    const token = fresh();
    window.localStorage.setItem(DEVICE_KEY, token);
    return token;
  } catch {
    return fresh();
  }
}
