"use client";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { AgentRunCard } from "@/components/AgentRunCard";
import { Badge, Button, PageHeader, Panel, Skeleton, Status, Tabs } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { cn, ms, usd } from "@/lib/format";

const ROLE: Record<string, string> = {
  "triage-agent": "Summarises and extracts; category and priority are rule-based",
  "research-agent": "Customer, orders and policy evidence",
  "resolution-agent": "LangGraph plan → draft → validate loop",
  "communication-agent": "Customer reply, claim-checked",
  "action-executor": "Runs approved actions only (deterministic)",
  "verification-agent": "Reads records back and compares (deterministic)",
  "requirements-agent": "Tender requirements with source offsets",
  "compliance-agent": "Evidence-based compliance status",
  "proposal-agent": "Grounded proposal sections with citations",
};

export default function MissionControl() {
  const { data: ov } = useApi<any>("/agents/overview", { live: 6000 });
  const [agent, setAgent] = useState<string | null>(null);
  const { data: runs, mutate } = useApi<any[]>(`/agents/runs?limit=40${agent ? `&agent=${agent}` : ""}`, { live: 3000 });
  const [tab, setTab] = useState<"runs" | "tools">("runs");
  const reduce = useReducedMotion();

  return (
    <>
      <PageHeader title="Agent mission control" sub="Every agent run with its model, prompt version, tool calls, context sources, budget use and cost. Reasoning is stored as a short summary, never as private chain-of-thought." />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left">
          <thead><tr className="border-b border-ink/80">
            {["Agent", "Role", "Runs", "Avg latency", "Cost", "Failures"].map((h, i) => <th key={h} className={cn("label pb-3 font-normal", i > 1 && "text-right")}>{h}</th>)}
          </tr></thead>
          <tbody>
            {!ov && <tr><td colSpan={6}><Skeleton className="mt-3 h-40" /></td></tr>}
            {ov?.agents.map((a: any) => {
              const fails = (a.by_status.failed ?? 0) + (a.by_status.budget_exceeded ?? 0);
              const on = agent === a.agent;
              return (
                <tr key={a.agent} onClick={() => setAgent(on ? null : a.agent)} aria-selected={on}
                  className={cn("cursor-pointer border-b border-line transition-colors", on ? "bg-raised" : "hover:bg-raised/50")}>
                  <td className="py-3.5 pr-4">
                    <button className="focus-ring flex items-center gap-2 text-[14px] font-semibold" onClick={(e) => { e.stopPropagation(); setAgent(on ? null : a.agent); }}>
                      <span className={cn("h-3 w-[3px]", on ? "bg-accent" : "bg-ink/20")} aria-hidden />{a.agent}
                      {a.by_status.running ? <Badge t="info" dot>running</Badge> : null}
                    </button>
                  </td>
                  <td className="py-3.5 pr-4 text-[13px] text-ink-mute">{ROLE[a.agent] ?? "Agent"}</td>
                  <td className="py-3.5 text-right font-mono text-[13px] tabular">{a.runs}</td>
                  <td className="py-3.5 text-right font-mono text-[13px] tabular">{ms(a.avg_latency_ms)}</td>
                  <td className="py-3.5 text-right font-mono text-[13px] tabular">{usd(a.cost_usd)}</td>
                  <td className={cn("py-3.5 text-right font-mono text-[13px] tabular", fails ? "text-bad" : "text-ink-faint")}>{fails || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-14"><Tabs value={tab} onChange={setTab} items={[{ id: "runs", label: agent ? `Runs: ${agent}` : "Live runs" }, { id: "tools", label: "Tool registry", count: ov?.registry.length }]} /></div>
      {tab === "runs" && (
        <div className="mt-4 space-y-2.5">
          <AnimatePresence initial={false}>
            {runs?.map((r) => (
              <motion.div key={r.id} layout={!reduce} initial={reduce ? false : { opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
                <AgentRunCard run={r} />
                {r.status === "running" && <Button size="sm" variant="danger" className="mt-1" onClick={async () => { await post(`/agents/runs/${r.id}/cancel`); mutate(); }}>Cancel run</Button>}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
      {tab === "tools" && (
        <Panel className="mt-4 overflow-x-auto p-0">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-[13px] text-ink-mute"><tr className="border-b border-line">{["Tool", "What it does", "Permission scope", "Approval", "Calls"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {ov?.registry.map((t: any) => {
                const calls = ov.tools.filter((x: any) => x.tool === t.name);
                return (
                  <tr key={t.name} className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-3 font-mono text-[13px] text-signal">{t.name}</td>
                    <td className="px-4 py-3 text-ink-soft">{t.description}</td>
                    <td className="px-4 py-3"><Badge>{t.scope}</Badge></td>
                    <td className="px-4 py-3">{t.consequential ? <Badge t="warn">required, scope-bound</Badge> : <span className="text-ink-mute">not needed</span>}</td>
                    <td className="px-4 py-3 tabular">{calls.map((c: any) => <span key={c.status} className="mr-2"><Status value={c.status === "ok" ? "succeeded" : c.status === "denied" ? "rejected" : "failed"} /> {c.count}</span>)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  );
}
