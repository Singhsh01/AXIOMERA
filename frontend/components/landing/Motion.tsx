"use client";
import { motion, useReducedMotion, useScroll } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/theme";
import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/format";

const EASE = [0.22, 1, 0.36, 1] as const;

/** Fades and lifts content into place the first time it scrolls into view. */
export function Reveal({ children, delay = 0, className, as = "div" }: { children: React.ReactNode; delay?: number; className?: string; as?: "div" | "li" | "section" }) {
  const reduce = useReducedMotion();
  const M = motion[as];
  return (
    <M className={className} initial={reduce ? false : { opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px" }} transition={{ duration: 0.9, delay, ease: EASE }}>
      {children}
    </M>
  );
}

/** Headline whose lines rise from behind a mask, one after another. */
export function RiseLines({ lines, className, delay = 0.15 }: { lines: React.ReactNode[]; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <span className={className}>
      {lines.map((l, i) => (
        <span key={i} className="block overflow-hidden pb-[0.08em]">
          <motion.span className="block" initial={reduce ? false : { y: "105%" }} animate={{ y: 0 }} transition={{ duration: 1.1, delay: delay + i * 0.12, ease: EASE }}>{l}</motion.span>
        </span>
      ))}
    </span>
  );
}

/** Light/dark variants of the same picture, stacked; the active theme or scroll scene fades between them. */
export function ThemedImage({ light, dark, alt, className, imgClassName, priority }: { light: string; dark: string; alt: string; className?: string; imgClassName?: string; priority?: boolean }) {
  return (
    <span className={cn("relative block", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={light} alt={alt} className={cn("tone-light", imgClassName)} loading={priority ? "eager" : "lazy"} decoding="async" />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={dark} alt="" aria-hidden className={cn("tone-dark absolute inset-0 h-full w-full", imgClassName)} loading="lazy" decoding="async" />
    </span>
  );
}

/**
 * Scroll scenes: chapters marked data-tone="alt" switch the whole page to the opposite theme while
 * they hold the middle of the viewport (ivory to night in the light theme, night to ivory in the dark
 * one). Colours cross-fade; the attribute is removed when leaving the page.
 */
export function SceneController() {
  useEffect(() => {
    const root = document.documentElement;
    let timer = 0;
    const set = (alt: boolean) => {
      const next = alt ? "alt" : "";
      if ((root.dataset.scene ?? "") === next) return;
      root.classList.add("scene-shift");
      if (alt) root.dataset.scene = "alt"; else delete root.dataset.scene;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => root.classList.remove("scene-shift"), 820);
    };
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) set((e.target as HTMLElement).dataset.tone === "alt");
    }, { rootMargin: "-50% 0px -50% 0px" });
    document.querySelectorAll<HTMLElement>("[data-tone]").forEach((el) => io.observe(el));
    return () => { io.disconnect(); window.clearTimeout(timer); root.classList.remove("scene-shift"); delete root.dataset.scene; };
  }, []);
  return null;
}

const LINKS = [["Two engines", "#engines"], ["Request lifecycle", "#lifecycle"], ["Governance", "#governance"], ["Demo journey", "#journey"]];

/** Transparent over the hero, a solid sheet with a hairline once the page scrolls. */
export function SiteHeader() {
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    const on = () => setSolid(window.scrollY > 40);
    on(); window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header className={cn("fixed inset-x-0 top-0 z-40 transition-[background-color,border-color,backdrop-filter] duration-500 ease-arch xl:left-14",
      solid ? "border-b border-line bg-page/90 backdrop-blur-md" : "border-b border-transparent")}>
      <div className="mx-auto flex h-[72px] max-w-[1400px] items-center justify-between px-5 sm:px-10">
        <Link href="/" className="focus-ring"><Logo /></Link>
        <nav className="flex items-center gap-1">
          {LINKS.map(([l, h]) => (
            <a key={h} href={h} className="focus-ring group relative hidden whitespace-nowrap px-3 py-2 font-mono text-[11px] uppercase tracking-label text-ink-soft hover:text-ink lg:block">
              {l}<span className="absolute inset-x-3 bottom-1 h-px origin-left scale-x-0 bg-ink transition-transform duration-300 ease-arch group-hover:scale-x-100" />
            </a>
          ))}
          <ThemeToggle className="ml-2" />
          <Link href="/login" className="focus-ring ml-2 inline-flex h-10 items-center whitespace-nowrap bg-primary px-5 font-mono text-[11px] uppercase tracking-label text-primary-fg transition-colors hover:bg-primary/85">Sign in</Link>
        </nav>
      </div>
    </header>
  );
}

/** Framing rail on wide screens: rotated product line and a scroll-progress hairline. */
export function Rail() {
  const { scrollYProgress } = useScroll();
  return (
    <aside className="fixed inset-y-0 left-0 z-50 hidden w-14 flex-col items-center justify-between border-r border-line bg-page py-6 xl:flex" aria-hidden>
      <span className="h-2 w-2 bg-accent" />
      <span className="rotate-180 font-mono text-[10px] uppercase tracking-[0.3em] text-ink-mute [writing-mode:vertical-rl]">{BRAND.name} — Governed automation</span>
      <span className="relative h-28 w-px bg-line">
        <motion.span className="absolute inset-x-0 top-0 block h-full origin-top bg-ink" style={{ scaleY: scrollYProgress }} />
      </span>
    </aside>
  );
}
