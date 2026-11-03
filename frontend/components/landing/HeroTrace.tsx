"use client";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

/** The real node chain of n8n Workflow A, drawn as an execution trace. */
const NODES = [
  { id: "Intake Webhook", x: 40, y: 150, kind: "trigger" },
  { id: "Verify Signature", x: 190, y: 90 },
  { id: "Create Case", x: 340, y: 150 },
  { id: "Classify", x: 490, y: 90, agent: "triage" },
  { id: "Retrieve Evidence", x: 640, y: 150, agent: "research" },
  { id: "Propose Resolution", x: 790, y: 90, agent: "resolution" },
  { id: "Approval", x: 940, y: 150, human: true },
  { id: "Execute", x: 1090, y: 90 },
  { id: "Verify", x: 1240, y: 150, agent: "verification" },
];

const LOG = [
  ["Intake Webhook", "Signed email from anna.weber@example.com accepted"],
  ["Create Case", "Case #1001 created · Message-ID used as idempotency key"],
  ["Classify", "billing_refund, priority P3, SLA due in 18h"],
  ["Retrieve Evidence", "Order ORD-10421 found; refund policy §Eligibility cited"],
  ["Propose Resolution", "Refund €149.00 proposed, inside the 30-day window"],
  ["Approval", "Waiting for Priya (approver) — policy refund-standard"],
  ["Execute", "Refund executed on the payments ledger (simulator)"],
  ["Verify", "Record read back: amount and order match. Case resolved"],
];

export function HeroTrace() {
  const reduce = useReducedMotion();
  const [step, setStep] = useState(reduce ? LOG.length - 1 : 0);
  useEffect(() => {
    if (reduce) return;
    const t = setInterval(() => setStep((s) => (s + 1) % (LOG.length + 2)), 1500);
    return () => clearInterval(t);
  }, [reduce]);
  const activeId = LOG[Math.min(step, LOG.length - 1)][0];
  const activeIdx = NODES.findIndex((n) => n.id === activeId);

  return (
    <div className="relative">
      <div className="overflow-x-auto pb-2 [scrollbar-width:none]">
        <svg viewBox="-30 0 1330 230" className="min-w-[860px] w-full" role="img" aria-label="Workflow A execution trace from intake to verification">
          <defs>
            <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V6" style={{ stroke: "rgb(var(--ink) / 0.18)" }} strokeWidth="1" /></pattern>
          </defs>
          {NODES.slice(1).map((n, i) => {
            const p = NODES[i];
            const d = `M${p.x + 22} ${p.y} C ${p.x + 80} ${p.y}, ${n.x - 58} ${n.y}, ${n.x - 22} ${n.y}`;
            const lit = i < activeIdx;
            return (
              <g key={n.id}>
                <path d={d} style={{ stroke: "rgb(var(--ink) / 0.16)" }} strokeWidth="1" strokeDasharray="3 4" fill="none" />
                {lit && <path d={d} style={{ stroke: "rgb(var(--ink) / 0.75)" }} strokeWidth="1.4" fill="none" />}
                {i === activeIdx - 1 && <path d={d} style={{ stroke: "rgb(var(--accent))" }} strokeWidth="2.5" fill="none" className="signal" />}
              </g>
            );
          })}
          {NODES.map((n, i) => {
            const done = i < activeIdx, active = i === activeIdx;
            const ring = n.human ? "rgb(var(--accent))" : active ? "rgb(var(--ink))" : done ? "rgb(var(--ink) / 0.6)" : "rgb(var(--ink) / 0.22)";
            return (
              <g key={n.id} transform={`translate(${n.x} ${n.y})`}>
                {active && <rect x="-30" y="-30" width="60" height="60" style={{ fill: n.human ? "rgb(var(--accent) / 0.14)" : "rgb(var(--ink) / 0.07)" }} className="live-dot" />}
                <rect x="-20" y="-20" width="40" height="40" rx={n.kind === "trigger" ? 20 : 0} style={{ fill: "rgb(var(--surface))", stroke: ring }} strokeWidth={active ? 2 : 1.2} />
                {n.human ? <path d="M-6 -2a6 6 0 1 1 12 0v3h-12z M-9 1h18v9h-18z" style={{ fill: active ? "rgb(var(--accent))" : "rgb(var(--ink-mute))" }} transform="scale(.8)" />
                  : n.agent ? <rect x="-7" y="-7" width="14" height="14" style={{ fill: done || active ? "url(#hatch)" : "transparent", stroke: done || active ? "rgb(var(--ink))" : "rgb(var(--ink) / 0.3)" }} strokeWidth="1" transform="rotate(45)" />
                  : <rect x="-6" y="-6" width="12" height="12" style={{ fill: done || active ? "rgb(var(--ink))" : "rgb(var(--ink) / 0.25)" }} />}
                <text y={n.y < 120 ? -34 : 42} textAnchor="middle" style={{ fill: active ? "rgb(var(--ink))" : "rgb(var(--ink-mute))" }} fontSize="13" fontWeight={active ? 700 : 500} fontFamily="Manrope Variable">{n.id}</text>
                {n.agent && <text y={n.y < 120 ? -50 : 58} textAnchor="middle" style={{ fill: "rgb(var(--ink-faint))" }} fontSize="10" letterSpacing="1.2" fontFamily="IBM Plex Mono">{n.agent.toUpperCase()} AGENT</text>}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center">
        <span className="label inline-flex items-center gap-2">
          <span className={`h-1.5 w-1.5 rounded-full ${activeId === "Approval" ? "bg-accent" : "bg-ink"} live-dot`} />
          n8n execution · workflow A
        </span>
        <motion.p key={step} initial={reduce ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
          className="border-l border-line pl-4 font-mono text-[12.5px] text-ink-soft" aria-live="polite">
          <span className="font-medium text-accent">{activeId}</span>&nbsp;&nbsp;{LOG[Math.min(step, LOG.length - 1)][1]}
        </motion.p>
      </div>
    </div>
  );
}
