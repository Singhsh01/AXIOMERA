"use client";
import Link from "next/link";
import { Chart } from "@/components/Chart";
import { RunStrip } from "@/components/RunStrip";
import { Badge, Empty, PageHeader, Panel, PanelTitle, Priority, Skeleton, Stat, Status } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { ago, human, ms, pct, until, usd } from "@/lib/format";

export default function CommandCenter() {
  const { data: d } = useApi<any>("/dashboard/summary", { live: 5000 });
  const { data: a } = useApi<any>("/analytics/overview?days=14", { live: 15000 });
  const { data: integ } = useApi<any[]>("/integrations", { live: 30000 });

  return (
    <>
      <PageHeader title="Command center" sub="Everything below is read live from the Orkestr database that n8n workflows write into." />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {d ? (
          <>
            <Stat label="Open cases" value={d.open_cases} sub={`${d.sla.breached} past SLA, ${d.sla.at_risk} due within 2h`} tone={d.sla.breached ? "bad" : undefined} />
            <Stat label="Waiting for approval" value={d.pending_approvals_count} sub="Consequential actions on hold" tone={d.pending_approvals_count ? "warn" : undefined} />
            <Stat label="Workflow success" value={pct(a?.workflow_success_rate)} sub={`${a?.workflow_runs ?? "…"} runs in 14 days`} />
            <Stat label="Proposals in review" value={d.proposals_in_review} sub={`${d.deadlines.length} tender deadlines in 30 days`} />
            <Stat label="AI spend, 14 days" value={usd(a?.estimated_ai_cost_usd)} sub={a && Object.keys(a.model_usage).every((k: string) => k.startsWith("fixture") || k === "deterministic") ? `${a.agent_runs} runs, fixtures only` : `${a?.agent_runs ?? "…"} agent runs`} />
          </>
        ) : Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.55fr_1fr]">
        <Panel>
          <PanelTitle hint="Each row is an n8n execution; dots are the steps it reported to the API." action={<Link className="text-sm text-cyan hover:underline" href="/app/workflows">Open workflow studio</Link>}>
            Live workflow activity
          </PanelTitle>
          <div className="space-y-1">
            {d?.recent_runs?.length ? d.recent_runs.map((r: any) => <RunStrip key={r.id} run={r} />) : d ? <Empty title="No workflow runs yet" body="Send an event to an n8n webhook or submit a request from Cases." /> : <Skeleton className="h-64" />}
          </div>
        </Panel>
        <Panel>
          <PanelTitle hint="Newest first. Approving resumes the waiting n8n execution." action={<Link className="text-sm text-cyan hover:underline" href="/app/approvals">All approvals</Link>}>
            Pending approvals
          </PanelTitle>
          <ul className="divide-y divide-line">
            {d?.pending_approvals?.map((p: any) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <Link href={`/app/approvals?focus=${p.id}`} className="block truncate text-sm font-medium hover:text-cyan">{p.summary}</Link>
                  <p className="text-xs text-ink-mute">{p.policy_rule} needs {p.required_role}, requested {ago(p.created_at)}</p>
                </div>
                <Badge t={p.risk_level === "critical" ? "bad" : p.risk_level === "high" ? "warn" : "info"}>{p.risk_level}</Badge>
              </li>
            ))}
            {d && !d.pending_approvals.length && <li className="py-3 text-sm text-ink-mute">Nothing is waiting on a decision.</li>}
          </ul>
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <PanelTitle hint="Cases created per day, last 14 days">Case volume</PanelTitle>
          {a ? (a.cases_per_day.length ? <Chart kind="bar" label="Cases per day" categories={a.cases_per_day.map((x: any) => x.day.slice(5))} series={[{ name: "Cases", data: a.cases_per_day.map((x: any) => x.count) }]} />
            : <Empty title="No cases in this window" />) : <Skeleton className="h-[220px]" />}
        </Panel>
        <Panel>
          <PanelTitle hint="Open cases against their response target">SLA status</PanelTitle>
          {d && (
            <div className="space-y-3">
              {[["On track", d.sla.on_track, "bg-ok"], ["Due within 2 hours", d.sla.at_risk, "bg-warn"], ["Breached", d.sla.breached, "bg-bad"]].map(([l, v, c]) => {
                const total = Math.max(1, d.sla.on_track + d.sla.at_risk + d.sla.breached);
                return (
                  <div key={l as string}>
                    <div className="mb-1 flex justify-between text-sm"><span className="text-ink-soft">{l}</span><span className="tabular">{v as number}</span></div>
                    <div className="h-2 rounded-full bg-ink/[0.05]"><div className={`h-2 rounded-full ${c}`} style={{ width: `${((v as number) / total) * 100}%` }} /></div>
                  </div>
                );
              })}
              <p className="pt-2 text-xs text-ink-mute">SLA compliance over 14 days: {pct(a?.sla_compliance)}</p>
            </div>
          )}
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Panel>
          <PanelTitle action={<Link className="text-sm text-cyan hover:underline" href="/app/agents">Mission control</Link>}>Agent activity</PanelTitle>
          <ul className="space-y-2.5">
            {d?.agent_activity?.slice(0, 7).map((r: any) => (
              <li key={r.id} className="flex items-center justify-between gap-3 text-sm">
                <div className="min-w-0"><p className="truncate">{r.task}</p><p className="text-xs text-ink-mute">{r.agent}, {r.tool_calls} tool calls, {ms(r.latency_ms)}</p></div>
                <Status value={r.status} />
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelTitle action={<Link className="text-sm text-cyan hover:underline" href="/app/rfps">Proposals</Link>}>Proposal pipeline</PanelTitle>
          {d && <Chart kind="bar" horizontal height={230} label="RFPs by stage"
            categories={Object.keys(d.proposal_pipeline).map(human).reverse()} series={[{ name: "RFPs", data: Object.values(d.proposal_pipeline as Record<string, number>).reverse() }]} />}
        </Panel>
        <Panel>
          <PanelTitle hint="Submission deadlines within 30 days">Upcoming deadlines</PanelTitle>
          <ul className="space-y-3">
            {d?.deadlines?.map((x: any) => (
              <li key={x.rfp_id} className="text-sm">
                <Link href={`/app/rfps/${x.rfp_id}`} className="line-clamp-1 font-medium hover:text-cyan">{x.title}</Link>
                <p className={`text-xs ${x.hours_left < 72 ? "text-warn" : "text-ink-mute"}`}>Due {until(x.due)}, {x.open_mandatory} mandatory requirement(s) not evidenced</p>
              </li>
            ))}
            {d && !d.deadlines.length && <li className="text-sm text-ink-mute">No submissions due in the next 30 days.</li>}
          </ul>
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Panel>
          <PanelTitle action={<Link className="text-sm text-cyan hover:underline" href="/app/cases?kind=incident">All incidents</Link>}>Recent incidents</PanelTitle>
          <ul className="divide-y divide-line">
            {d?.incidents?.map((c: any) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-2.5">
                <Link href={`/app/cases/${c.id}`} className="flex min-w-0 items-center gap-2.5 hover:text-cyan">
                  <Priority p={c.priority} /><span className="truncate text-sm">#{c.number} {c.title}</span>
                </Link>
                <span className="flex items-center gap-2">{c.jira && <Badge t="cyan">{c.jira}</Badge>}<Status value={c.status} /></span>
              </li>
            ))}
            {d && !d.incidents.length && <li className="py-3 text-sm text-ink-mute">No incidents reported.</li>}
          </ul>
        </Panel>
        <Panel>
          <PanelTitle hint="Health checks run when this page loads" action={<Link className="text-sm text-cyan hover:underline" href="/app/integrations">Manage</Link>}>Integration health</PanelTitle>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {integ?.map((i: any) => (
              <div key={i.kind} className="rounded-lg border border-line bg-ink/[0.02] p-3">
                <p className="text-sm font-medium">{i.display_name}</p>
                <div className="mt-2 flex flex-wrap gap-1.5"><Status value={i.health?.status} /><Badge t={i.effective_mode === "live" ? "ok" : "cyan"}>{i.effective_mode}</Badge></div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
