import type { Config } from "tailwindcss";

/**
 * Colours are declared twice on purpose: as CSS custom properties in
 * globals.css (for inline styles, chart libraries and anything that needs
 * a runtime value) and as literals here (so Tailwind can generate the
 * utility classes at build time). They must be kept in step — globals.css
 * is the reference; this file mirrors it.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        aureus: {
          // Ground and surfaces
          ink:        "#101309",
          panel:      "#191d12",
          panellift:  "#232719",
          panelhigh:  "#2c3120",

          // Rules
          rule:       "#3a3728",
          rulestrong: "#57523c",
          rulesoft:   "#2a2820",

          // Accent
          gold:       "#d9b478",
          goldbright: "#ecca94",
          golddim:    "#8a7145",

          // Direction
          verdigris:       "#83bda2",
          verdigrisbright: "#a3d4bd",
          verdigrisdim:    "#3f6552",
          oxblood:         "#c46e6e",
          oxbloodbright:   "#dc9090",
          oxblooddim:      "#6d3a3a",

          // Caution
          amber:    "#d8a24a",
          amberdim: "#6d5227",

          // Type
          text:  "#f4f1e6",
          soft:  "#cdc8b6",
          muted: "#9c9783",

          // Charts
          grid: "#262a1c",

          // Legacy aliases — kept so any not-yet-converted className still
          // resolves to a real colour instead of silently dropping out.
          bg:      "#101309",
          surface: "#191d12",
          border:  "#3a3728",
          green:   "#83bda2",
          red:     "#c46e6e",
        },
      },
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
        mono:    ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        lift:   "0 1px 0 rgba(255,255,255,0.025) inset, 0 6px 18px -10px rgba(0,0,0,0.75)",
        lift2:  "0 1px 0 rgba(255,255,255,0.03) inset, 0 14px 34px -14px rgba(0,0,0,0.85)",
        modal:  "0 24px 64px -16px rgba(0,0,0,0.9)",
      },
      letterSpacing: {
        caps: "0.18em",
      },
    },
  },
  plugins: [],
};
export default config;
