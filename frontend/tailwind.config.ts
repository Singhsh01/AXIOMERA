import type { Config } from "tailwindcss";

/**
 * Every colour is a semantic token backed by a CSS variable (channels only, so Tailwind's /<alpha>
 * modifiers work). Values live in app/globals.css: one set for the light "travertine" theme and one
 * for the dark theme. Components never hard-code theme colours.
 */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        page: v("page"),          // the canvas behind everything
        surface: v("surface"),    // panels, tables, dialogs
        raised: v("raised"),      // stone: hover, selected rows, insets
        ink: { DEFAULT: v("ink"), soft: v("ink-soft"), mute: v("ink-mute"), faint: v("ink-faint") },
        accent: { DEFAULT: v("accent"), deep: v("accent-deep") }, // bronze (light) / violet (dark)
        signal: v("signal"),      // live / active state
        info: v("info"),
        ok: v("ok"), warn: v("warn"), bad: v("bad"),
        primary: { DEFAULT: v("primary"), fg: v("on-primary") }, // primary button
        inverse: { DEFAULT: v("inverse"), fg: v("on-inverse") },  // emphasis band
        line: "rgb(var(--line) / calc(var(--line-a) * <alpha-value>))",
      },
      fontFamily: {
        display: ['"Manrope Variable"', "ui-sans-serif", "system-ui"],
        sans: ['"Manrope Variable"', "ui-sans-serif", "system-ui"],
        serif: ['"Instrument Serif"', "ui-serif", "Georgia", "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { panel: "var(--radius-panel)", control: "var(--radius-control)" },
      boxShadow: {
        lift: "var(--shadow-lift)",
        plate: "var(--shadow-plate)",
      },
      letterSpacing: { label: "0.16em", wordmark: "0.24em" },
      transitionTimingFunction: { arch: "cubic-bezier(0.22, 1, 0.36, 1)" },
    },
  },
  plugins: [],
} satisfies Config;
