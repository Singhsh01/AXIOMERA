import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        abyss: "#070A14", midnight: "#0E1426", deep: "#131B33",
        ink: { DEFAULT: "#EEF1FF", soft: "#B8BFDB", mute: "#7A83A6", faint: "#4B5376" },
        violet: { DEFAULT: "#8B7CFF", deep: "#5B4BD6" }, electric: "#3D7BFF", cyan: "#38E1F0",
        ok: "#34D399", warn: "#FBBF24", bad: "#FB7185",
        line: "rgba(139,148,255,0.16)",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "ui-sans-serif", "system-ui"],
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { panel: "14px" },
      boxShadow: {
        glow: "0 0 0 1px rgba(139,148,255,0.18), 0 12px 40px -12px rgba(61,123,255,0.25)",
        lift: "0 24px 60px -24px rgba(0,0,0,0.7)",
      },
    },
  },
  plugins: [],
} satisfies Config;
