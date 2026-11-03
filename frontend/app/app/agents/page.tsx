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
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {!ov && [0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}
        {ov?.agents.map((a: any) => {
          const fails = (a.by_status.failed ?? 0) + (a.by_status.budget_exceeded ?? 0);
          return (
            <button key={a.agent} onClick={() => setAgent(agent === a.agent ? null : a.agent)}
              className={cn("focus-ring glass p-4 text-left transition-colors", agent === a.agent ? "border-cyan/50 bg-cyan/[0.05]" : "hover:bg-ink/[0.04]")}>
              <div className="flex items-center justify-between"><p className="font-medium">{a.agent}</p>{a.by_status.running ? <Badge t="info" dot>running</Badge> : null}</div>
              <p className="mt-0.5 text-xs text-ink-mute">{ROLE[a.agent] ?? "Agent"}</p>
              <div className="mt-3 flex gap-5 text-sm tabular">
                <span><span className="text-ink-mute">runs</span> {a.runs}</span>
                <span><span className="text-ink-mute">avg</span> {ms(a.avg_latency_ms)}</span>
                <span><span className="text-ink-mute">cost</span> {usd(a.cost_usd)}</span>
                {fails > 0 && <span className="text-bad">{fails} failed</span>}
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-6"><Tabs value={tab} onChange={setTab} items={[{ id: "runs", label: agent ? `Runs: ${agent}` : "Live runs" }, { id: "tools", label: "Tool registry", count: ov?.registry.length }]} /></div>
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
                    <td className="px-4 py-3 font-mono text-[13px] text-cyan">{t.name}</td>
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
