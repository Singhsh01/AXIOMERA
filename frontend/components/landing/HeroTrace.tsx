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
            <linearGradient id="edge" x1="0" x2="1"><stop offset="0" stopColor="#8B7CFF" /><stop offset="1" stopColor="#38E1F0" /></linearGradient>
            <filter id="glow"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>
          {NODES.slice(1).map((n, i) => {
            const p = NODES[i];
            const d = `M${p.x + 22} ${p.y} C ${p.x + 80} ${p.y}, ${n.x - 58} ${n.y}, ${n.x - 22} ${n.y}`;
            const lit = i < activeIdx;
            return (
              <g key={n.id}>
                <path d={d} stroke="rgba(139,148,255,0.18)" strokeWidth="1.5" fill="none" />
                {lit && <path d={d} stroke="url(#edge)" strokeWidth="2" fill="none" opacity="0.8" />}
                {i === activeIdx - 1 && <path d={d} stroke="#38E1F0" strokeWidth="3" fill="none" className="signal" filter="url(#glow)" />}
              </g>
            );
          })}
          {NODES.map((n, i) => {
            const done = i < activeIdx, active = i === activeIdx;
            const ring = n.human ? "#FBBF24" : active ? "#38E1F0" : done ? "#8B7CFF" : "rgba(139,148,255,0.3)";
            return (
              <g key={n.id} transform={`translate(${n.x} ${n.y})`}>
                {active && <circle r="30" fill={n.human ? "rgba(251,191,36,0.12)" : "rgba(56,225,240,0.12)"} className="live-dot" />}
                <rect x="-22" y="-22" width="44" height="44" rx={n.kind === "trigger" ? 22 : 11} fill="#0E1426" stroke={ring} strokeWidth={active ? 2 : 1.4} />
                {n.human ? <path d="M-6 -2a6 6 0 1 1 12 0v3h-12z M-9 1h18v9h-18z" fill={active ? "#FBBF24" : "#7A83A6"} transform="scale(.8)" />
                  : n.agent ? <circle r="6" fill={done || active ? "url(#edge)" : "#4B5376"} />
                  : <rect x="-6" y="-6" width="12" height="12" rx="3" fill={done || active ? "#8B7CFF" : "#4B5376"} />}
                <text y={n.y < 120 ? -34 : 42} textAnchor="middle" fill={active ? "#EEF1FF" : "#7A83A6"} fontSize="13" fontFamily="IBM Plex Sans">{n.id}</text>
                {n.agent && <text y={n.y < 120 ? -50 : 58} textAnchor="middle" fill="#4B5376" fontSize="11" fontFamily="IBM Plex Sans">{n.agent} agent</text>}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-[auto_1fr] sm:items-center">
        <span className="inline-flex items-center gap-2 text-sm text-ink-mute">
          <span className={`h-2 w-2 rounded-full ${activeId === "Approval" ? "bg-warn" : "bg-cyan"} live-dot`} />
          n8n execution 2
        </span>
        <motion.p key={step} initial={reduce ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
          className="font-mono text-[13px] text-ink-soft" aria-live="polite">
          <span className="text-violet">{activeId}</span>&nbsp;&nbsp;{LOG[Math.min(step, LOG.length - 1)][1]}
        </motion.p>
      </div>
    </div>
  );
}
