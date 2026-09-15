import type { Config } from "tailwindcss";

/**
 * Aureus design tokens.
 *
 * Colours are declared twice on purpose: as CSS custom properties in
 * globals.css (for inline styles and chart libraries that need a runtime
 * value) and as literals here (so Tailwind can generate utilities at build
 * time). globals.css is the reference; this file mirrors it.
 *
 * Every text colour below was checked against every surface for WCAG AA
 * contrast (4.5:1). The tightest pairing is crimson on panelhigh at 4.8:1.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    // REPLACED, not extended. The scale tops out at 3px, so a stray
    // `rounded-xl` renders square rather than reintroducing soft corners.
    // `full` survives for the one legitimate use: small status dots.
    borderRadius: {
      none: "0",
      sm: "2px",
      DEFAULT: "2px",
      md: "3px",
      lg: "3px",
      xl: "3px",
      "2xl": "3px",
      "3xl": "3px",
      full: "9999px",
    },
    extend: {
      colors: {
        aureus: {
          // Ground and surfaces: near-black, stepped by luminance only.
          ink:       "#0b0b0a",
          panel:     "#131311",
          panellift: "#1a1a17",
          panelhigh: "#23221e",

          // Rules
          rule:       "#2d2c27",
          rulestrong: "#48463e",
          rulesoft:   "#1e1d1a",

          // The one accent that means "act"
          gold:       "#c9a45c",
          goldbright: "#e2c07c",
          golddim:    "#7b6436",

          // Direction
          emerald:       "#34ad76",
          emeraldbright: "#4fc48d",
          emeralddim:    "#1d5a3f",
          crimson:       "#ef5a5f",
          crimsonbright: "#f7797d",
          crimsondim:    "#5c1a1d",

          // Caution, for what is neither gain nor loss
          amber:    "#d99a2b",
          amberdim: "#5e4214",

          // Type
          text:  "#f2efe7",
          soft:  "#c9c5ba",
          muted: "#9a9689",

          // Charts
          grid: "#1c1c19",
        },
      },
      fontFamily: {
        sans:    ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
        mono:    ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      // One shadow, for surfaces that genuinely float above the page:
      // dropdowns, drawers, modals and chart tooltips. Cards and buttons
      // separate from the ground by luminance and a hairline, never by a
      // cast shadow.
      boxShadow: {
        overlay: "0 18px 48px -12px rgba(0, 0, 0, 0.85)",
      },
      letterSpacing: {
        caps: "0.16em",
      },
    },
  },
  plugins: [],
};
export default config;
