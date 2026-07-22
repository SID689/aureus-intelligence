import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        aureus: {
          bg:      "#0a0a0f",
          surface: "#12121a",
          border:  "#1e1e2e",
          gold:    "#d4a843",
          green:   "#22c55e",
          red:     "#ef4444",
          muted:   "#6b7280",
        }
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    }
  },
  plugins: [],
};
export default config;
