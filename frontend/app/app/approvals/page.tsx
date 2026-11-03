"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ApprovalActions } from "@/components/ApprovalActions";
import { Badge, Empty, JsonBlock, PageHeader, Panel, Skeleton, Status, Tabs } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { ago, cn, dt, human, until } from "@/lib/format";

function Approvals() {
  const focus = useSearchParams().get("focus");
  const [tab, setTab] = useState<"pending" | "decided">("pending");
  const { data, mutate } = useApi<any[]>(tab === "pending" ? "/approvals?status=pending" : "/approvals", { live: 5000 });
  const rows = tab === "pending" ? data : data?.filter((a) => a.status !== "pending");
  const [sel, setSel] = useState<string | null>(focus);
  const current = rows?.find((a) => a.id === sel) ?? rows?.[0];

  return (
    <>
      <PageHeader title="Approvals" sub="Refunds, credits, customer emails and account changes wait here. Approving resumes the n8n execution that requested it; nothing runs unless the parameters still match what you approved." />
      <Tabs value={tab} onChange={(t) => { setTab(t); setSel(null); }} items={[{ id: "pending", label: "Waiting for a decision" }, { id: "decided", label: "Decided" }]} />
      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1.15fr]">
        <div className="space-y-2">
          {!rows && <Skeleton className="h-60" />}
          {rows && !rows.length && <Empty title={tab === "pending" ? "Nothing is waiting on you" : "No decisions yet"} body="New approvals appear when an agent proposes a consequential action." />}
          {rows?.map((a) => (
            <button key={a.id} onClick={() => setSel(a.id)} className={cn("focus-ring glass block w-full p-4 text-left transition-colors", current?.id === a.id ? "border-violet/50 bg-violet/[0.06]" : "hover:bg-ink/[0.04]")}>
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium">{a.summary}</p>
                <Badge t={a.risk_level === "critical" ? "bad" : a.risk_level === "high" ? "warn" : "info"}>{a.risk_level}</Badge>
              </div>
              <p className="mt-1 text-xs text-ink-mute">{a.policy_rule} · needs {a.required_role} · {a.status === "pending" ? `expires ${until(a.expires_at)}` : `${a.status} ${ago(a.decided_at)}`}{a.waiting_in_n8n && " · n8n waiting"}</p>
            </button>
          ))}
        </div>
        {current && (
          <Panel className="h-fit lg:sticky lg:top-20">
            <div className="flex flex-wrap items-center gap-2"><h2 className="font-display text-xl font-semibold">{human(current.action_type)}</h2><Status value={current.status} /></div>
            {current.case && <Link href={`/app/cases/${current.case.id}`} className="mt-1 block text-sm text-cyan hover:underline">Case #{current.case.number}: {current.case.title}</Link>}
            {current.rationale && <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">{current.rationale}</p>}
            <p className="mt-5 text-xs text-ink-mute">Exact parameters that will be executed</p>
            <JsonBlock value={current.scope} className="mt-1.5" />
            <dl className="mt-4 grid grid-cols-[9rem_1fr] gap-y-1.5 text-sm">
              <dt className="text-ink-mute">Requested by</dt><dd>{current.requested_by}</dd>
              <dt className="text-ink-mute">Requested</dt><dd>{dt(current.created_at)}</dd>
              <dt className="text-ink-mute">Scope hash</dt><dd className="truncate font-mono text-xs">{current.scope_hash}</dd>
              {current.decided_at && <><dt className="text-ink-mute">Decision</dt><dd>{human(current.status)} {dt(current.decided_at)} {current.decision_note && `— “${current.decision_note}”`}</dd></>}
              {current.execution_result && <><dt className="text-ink-mute">Executed as</dt><dd>{current.execution_result.external_id} ({current.execution_result.mode})</dd></>}
            </dl>
            {current.status === "pending" && <div className="mt-5 border-t border-line pt-4"><ApprovalActions approval={current} onDone={mutate} /></div>}
          </Panel>
        )}
      </div>
    </>
  );
}

export default function Page() {
  return <Suspense><Approvals /></Suspense>;
}
