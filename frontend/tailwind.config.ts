import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Light theme. Token names are historical: abyss = page, midnight = panel, deep = raised surface.
        abyss: "#F5F6FB", midnight: "#FFFFFF", deep: "#EEF0F8",
        ink: { DEFAULT: "#141A33", soft: "#3C4466", mute: "#596282", faint: "#737B9A" },
        violet: { DEFAULT: "#6A5AE0", deep: "#4B3BC4" }, electric: "#2F6BEB", cyan: "#0E8FA3",
        ok: "#0F8A5C", warn: "#A86412", bad: "#CF3A57",
        line: "rgba(40,52,110,0.12)",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "ui-sans-serif", "system-ui"],
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { panel: "14px" },
      boxShadow: {
        glow: "0 0 0 1px rgba(106,90,224,0.18), 0 12px 40px -12px rgba(47,107,235,0.22)",
        lift: "0 20px 50px -24px rgba(20,26,51,0.28)",
      },
    },
  },
  plugins: [],
} satisfies Config;
