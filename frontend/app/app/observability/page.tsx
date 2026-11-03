"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Chart } from "@/components/Chart";
import { can, useMe } from "@/components/me";
import { Badge, Button, Empty, ErrorNote, JsonBlock, PageHeader, Panel, PanelTitle, Skeleton, Stat, Status, Tabs } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { ago, dt, ms, pct, usd } from "@/lib/format";

function Analytics() {
  const { data: a } = useApi<any>("/analytics/overview?days=30", { live: 20000 });
  if (!a) return <Skeleton className="h-96" />;
  const wf = Object.entries(a.workflow_runs_by_key as Record<string, number>);
  const agents = Object.entries(a.agent_runs_by_agent as Record<string, number>).sort((x, y) => y[1] - x[1]);
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Workflow success rate" value={pct(a.workflow_success_rate)} sub={`p50 ${a.workflow_latency_p50_s ?? "—"} s, p95 ${a.workflow_latency_p95_s ?? "—"} s`} />
        <Stat label="Average case resolution" value={a.case_resolution_minutes_avg !== null ? `${a.case_resolution_minutes_avg} min` : "—"} sub={`${a.cases_resolved} of ${a.cases_created} resolved`} />
        <Stat label="Approval turnaround" value={a.approval_turnaround_minutes_avg !== null ? `${a.approval_turnaround_minutes_avg} min` : "—"} sub="request to decision" />
        <Stat label="Tool failure rate" value={pct(a.tool_failure_rate)} sub={`${a.tool_calls} tool calls`} tone={a.tool_failure_rate > 10 ? "warn" : undefined} />
        <Stat label="SLA compliance" value={pct(a.sla_compliance)} />
        <Stat label="RFP upload to draft" value={a.rfp_processing_seconds_avg !== null ? `${a.rfp_processing_seconds_avg} s` : "—"} sub="average" />
        <Stat label="Evidence coverage" value={pct(a.evidence_coverage)} sub={`of ${a.requirements_total} requirements`} />
        <Stat label="Estimated AI cost" value={usd(a.estimated_ai_cost_usd)} sub="30 days" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Panel><PanelTitle hint="Executions reported by each n8n workflow">Workflow runs</PanelTitle>
          <Chart kind="bar" label="Workflow runs by workflow" categories={wf.map(([k]) => k)} series={[{ name: "Runs", data: wf.map(([, v]) => v) }]} /></Panel>
        <Panel><PanelTitle hint="Runs per agent">Agent runs</PanelTitle>
          <Chart kind="bar" horizontal label="Agent runs" categories={agents.map(([k]) => k).reverse()} series={[{ name: "Runs", data: agents.map(([, v]) => v).reverse() }]} height={260} /></Panel>
        <Panel><PanelTitle hint="Tokens and estimated cost by provider. Fixture and deterministic runs make no model calls.">Model usage</PanelTitle>
          <table className="w-full text-sm"><thead className="text-left text-ink-mute"><tr><th className="py-2 font-medium">Provider</th><th className="font-medium">Runs</th><th className="font-medium">Tokens</th><th className="font-medium">Cost</th></tr></thead>
            <tbody>{Object.entries(a.model_usage as Record<string, any>).map(([p, v]) => <tr key={p} className="border-t border-line"><td className="py-2"><Status value={p} /></td><td className="tabular">{v.runs}</td><td className="tabular">{v.tokens}</td><td className="tabular">{usd(v.cost_usd)}</td></tr>)}</tbody></table></Panel>
        <Panel><PanelTitle hint="Most recent run of each suite">Evaluations</PanelTitle>
          {a.evaluations.length ? a.evaluations.map((e: any) => (
            <div key={e.suite} className="mb-3 rounded-lg border border-line p-3">
              <div className="flex items-center justify-between"><p className="font-medium">{e.suite}</p><span className="text-xs text-ink-mute">{ago(e.at)} {e.uses_fixtures && "· fixtures"}</span></div>
              <p className="mt-1 font-mono text-[12px] text-ink-soft">{Object.entries(e.metrics).filter(([, v]) => typeof v === "number").map(([k, v]) => `${k} ${v}`).join("  ")}</p>
            </div>
          )) : <Empty title="No evaluation runs recorded" body="Run make eval to populate this." />}
        </Panel>
      </div>
    </>
  );
}

function Timeline() {
  const { data } = useApi<any[]>("/workflows/runs?limit=40", { live: 5000 });
  if (!data) return <Skeleton className="h-96" />;
  const t0 = Math.min(...data.map((r) => new Date(r.started_at).getTime()));
  const t1 = Math.max(...data.map((r) => new Date(r.started_at).getTime() + r.duration_ms), t0 + 1);
  return (
    <Panel>
      <PanelTitle hint="Each bar is one execution from start to its last reported step, positioned on a shared time axis">Execution timeline</PanelTitle>
      <div className="space-y-1.5">
        {data.map((r) => {
          const left = ((new Date(r.started_at).getTime() - t0) / (t1 - t0)) * 100;
          const width = Math.max(0.6, (Math.min(r.duration_ms, t1 - t0) / (t1 - t0)) * 100);
          return (
            <div key={r.id} className="grid grid-cols-[9rem_1fr] items-center gap-3 text-xs">
              <span className="truncate text-ink-mute">{r.workflow_key} {r.n8n_execution_id ? `#${r.n8n_execution_id}` : r.trigger}</span>
              <div className="relative h-5 rounded bg-ink/[0.03]">
                <span title={`${r.status}, ${ms(r.duration_ms)}`} className={`absolute top-0.5 h-4 rounded ${r.status === "failed" ? "bg-bad/80" : r.status === "waiting" ? "bg-warn/70" : r.status === "running" ? "bg-electric/70" : "bg-violet/80"}`} style={{ left: `${left}%`, width: `${width}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-ink-faint">{dt(new Date(t0).toISOString())} to {dt(new Date(t1).toISOString())}</p>
    </Panel>
  );
}

function DeadLetters() {
  const { data, mutate } = useApi<any[]>("/dead-letters", { live: 5000 });
  const me = useMe();
  const [err, setErr] = useState<unknown>(null);
  return (
    <Panel>
      <PanelTitle hint="Executions that failed after all retries, reported by n8n's error workflow">Incident explorer</PanelTitle>
      <ErrorNote error={err} />
      {data?.length === 0 && <Empty title="No dead letters" body="Failed executions land here with the node, error and payload needed to replay them." />}
      <div className="space-y-3">
        {data?.map((d) => (
          <div key={d.id} className="rounded-lg border border-line p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium">{d.source} {d.workflow_key && <Badge t="cyan">workflow {d.workflow_key}</Badge>}</p>
              <span className="flex items-center gap-2 text-xs text-ink-mute">{ago(d.created_at)} {d.n8n_execution_id && `· n8n #${d.n8n_execution_id}`}<Status value={d.status === "open" ? "failed" : "succeeded"} /></span>
            </div>
            <p className="mt-2 text-sm text-bad">{d.error}</p>
            <JsonBlock value={d.payload} className="mt-2 max-h-32" />
            {d.status === "open" && can(me, "deadletter.manage") && (d.payload.approval_id || d.payload.case_id) && (
              <Button size="sm" className="mt-3" onClick={async () => { setErr(null); try { await post(`/dead-letters/${d.id}/replay`); mutate(); } catch (e) { setErr(e); } }}>Replay</Button>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Audit() {
  const { data } = useApi<any[]>("/audit?limit=150", { live: 8000 });
  const { data: v, mutate } = useApi<any>("/audit/verify");
  return (
    <Panel>
      <PanelTitle hint="Append-only, SHA-256 chained per workspace" action={<Button size="sm" onClick={() => mutate()}>Verify chain</Button>}>Audit log</PanelTitle>
      {v && <p className={`mb-4 rounded-lg border px-3 py-2 text-sm ${v.valid ? "border-ok/30 bg-ok/10 text-ok" : "border-bad/30 bg-bad/10 text-bad"}`}>
        {v.valid ? `Chain intact across ${v.events} events. Head ${v.head.slice(0, 16)}…` : `Chain broken at sequence ${v.broken_at_seq}: a record was altered or removed.`}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-left text-[12px] text-ink-mute"><tr>{["Seq", "Action", "Actor", "Entity", "When", "Hash"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>{data?.map((e) => (
            <tr key={e.id} className="border-t border-line/60">
              <td className="py-2 pr-3 tabular text-ink-mute">{e.seq}</td><td className="pr-3 font-medium">{e.action}</td>
              <td className="pr-3 text-ink-soft">{e.actor_type}:{e.actor_id.slice(0, 14)}</td><td className="pr-3 text-ink-mute">{e.entity_type}</td>
              <td className="pr-3 text-ink-mute">{dt(e.created_at)}</td><td className="font-mono text-[11px] text-ink-faint">{e.hash.slice(0, 12)}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </Panel>
  );
}

function Obs() {
  const t = useSearchParams().get("tab");
  const [tab, setTab] = useState<string>(t ?? "analytics");
  return (
    <>
      <PageHeader title="Observability" sub="Metrics computed from stored events, the execution timeline, failed executions and the tamper-evident audit log. Prometheus metrics are exposed at /metrics and traces via OpenTelemetry." />
      <Tabs value={tab} onChange={setTab} items={[{ id: "analytics", label: "Analytics" }, { id: "timeline", label: "Execution timeline" }, { id: "dead-letters", label: "Incident explorer" }, { id: "audit", label: "Audit log" }]} />
      <div className="mt-5">{tab === "analytics" ? <Analytics /> : tab === "timeline" ? <Timeline /> : tab === "dead-letters" ? <DeadLetters /> : <Audit />}</div>
    </>
  );
}

export default function Page() {
  return <Suspense><Obs /></Suspense>;
}
