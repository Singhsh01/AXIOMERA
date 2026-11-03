"use client";
import Link from "next/link";
import { Chart } from "@/components/Chart";
import { RunStrip } from "@/components/RunStrip";
import { Badge, Empty, More, PageHeader, Priority, Section, Skeleton, Stat, Status } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { ago, human, ms, pct, until, usd } from "@/lib/format";

export default function CommandCenter() {
  const { data: d } = useApi<any>("/dashboard/summary", { live: 5000 });
  const { data: a } = useApi<any>("/analytics/overview?days=14", { live: 15000 });
  const { data: integ } = useApi<any[]>("/integrations", { live: 30000 });
  const slaTotal = d ? Math.max(1, d.sla.on_track + d.sla.at_risk + d.sla.breached) : 1;

  return (
    <>
      <PageHeader title="Command center" sub="Read live from the database that the n8n workflows write into: what is moving, what is stuck, and what is waiting for a person." />

      {/* Metric strip: five figures, hairline separators, no boxes. */}
      <div className="grid grid-cols-2 gap-y-8 lg:grid-cols-5">
        {d ? (
          <>
            <Stat label="Open cases" value={d.open_cases} sub={`${d.sla.breached} past SLA · ${d.sla.at_risk} due within 2 h`} tone={d.sla.breached ? "bad" : undefined} />
            <Stat label="Awaiting decision" value={d.pending_approvals_count} sub="Consequential actions on hold" tone={d.pending_approvals_count ? "warn" : undefined} />
            <Stat label="Workflow success" value={pct(a?.workflow_success_rate)} sub={`${a?.workflow_runs ?? "…"} n8n runs · 14 days`} />
            <Stat label="Proposals in review" value={d.proposals_in_review} sub={`${d.deadlines.length} tender deadlines · 30 days`} />
            <Stat label="AI spend · 14 days" value={usd(a?.estimated_ai_cost_usd)} sub={a && Object.keys(a.model_usage).every((k: string) => k.startsWith("fixture") || k === "deterministic") ? `${a.agent_runs} runs · fixtures only` : `${a?.agent_runs ?? "…"} agent runs`} />
          </>
        ) : Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-[112px]" />)}
      </div>

      <div className="mt-16 grid gap-12 xl:grid-cols-[1.6fr_1fr]">
        <Section index="A" title="Live workflow activity" hint="Each row is an n8n execution; marks are the steps it reported to the API." action={<More href="/app/workflows">Workflow studio</More>}>
          {d?.recent_runs?.length ? <div>{d.recent_runs.map((r: any) => <RunStrip key={r.id} run={r} />)}</div>
            : d ? <Empty title="No workflow runs yet" body="Send an event to an n8n webhook or submit a request from Cases." /> : <Skeleton className="h-64" />}
        </Section>

        {/* Decisions band: the one place on the page that asks something of a person. */}
        <section className="h-fit bg-inverse p-7 text-inverse-fg">
          <p className="font-mono text-[11px] uppercase tracking-label text-inverse-fg/60">B · Awaiting a decision</p>
          <p className="mt-4 font-display text-[64px] font-bold leading-none tracking-[-0.05em] tabular">{d?.pending_approvals_count ?? "—"}</p>
          <p className="mt-2 text-[13px] text-inverse-fg/70">Approving resumes the n8n execution that is waiting on it.</p>
          <ul className="mt-6 border-t border-inverse-fg/15">
            {d?.pending_approvals?.slice(0, 6).map((p: any) => (
              <li key={p.id} className="border-b border-inverse-fg/15">
                <Link href={`/app/approvals?focus=${p.id}`} className="focus-ring group flex items-center justify-between gap-3 py-3">
                  <span className="min-w-0">
                    <span className="block truncate text-[13.5px] font-semibold group-hover:underline">{p.summary}</span>
                    <span className="block font-mono text-[10.5px] text-inverse-fg/60">{p.policy_rule} · {p.required_role} · {ago(p.created_at)}</span>
                  </span>
                  <span className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-inverse-fg/80">{p.risk_level}</span>
                </Link>
              </li>
            ))}
            {d && !d.pending_approvals.length && <li className="py-3 text-sm text-inverse-fg/70">Nothing is waiting on a decision.</li>}
          </ul>
          <Link href="/app/approvals" className="focus-ring mt-6 inline-flex h-10 items-center gap-2 border border-inverse-fg/30 px-4 font-mono text-[11px] uppercase tracking-label hover:bg-inverse-fg/10">
            Open approval center <span aria-hidden>→</span>
          </Link>
        </section>
      </div>

      <div className="mt-16 grid gap-12 lg:grid-cols-[2fr_1fr]">
        <Section index="C" title="Case volume" hint="Cases created per day, last 14 days">
          {a ? (a.cases_per_day.length ? <Chart kind="bar" label="Cases per day" categories={a.cases_per_day.map((x: any) => x.day.slice(5))} series={[{ name: "Cases", data: a.cases_per_day.map((x: any) => x.count) }]} />
            : <Empty title="No cases in this window" />) : <Skeleton className="h-[220px]" />}
        </Section>
        <Section index="D" title="Service levels" hint="Open cases against their response target">
          {d && (
            <>
              <div className="flex h-3 w-full overflow-hidden bg-raised" role="img" aria-label={`${d.sla.on_track} on track, ${d.sla.at_risk} due within 2 hours, ${d.sla.breached} breached`}>
                <span className="bg-ok" style={{ width: `${(d.sla.on_track / slaTotal) * 100}%` }} />
                <span className="bg-warn" style={{ width: `${(d.sla.at_risk / slaTotal) * 100}%` }} />
                <span className="bg-bad" style={{ width: `${(d.sla.breached / slaTotal) * 100}%` }} />
              </div>
              <dl className="mt-6 grid grid-cols-3">
                {[["On track", d.sla.on_track, "text-ok"], ["Due < 2 h", d.sla.at_risk, "text-warn"], ["Breached", d.sla.breached, "text-bad"]].map(([l, v, c]) => (
                  <div key={l as string} className="border-l border-line pl-3">
                    <dt className="label">{l}</dt>
                    <dd className={`mt-2 font-display text-[28px] font-semibold tabular ${c}`}>{v as number}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-6 text-[13px] text-ink-mute">SLA compliance over 14 days: <span className="font-semibold text-ink">{pct(a?.sla_compliance)}</span></p>
            </>
          )}
        </Section>
      </div>

      <div className="mt-16 grid gap-12 lg:grid-cols-3">
        <Section index="E" title="Agent activity" action={<More href="/app/agents">Mission control</More>}>
          <ul>
            {d?.agent_activity?.slice(0, 7).map((r: any) => (
              <li key={r.id} className="flex items-center justify-between gap-3 border-b border-line py-2.5 last:border-0">
                <div className="min-w-0"><p className="truncate text-[13.5px]">{r.task}</p><p className="font-mono text-[10.5px] text-ink-mute">{r.agent} · {r.tool_calls} tools · {ms(r.latency_ms)}</p></div>
                <Status value={r.status} />
              </li>
            ))}
          </ul>
        </Section>
        <Section index="F" title="Proposal pipeline" action={<More href="/app/rfps">Proposals</More>}>
          {d && <Chart kind="bar" horizontal height={230} label="RFPs by stage"
            categories={Object.keys(d.proposal_pipeline).map(human).reverse()} series={[{ name: "RFPs", data: Object.values(d.proposal_pipeline as Record<string, number>).reverse() }]} />}
        </Section>
        <Section index="G" title="Upcoming deadlines" hint="Submission deadlines within 30 days">
          <ul>
            {d?.deadlines?.map((x: any) => (
              <li key={x.rfp_id} className="border-b border-line py-3 last:border-0">
                <Link href={`/app/rfps/${x.rfp_id}`} className="line-clamp-1 text-[13.5px] font-semibold hover:text-accent">{x.title}</Link>
                <p className={`mt-0.5 font-mono text-[10.5px] ${x.hours_left < 72 ? "text-warn" : "text-ink-mute"}`}>Due {until(x.due)} · {x.open_mandatory} mandatory not evidenced</p>
              </li>
            ))}
            {d && !d.deadlines.length && <li className="text-sm text-ink-mute">No submissions due in the next 30 days.</li>}
          </ul>
        </Section>
      </div>

      <div className="mt-16 grid gap-12 lg:grid-cols-[1fr_1.2fr]">
        <Section index="H" title="Recent incidents" action={<More href="/app/cases?kind=incident">All incidents</More>}>
          <ul>
            {d?.incidents?.map((c: any) => (
              <li key={c.id} className="flex items-center justify-between gap-3 border-b border-line py-2.5 last:border-0">
                <Link href={`/app/cases/${c.id}`} className="flex min-w-0 items-center gap-2.5 hover:text-accent">
                  <Priority p={c.priority} /><span className="truncate text-[13.5px]"><span className="font-mono text-ink-faint">#{c.number}</span> {c.title}</span>
                </Link>
                <span className="flex items-center gap-2">{c.jira && <Badge t="signal">{c.jira}</Badge>}<Status value={c.status} /></span>
              </li>
            ))}
            {d && !d.incidents.length && <li className="py-3 text-sm text-ink-mute">No incidents reported.</li>}
          </ul>
        </Section>
        <Section index="I" title="Integration health" hint="Health checks run when this page loads" action={<More href="/app/integrations">Manage</More>}>
          <div className="grid grid-cols-2 border-l border-t border-line sm:grid-cols-4">
            {integ?.map((i: any) => (
              <div key={i.kind} className="border-b border-r border-line p-4">
                <p className="text-[13.5px] font-semibold">{i.display_name}</p>
                <div className="mt-3 flex flex-wrap gap-1.5"><Status value={i.health?.status} /><Badge t={i.effective_mode === "live" ? "ok" : "signal"}>{i.effective_mode}</Badge></div>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </>
  );
}
