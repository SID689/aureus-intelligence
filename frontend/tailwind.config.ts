import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        aureus: {
          ink:        "#0b0d09",
          panel:      "#14160f",
          panellift:  "#191c13",
          rule:       "#2e2c22",
          gold:       "#b8935a",
          goldbright: "#d4ac74",
          verdigris:  "#6fa089",
          oxblood:    "#a14545",
          text:       "#e8e4d8",
          muted:      "#8a8676",
          // legacy aliases kept so existing className references still work
          bg:      "#0b0d09",
          surface: "#14160f",
          border:  "#2e2c22",
          green:   "#6fa089",
          red:     "#a14545",
        },
      },
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
        mono:    ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
