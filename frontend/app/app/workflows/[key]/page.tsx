"use client";
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, use, useMemo, useState } from "react";
import { can, useMe } from "@/components/me";
import { Badge, Button, ErrorNote, PageHeader, Panel, PanelTitle, Skeleton, Status } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { ago, cn, dt, ms } from "@/lib/format";

const Monaco = dynamic(() => import("@monaco-editor/react"), { ssr: false, loading: () => <Skeleton className="h-72" /> });

type NodeData = { label: string; type: string; state?: string; attempts?: number; retry?: any; selected?: boolean; error?: string };

const TYPE_LABEL: Record<string, string> = { webhook: "Webhook", code: "Code", httpRequest: "HTTP → Orkestr API", if: "Branch", respondToWebhook: "Respond", wait: "Wait for human",
  executeWorkflow: "Sub-workflow", executeWorkflowTrigger: "Called by workflow", scheduleTrigger: "Schedule", splitOut: "Split items", errorTrigger: "Error trigger", stopAndError: "Stop" };

function FlowNode({ data }: NodeProps<Node<NodeData>>) {
  const s = data.state;
  return (
    <div className={cn("w-[190px] rounded-xl border bg-midnight/95 px-3 py-2.5 shadow-lift transition-colors",
      s === "failed" ? "border-bad/70" : s === "waiting" ? "border-warn/70" : s === "succeeded" ? "border-violet/70" : "border-line",
      data.selected && "ring-2 ring-cyan/60")}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-ink-faint" />
      <p className="text-[11px] text-ink-mute">{TYPE_LABEL[data.type] ?? data.type}</p>
      <p className="truncate text-[13px] font-medium text-ink">{data.label}</p>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {s && <Status value={s} />}
        {(data.attempts ?? 0) > 1 && <Badge t="cyan">attempt {data.attempts}</Badge>}
        {data.retry?.enabled && !s && <Badge>retry ×{data.retry.maxTries}</Badge>}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-ink-faint" />
    </div>
  );
}
const nodeTypes = { flow: FlowNode };

/** n8n lays workflows out in one long row. Re-layout by depth and wrap into bands so the graph stays readable. */
function layout(nodes: any[], edges: any[]) {
  const incoming: Record<string, number> = {};
  const out: Record<string, string[]> = {};
  for (const e of edges) { incoming[e.target] = (incoming[e.target] ?? 0) + 1; (out[e.source] ||= []).push(e.target); }
  const depth: Record<string, number> = {};
  const queue = nodes.filter((n) => !incoming[n.id]).map((n) => n.id);
  queue.forEach((id) => (depth[id] = 0));
  for (let i = 0; i < queue.length && i < 500; i++) {
    const id = queue[i];
    for (const t of out[id] ?? []) {
      if (depth[t] === undefined || depth[t] < depth[id] + 1) { depth[t] = Math.min(depth[id] + 1, 40); queue.push(t); }
    }
  }
  const COLS = 6, W = 235, H = 105;
  const counts: Record<number, number> = {};
  for (const n of nodes) { const d = depth[n.id] ?? 0; counts[d] = (counts[d] ?? 0) + 1; }
  const band = (Math.max(1, ...Object.values(counts)) + 1) * H;
  const lane: Record<number, number> = {};
  const pos: Record<string, { x: number; y: number }> = {};
  [...nodes].sort((a, b) => a.position.y - b.position.y).forEach((n) => {
    const d = depth[n.id] ?? 0;
    const i = (lane[d] = (lane[d] ?? -1) + 1);
    const row = Math.floor(d / COLS), col = d % COLS;
    pos[n.id] = { x: col * W, y: row * band + i * H };
  });
  return pos;
}

function Studio({ wfKey }: { wfKey: string }) {
  const runParam = useSearchParams().get("run");
  const { data, mutate } = useApi<any>(`/workflows/${wfKey}`, { live: 5000 });
  const [runId, setRunId] = useState<string | null>(runParam);
  const [selNode, setSelNode] = useState<string | null>(null);
  const me = useMe();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const run = data?.runs.find((r: any) => r.id === runId) ?? data?.runs[0];

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    const state: Record<string, any> = {};
    for (const s of run?.steps ?? []) state[s.node] = { state: s.status, attempts: s.attempt, error: s.error };
    const pos = layout(data.nodes, data.edges);
    const ns: Node<NodeData>[] = data.nodes.map((n: any) => ({
      id: n.id, type: "flow", position: pos[n.id],
      data: { label: n.id, type: n.type, retry: n.retry, selected: n.id === selNode, ...state[n.id] },
    }));
    const es: Edge[] = data.edges.map((e: any) => {
      const lit = state[e.source]?.state === "succeeded" && state[e.target];
      return { id: e.id, source: e.source, target: e.target, animated: !!lit, label: data.nodes.find((n: any) => n.id === e.source)?.type === "if" ? (e.branch === 0 ? "true" : "false") : undefined,
        labelStyle: { fill: "#7A83A6", fontSize: 10 }, labelBgStyle: { fill: "#0E1426" },
        style: { stroke: lit ? "#38E1F0" : "rgba(139,148,255,0.3)", strokeWidth: lit ? 2 : 1.3 } };
    });
    return { nodes: ns, edges: es };
  }, [data, run, selNode]);

  if (!data) return <Skeleton className="h-[600px]" />;
  const nodeDef = data.definition.nodes.find((n: any) => n.name === selNode);
  const nodeSteps = (run?.steps ?? []).filter((s: any) => s.node === selNode);

  async function triggerTest() {
    setBusy(true); setErr(null);
    try {
      const payload = wfKey === "B" ? { source: "monitoring", event_id: `ui-${Date.now()}`, title: "Search API latency above 5 s for all users", description: "Production: p95 latency on the search API exceeded 5 seconds; users report timeouts.", service: "search-api", severity: "high" } : {};
      await post(`/workflows/${wfKey}/trigger`, { payload });
      setTimeout(() => mutate(), 2500);
    } catch (e) { setErr(e); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title={`${data.key} · ${data.name}`} sub={<>n8n workflow <span className="font-mono text-sm">{data.id}</span>. Select a node to see its definition and what it did in the selected run.</>}
        actions={(wfKey === "B" || wfKey === "D") && can(me, "workflow.trigger") && <Button variant="primary" loading={busy} onClick={triggerTest}>{wfKey === "B" ? "Send test incident" : "Run deadline scan now"}</Button>} />
      <ErrorNote error={err} />
      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <div className="glass h-[620px] overflow-hidden">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.08 }} minZoom={0.2}
            onNodeClick={(_, n) => setSelNode(n.id)} nodesDraggable={false} nodesConnectable={false} proOptions={{ hideAttribution: true }}>
            <Background color="rgba(139,148,255,0.12)" gap={28} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <Panel className="max-h-[620px] overflow-auto">
          <PanelTitle hint="Most recent first">Executions</PanelTitle>
          <ul className="space-y-1.5">
            {data.runs.map((r: any) => (
              <li key={r.id}>
                <button onClick={() => setRunId(r.id)} className={cn("focus-ring w-full rounded-lg border px-3 py-2 text-left text-sm", run?.id === r.id ? "border-violet/50 bg-violet/10" : "border-line hover:bg-white/[0.04]")}>
                  <div className="flex items-center justify-between gap-2"><span>{r.n8n_execution_id ? `n8n #${r.n8n_execution_id}` : r.trigger}</span><Status value={r.status} /></div>
                  <p className="mt-0.5 text-xs text-ink-mute">{ago(r.started_at)} · {r.step_count} steps · {ms(r.duration_ms)}{r.retries ? ` · ${r.retries} retried` : ""}</p>
                </button>
              </li>
            ))}
            {!data.runs.length && <li className="text-sm text-ink-mute">No executions recorded yet.</li>}
          </ul>
        </Panel>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Panel>
          <PanelTitle hint={selNode ? "As committed in n8n/workflows" : "Select a node in the graph"}>{selNode ?? "Node definition"}</PanelTitle>
          {nodeDef ? <div className="overflow-hidden rounded-lg border border-line"><Monaco height="300px" defaultLanguage="json" theme="vs-dark" value={JSON.stringify(nodeDef, null, 2)}
            options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false, wordWrap: "on" }} /></div> : <p className="text-sm text-ink-mute">Nothing selected.</p>}
        </Panel>
        <Panel>
          <PanelTitle hint={run ? `Run started ${dt(run.started_at)}` : undefined}>Step results</PanelTitle>
          {(selNode ? nodeSteps : run?.steps ?? []).map((s: any) => (
            <div key={s.id} className="mb-2 rounded-lg border border-line p-3 text-sm">
              <div className="flex items-center justify-between"><span className="font-medium">{s.node}{s.attempt > 1 && <span className="text-cyan"> · attempt {s.attempt}</span>}</span><Status value={s.status} /></div>
              {s.error && <p className="mt-1 text-bad">{s.error}</p>}
              {s.detail && Object.keys(s.detail).length > 0 && <p className="mt-1 break-all font-mono text-[11px] text-ink-mute">{JSON.stringify(s.detail)}</p>}
            </div>
          ))}
          {run?.error && <p className="text-sm text-bad">Run error: {run.error}</p>}
          {run?.entity_id && run.entity_type === "case" && <Link href={`/app/cases/${run.entity_id}`} className="text-sm text-cyan hover:underline">Open the case this run handled</Link>}
          {run?.entity_id && run.entity_type === "rfp" && <Link href={`/app/rfps/${run.entity_id}`} className="text-sm text-cyan hover:underline">Open the RFP this run processed</Link>}
        </Panel>
      </div>
    </>
  );
}

export default function Page({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params);
  return <Suspense><Studio wfKey={key} /></Suspense>;
}
