"use client";
import Link from "next/link";
import { Badge, PageHeader, Skeleton, Status } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { ago } from "@/lib/format";

export default function Workflows() {
  const { data } = useApi<any>("/workflows", { live: 10000 });
  return (
    <>
      <PageHeader title="Workflow studio" sub="The n8n workflows in this repository, rendered from their version-controlled JSON and overlaid with the executions they reported. Editing happens in n8n; Orkestr shows what ran."
        actions={data && <Badge t={data.n8n.status === "healthy" ? "ok" : "bad"} dot={data.n8n.status === "healthy"}>n8n {data.n8n.status}</Badge>} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {!data && [0, 1, 2].map((i) => <Skeleton key={i} className="h-44" />)}
        {data?.workflows.map((w: any) => {
          const total = Object.values(w.stats as Record<string, number>).reduce((a, b) => a + b, 0);
          return (
            <Link key={w.key} href={`/app/workflows/${w.key}`} className="focus-ring glass group block p-5 transition-colors hover:bg-white/[0.05]">
              <div className="flex items-start gap-4">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-line bg-midnight font-display text-xl font-semibold text-cyan">{w.key}</span>
                <div className="min-w-0">
                  <h2 className="font-display text-lg font-semibold">{w.name}</h2>
                  <p className="text-xs text-ink-mute">{w.nodes} nodes · {w.triggers.join(", ") || "sub-workflow"} · n8n id {w.n8n_id}</p>
                </div>
              </div>
              <div className="mt-5 flex items-center justify-between text-sm">
                <span className="text-ink-mute">{total} runs · {w.stats.failed ?? 0} failed · {w.stats.waiting ?? 0} waiting</span>
                {w.last_run ? <span className="flex items-center gap-2 text-xs text-ink-mute">{ago(w.last_run.started_at)}<Status value={w.last_run.status} /></span> : <span className="text-xs text-ink-faint">never run</span>}
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
