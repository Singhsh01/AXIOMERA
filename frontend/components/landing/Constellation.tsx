"use client";
import { useEffect, useRef } from "react";

type Hub = { label: string; x: number; y: number };
type Pt = { x: number; y: number; vx: number; vy: number; hub?: string; r: number };

/**
 * A slowly drifting constellation: anonymous points plus labelled hubs (the systems and agents the
 * platform coordinates). Nearby points join with hairlines; bronze pulses travel along edges like
 * messages between systems; the pointer pulls a few links towards it.
 *
 * Colours come from the theme tokens of the canvas's own context (so scroll scenes and theme
 * switches recolour it), drawing pauses off-screen and in hidden tabs, density scales with area,
 * and prefers-reduced-motion gets a single still frame.
 */
export function Constellation({ hubs = [], density = 1, className, maxLink = 150, pulses = true, fadeLeft = false }: {
  hubs?: Hub[]; density?: number; className?: string; maxLink?: number; pulses?: boolean; fadeLeft?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W = 0, H = 0, dpr = 1, raf = 0, visible = true, frame = 0;
    let pts: Pt[] = [];
    let col = { ink: "24,22,19", accent: "130,86,46", surface: "251,249,244" };
    const mouse = { x: -9999, y: -9999 };
    const flows: { a: number; b: number; t: number; speed: number }[] = [];

    const readColours = () => {
      const cs = getComputedStyle(cv);
      const g = (n: string, f: string) => (cs.getPropertyValue(n).trim().split(/\s+/).join(",") || f);
      col = { ink: g("--ink", col.ink), accent: g("--accent", col.accent), surface: g("--surface", col.surface) };
    };

    const seed = () => {
      const rect = cv.getBoundingClientRect();
      W = rect.width; H = rect.height; dpr = Math.min(1.5, window.devicePixelRatio || 1);
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(110, (W * H) / 13000) * density);
      let s = 11; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
      pts = Array.from({ length: n }, () => ({ x: rnd() * W, y: rnd() * H, vx: (rnd() - 0.5) * 0.22, vy: (rnd() - 0.5) * 0.22, r: 1 + rnd() * 1.2 }));
      for (const h of hubs) pts.push({ x: h.x * W, y: h.y * H, vx: (rnd() - 0.5) * 0.08, vy: (rnd() - 0.5) * 0.08, hub: h.label, r: 3.2 });
    };

    const step = () => {
      frame++;
      if (frame % 23 === 1) readColours();
      ctx.clearRect(0, 0, W, H);
      // drift
      for (const p of pts) {
        p.x += p.vx * 2; p.y += p.vy * 2;
        if (p.x < -20) p.x = W + 20; if (p.x > W + 20) p.x = -20;
        if (p.y < -20) p.y = H + 20; if (p.y > H + 20) p.y = -20;
      }
      // links
      const L2 = maxLink * maxLink;
      const edges: [number, number][] = [];
      ctx.lineWidth = 1;
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i];
        for (let j = i + 1; j < pts.length; j++) {
          const b = pts[j];
          const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
          const lim = a.hub || b.hub ? L2 * 1.9 : L2;
          if (d2 < lim) {
            const k = 1 - d2 / lim;
            ctx.strokeStyle = `rgba(${col.ink},${(a.hub || b.hub ? 0.2 : 0.13) * k})`;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
            if (k > 0.35) edges.push([i, j]);
          }
        }
        const dx = a.x - mouse.x, dy = a.y - mouse.y, d2 = dx * dx + dy * dy;
        if (d2 < 180 * 180) {
          ctx.strokeStyle = `rgba(${col.accent},${0.45 * (1 - d2 / (180 * 180))})`;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
        }
      }
      // pulses: messages travelling between connected points (hub edges preferred)
      if (pulses && frame % 9 === 0 && edges.length && flows.length < 14) {
        const hubEdges = edges.filter(([i, j]) => pts[i].hub || pts[j].hub);
        const pool = hubEdges.length && Math.random() < 0.7 ? hubEdges : edges;
        const [a, b] = pool[Math.floor(Math.random() * pool.length)];
        flows.push({ a, b, t: 0, speed: 0.012 + Math.random() * 0.012 });
      }
      for (let k = flows.length - 1; k >= 0; k--) {
        const f = flows[k]; f.t += f.speed * 2;
        const a = pts[f.a], b = pts[f.b];
        if (f.t >= 1 || !a || !b) { flows.splice(k, 1); continue; }
        const x = a.x + (b.x - a.x) * f.t, y = a.y + (b.y - a.y) * f.t;
        ctx.strokeStyle = `rgba(${col.accent},0.85)`; ctx.lineWidth = 1.4;
        const tx = a.x + (b.x - a.x) * Math.max(0, f.t - 0.12), ty = a.y + (b.y - a.y) * Math.max(0, f.t - 0.12);
        ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke(); ctx.lineWidth = 1;
        ctx.fillStyle = `rgba(${col.accent},1)`; ctx.fillRect(x - 1.8, y - 1.8, 3.6, 3.6);
      }
      // points and hubs
      for (const p of pts) {
        if (p.hub) {
          ctx.fillStyle = `rgba(${col.surface},1)`; ctx.fillRect(p.x - 5, p.y - 5, 10, 10);
          ctx.strokeStyle = `rgba(${col.ink},0.8)`; ctx.strokeRect(p.x - 5, p.y - 5, 10, 10);
          ctx.fillStyle = `rgba(${col.accent},1)`; ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
          ctx.font = "500 10px 'IBM Plex Mono', monospace"; ctx.fillStyle = `rgba(${col.ink},0.7)`;
          ctx.fillText(p.hub.toUpperCase(), p.x + 10, p.y + 3.5);
        } else {
          ctx.fillStyle = `rgba(${col.ink},0.38)`; ctx.fillRect(p.x - p.r / 2, p.y - p.r / 2, p.r, p.r);
        }
      }
    };

    let tick = 0;
    // 30 fps is plenty for slow drift and halves the cost; nothing is drawn while off-screen or hidden.
    const loop = () => { tick++; if (visible && !document.hidden && tick % 2 === 0) step(); raf = requestAnimationFrame(loop); };
    readColours(); seed();
    if (reduce) { step(); } else { raf = requestAnimationFrame(loop); }

    const ro = new ResizeObserver(() => { seed(); if (reduce) step(); });
    ro.observe(cv);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { rootMargin: "100px" });
    io.observe(cv);
    const host = cv.parentElement!;
    const move = (e: PointerEvent) => { const r = cv.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top; };
    const leave = () => { mouse.x = mouse.y = -9999; };
    host.addEventListener("pointermove", move); host.addEventListener("pointerleave", leave);
    const mo = new MutationObserver(() => { readColours(); if (reduce) step(); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-scene"] });
    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); mo.disconnect(); host.removeEventListener("pointermove", move); host.removeEventListener("pointerleave", leave); };
  }, [hubs, density, maxLink, pulses]);

  return (
    <canvas ref={ref} aria-hidden className={className}
      style={fadeLeft ? { maskImage: "linear-gradient(90deg, transparent 0%, rgba(0,0,0,.35) 30%, #000 60%)", WebkitMaskImage: "linear-gradient(90deg, transparent 0%, rgba(0,0,0,.35) 30%, #000 60%)" } : undefined} />
  );
}
