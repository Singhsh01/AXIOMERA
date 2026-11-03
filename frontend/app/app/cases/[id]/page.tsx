"use client";
import { AlertTriangle, ExternalLink } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { AgentRunCard } from "@/components/AgentRunCard";
import { can, useMe } from "@/components/me";
import { ApprovalActions } from "@/components/ApprovalActions";
import { Badge, Button, JsonBlock, Panel, PanelTitle, Priority, Skeleton, Status, Tabs } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { ago, dt, human, ms, until } from "@/lib/format";

export default function CaseDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: c, mutate } = useApi<any>(`/cases/${id}`, { live: 4000 });
  const { data: auditLog } = useApi<any[]>(`/audit?correlation_id=${c?.correlation_id ?? ""}&limit=200`, { live: 8000 });
  const [tab, setTab] = useState<"overview" | "actions" | "timeline" | "agents" | "audit">("overview");
  const me = useMe();
  if (!c) return <Skeleton className="h-96" />;

  const timeline = [
    ...c.events.map((e: any) => ({ at: e.created_at, kind: "case", title: e.type === "status_changed" ? `${human(e.from_status)} → ${human(e.to_status)}` : human(e.type), detail: e.data?.reason, actor: e.actor })),
    ...c.workflow_runs.flatMap((w: any) => w.steps.map((s: any) => ({ at: s.started_at, kind: "n8n", title: `${w.workflow_key} · ${s.node}`, detail: s.error || (s.attempt > 1 ? `attempt ${s.attempt}` : ""), actor: w.n8n_execution_id ? `n8n #${w.n8n_execution_id}` : w.trigger, status: s.status }))),
  ].sort((a, b) => a.at.localeCompare(b.at));

  return (
    <>
      <div className="mb-6">
        <Link href="/app/cases" className="text-sm text-ink-mute hover:text-ink">Cases</Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="h-display text-[32px] font-semibold sm:text-[38px]"><span className="text-ink-faint">#{c.number}</span> {c.title}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Status value={c.status} /><Priority p={c.priority} /><Badge>{human(c.category)}</Badge>
              {c.kind === "incident" && <Badge t="bad">incident</Badge>}
              {c.owner_team && <Badge t="violet">team {c.owner_team}</Badge>}
              {c.external_refs?.jira && <Badge t="cyan">{c.external_refs.jira}</Badge>}
              <span className={`text-sm ${c.sla_breached ? "text-bad" : "text-ink-mute"}`}>SLA {["resolved", "closed"].includes(c.status) ? "met" : until(c.sla_due_at)}</span>
            </div>
          </div>
          {c.status === "needs_review" && can(me, "case.write") && (
            <Button variant="secondary" onClick={async () => { await post(`/cases/${id}/release-review`); mutate(); }}>Release for automation</Button>
          )}
        </div>
      </div>

      {c.security_flags?.length > 0 && (
        <div role="alert" className="mb-5 flex gap-3 rounded-panel border border-warn/30 bg-warn/10 p-4 text-sm">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warn" />
          <div><p className="font-medium text-warn">Automation paused: the message tries to instruct the system</p>
            <ul className="mt-1 space-y-0.5 text-ink-soft">{c.security_flags.map((f: any, i: number) => <li key={i}>{human(f.pattern)}: “{f.excerpt}”</li>)}</ul></div>
        </div>
      )}

      <Tabs value={tab} onChange={setTab} items={[
        { id: "overview", label: "Overview" }, { id: "actions", label: "Actions & approvals", count: c.actions.length },
        { id: "timeline", label: "Timeline", count: timeline.length }, { id: "agents", label: "Agent runs", count: c.agent_runs.length }, { id: "audit", label: "Audit" },
      ]} />

      <div className="mt-5">
        {tab === "overview" && (
          <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
            <div className="space-y-5">
              <Panel>
                <PanelTitle hint={`${c.source} from ${c.triage?.sender ?? "unknown"} · ${dt(c.created_at)}`}>Request</PanelTitle>
                <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink-soft">{c.description}</p>
              </Panel>
              {c.resolution?.rationale && (
                <Panel>
                  <PanelTitle hint="From the resolution agent's LangGraph run">Proposed resolution</PanelTitle>
                  <p className="text-[15px] leading-relaxed">{c.resolution.rationale}</p>
                  {c.resolution.missing_information?.length > 0 && <p className="mt-2 text-sm text-warn">Missing: {c.resolution.missing_information.map(human).join(", ")}</p>}
                </Panel>
              )}
              {c.draft_reply && (
                <Panel>
                  <PanelTitle hint="Sent only after approval of the customer email action">Draft reply</PanelTitle>
                  <p className="whitespace-pre-wrap rounded-lg border border-line bg-abyss/50 p-4 text-sm leading-relaxed text-ink-soft">{c.draft_reply}</p>
                </Panel>
              )}
            </div>
            <div className="space-y-5">
              <Panel>
                <PanelTitle>Triage</PanelTitle>
                <dl className="grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
                  <dt className="text-ink-mute">Summary</dt><dd>{c.triage?.summary ?? "—"}</dd>
                  <dt className="text-ink-mute">Confidence</dt><dd className="tabular">{c.triage?.confidence ?? "—"}</dd>
                  <dt className="text-ink-mute">Why this priority</dt><dd>{c.triage?.priority_reason ?? "—"}</dd>
                  <dt className="text-ink-mute">Customer</dt><dd>{c.customer ? `${c.customer.name}, ${c.customer.tier}` : "No match"}</dd>
                  <dt className="text-ink-mute">Orders mentioned</dt><dd>{c.triage?.entities?.order_ids?.join(", ") || "—"}</dd>
                </dl>
              </Panel>
              <Panel>
                <PanelTitle hint="Approved policy passages retrieved by hybrid search">Evidence</PanelTitle>
                <ul className="space-y-3">
                  {(c.research?.policy_evidence ?? []).map((e: any) => (
                    <li key={e.chunk_id} className="rounded-lg border border-line p-3">
                      <p className="text-sm font-medium">{e.document}{e.heading && <span className="text-ink-mute"> / {e.heading}</span>}</p>
                      <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink-mute">{e.excerpt}</p>
                    </li>
                  ))}
                  {(c.research?.orders ?? []).map((o: any) => <li key={o.id} className="text-sm text-ink-soft">Order {o.id}: €{o.amount.toFixed(2)}, {o.product}, {o.status}{o.inferred && " (inferred as most recent)"}</li>)}
                  {!c.research?.policy_evidence && <li className="text-sm text-ink-mute">Research has not run for this case.</li>}
                </ul>
              </Panel>
            </div>
          </div>
        )}

        {tab === "actions" && (
          <div className="space-y-3">
            {c.actions.map((a: any) => (
              <Panel key={a.id} className="grid gap-4 lg:grid-cols-[1fr_1fr]">
                <div>
                  <div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-lg font-semibold">{human(a.action_type)}</h3><Status value={a.status} />
                    {a.result?.mode && <Badge t={a.result.mode === "live" ? "ok" : "cyan"}>{a.result.mode}{a.result.external_id ? ` ${a.result.external_id}` : ""}</Badge>}</div>
                  <JsonBlock value={a.params} className="mt-3 max-h-48" />
                </div>
                <div className="space-y-3 text-sm">
                  {a.approval ? (
                    <div className="rounded-lg border border-line p-3">
                      <p>Policy <span className="font-medium">{a.approval.policy_rule}</span>, risk {a.approval.risk_level}, needs {a.approval.required_role}</p>
                      <p className="mt-1 text-ink-mute">{a.approval.decided_at ? `${human(a.approval.status)} ${ago(a.approval.decided_at)}${a.approval.decision_note ? `: “${a.approval.decision_note}”` : ""}` : `Requested ${ago(a.approval.created_at)}, expires ${until(a.approval.expires_at)}`}</p>
                      <p className="mt-1 font-mono text-[11px] text-ink-faint">scope {a.approval.scope_hash.slice(0, 16)}…</p>
                      {a.approval.status === "pending" && <div className="mt-3"><ApprovalActions approval={a.approval} onDone={mutate} /></div>}
                    </div>
                  ) : <p className="text-ink-mute">No approval required by policy (internal, low risk).</p>}
                  {a.verification && (
                    <div className="rounded-lg border border-line p-3">
                      <p className="font-medium">{a.verification.verified ? "Verified by read-back" : "Verification failed"}</p>
                      <ul className="mt-1 space-y-0.5 text-ink-mute">{a.verification.checks.map((ch: any) => <li key={ch.check}>{ch.passed ? "✓" : "✗"} {ch.check}</li>)}</ul>
                    </div>
                  )}
                </div>
              </Panel>
            ))}
            {!c.actions.length && <p className="text-ink-mute">No actions proposed yet.</p>}
          </div>
        )}

        {tab === "timeline" && (
          <Panel>
            <ol className="relative space-y-4 border-l border-line pl-6">
              {timeline.map((t, i) => (
                <li key={i} className="relative">
                  <span className={`absolute -left-[29px] top-1.5 h-2.5 w-2.5 rounded-full ${t.status === "failed" ? "bg-bad" : t.kind === "n8n" ? "bg-cyan" : "bg-violet"}`} />
                  <div className="flex flex-wrap items-baseline gap-x-3"><p className="text-sm font-medium">{t.title}</p><p className="text-xs text-ink-faint">{dt(t.at)} · {t.actor}</p></div>
                  {t.detail && <p className={`text-sm ${t.status === "failed" ? "text-bad" : "text-ink-mute"}`}>{t.detail}</p>}
                </li>
              ))}
            </ol>
          </Panel>
        )}

        {tab === "agents" && <div className="space-y-3">{c.agent_runs.map((r: any) => <AgentRunCard key={r.id} run={r} />)}</div>}

        {tab === "audit" && (
          <Panel>
            <PanelTitle hint="All audit events sharing this case's correlation id">Audit trail</PanelTitle>
            <ul className="divide-y divide-line text-sm">
              {auditLog?.map((e) => (
                <li key={e.id} className="grid gap-1 py-2.5 sm:grid-cols-[5rem_14rem_1fr]">
                  <span className="font-mono text-xs text-ink-faint">seq {e.seq}</span>
                  <span className="font-medium">{e.action}</span>
                  <span className="text-ink-mute">{e.actor_type}:{e.actor_id} · {dt(e.created_at)} {e.n8n_execution_id && <span className="inline-flex items-center gap-1">· n8n #{e.n8n_execution_id}<ExternalLink className="h-3 w-3" /></span>}</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>
      <p className="mt-6 font-mono text-xs text-ink-faint">correlation {c.correlation_id}</p>
    </>
  );
}
