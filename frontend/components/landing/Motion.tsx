"use client";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
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

/** Light/dark variants of the same picture; CSS picks one, so there is no flash or layout shift. */
export function ThemedImage({ light, dark, alt, className, imgClassName, priority }: { light: string; dark: string; alt: string; className?: string; imgClassName?: string; priority?: boolean }) {
  return (
    <span className={cn("block", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={light} alt={alt} className={cn("dark:hidden", imgClassName)} loading={priority ? "eager" : "lazy"} decoding="async" />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={dark} alt={alt} className={cn("hidden dark:block", imgClassName)} loading="lazy" decoding="async" />
    </span>
  );
}

/** Hero picture drifting slower than the page (subtle parallax; off for reduced motion). */
export function ParallaxImage({ light, dark, alt }: { light: string; dark: string; alt: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], ["0%", reduce ? "0%" : "18%"]);
  const scale = useTransform(scrollYProgress, [0, 1], [1.04, reduce ? 1.04 : 1.12]);
  return (
    <div ref={ref} className="absolute inset-0 overflow-hidden">
      <motion.div style={{ y, scale }} className="absolute inset-0">
        <ThemedImage light={light} dark={dark} alt={alt} priority className="h-full w-full" imgClassName="h-full w-full object-cover object-[70%_center]" />
      </motion.div>
    </div>
  );
}

const LINKS = [["Platform", "#platform"], ["Request lifecycle", "#lifecycle"], ["Governance", "#governance"], ["Evidence", "#evidence"]];

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
