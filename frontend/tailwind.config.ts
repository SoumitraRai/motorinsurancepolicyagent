import type { Config } from "tailwindcss";

// Security-paper schedule: navy ink on white, a teal guilloché band, security-pink quotes, red serials.
export default {
  content: ["./index.html", "./preview.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1C2440", soft: "#3A4262", muted: "#545C78" },
        rule: { DEFAULT: "#D9DEE8", strong: "#B8C0D2" },
        sheet: { DEFAULT: "#FFFFFF", wash: "#F6F8FB" },
        guard: { DEFAULT: "#2E7D6F", deep: "#1F5E53", tint: "#E2F0EA" },
        quote: "#F5E1E7",
        serial: "#C62828",
        warn: { DEFAULT: "#7A4F00", tint: "#FFF1D0" },
        refuse: { DEFAULT: "#A3201C", tint: "#FBE8E8" },
      },
      fontFamily: {
        sans: ["Hind", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      fontSize: { rate: ["2.75rem", { lineHeight: "1.1", letterSpacing: "-0.02em" }] },
    },
  },
  plugins: [],
} satisfies Config;
