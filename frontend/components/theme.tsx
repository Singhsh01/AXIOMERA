"use client";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/format";

export type Theme = "light" | "dark";
const KEY = "axiomera-theme";

/** Runs in <head> before first paint so the saved theme never flashes. Light is the signature default. */
export const themeInitScript = `(function(){try{var t=localStorage.getItem("${KEY}");document.documentElement.dataset.theme=(t==="dark"||t==="light")?t:"light"}catch(e){document.documentElement.dataset.theme="light"}})()`;

function current(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** The active theme, kept in sync when it changes anywhere (charts and editors re-render on it). */
export function useTheme(): Theme {
  const [t, setT] = useState<Theme>("light");
  useEffect(() => {
    setT(current());
    const mo = new MutationObserver(() => setT(current()));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, []);
  return t;
}

export function setTheme(t: Theme) {
  const root = document.documentElement;
  root.classList.add("theme-fade");
  root.dataset.theme = t;
  try { localStorage.setItem(KEY, t); } catch { /* storage may be unavailable; the switch still applies */ }
  window.setTimeout(() => root.classList.remove("theme-fade"), 320);
}

export function ThemeToggle({ className }: { className?: string }) {
  const t = useTheme();
  const next: Theme = t === "dark" ? "light" : "dark";
  return (
    <button type="button" onClick={() => setTheme(next)} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}
      className={cn("focus-ring inline-flex h-8 w-8 items-center justify-center rounded-control text-ink-soft transition-colors hover:bg-raised hover:text-ink", className)}>
      {t === "dark" ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
    </button>
  );
}

/** Reads a CSS custom property (resolved for the active theme). */
export function cssVar(name: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
/** "R G B" channel tokens -> rgb()/rgba() string usable by canvas/SVG libraries. */
export function tokenColor(name: string, alpha = 1): string {
  const v = cssVar(`--${name}`);
  return alpha === 1 ? `rgb(${v.split(" ").join(",")})` : `rgba(${v.split(" ").join(",")},${alpha})`;
}
