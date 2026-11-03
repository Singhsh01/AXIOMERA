"use client";
import Link from "next/link";
import { Badge, PageHeader, Skeleton, Status } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { ago } from "@/lib/format";

export default function Workflows() {
  const { data } = useApi<any>("/workflows", { live: 10000 });
  return (
    <>
      <PageHeader title="Workflow studio" sub="The n8n workflows in this repository, drawn from their version-controlled JSON and overlaid with the executions they reported. Editing happens in n8n; this view shows what actually ran."
        actions={data && <Badge t={data.n8n.status === "healthy" ? "ok" : "bad"} dot={data.n8n.status === "healthy"}>n8n {data.n8n.status}</Badge>} />
      <div className="grid border-l border-t border-line md:grid-cols-2 xl:grid-cols-3">
        {!data && [0, 1, 2].map((i) => <Skeleton key={i} className="h-56 border-b border-r border-line" />)}
        {data?.workflows.map((w: any) => {
          const total = Object.values(w.stats as Record<string, number>).reduce((a, b) => a + b, 0);
          return (
            <Link key={w.key} href={`/app/workflows/${w.key}`} className="focus-ring group relative flex min-h-[240px] flex-col border-b border-r border-line bg-surface/40 p-7 transition-colors duration-300 hover:bg-surface">
              <div className="flex items-start justify-between">
                <span className="font-display text-[72px] font-bold leading-[0.8] tracking-[-0.06em] text-ink/15 transition-colors duration-300 group-hover:text-accent">{w.key}</span>
                {w.last_run ? <Status value={w.last_run.status} /> : <Badge>never run</Badge>}
              </div>
              <h2 className="mt-auto pt-8 font-display text-[20px] font-bold tracking-[-0.02em]">{w.name}</h2>
              <p className="mt-1 font-mono text-[10.5px] text-ink-mute">{w.nodes} nodes · {w.triggers.join(", ") || "sub-workflow"} · {w.n8n_id}</p>
              <div className="mt-5 flex items-center justify-between border-t border-line pt-4 text-[12.5px] text-ink-mute">
                <span><span className="font-semibold text-ink tabular">{total}</span> runs · {w.stats.failed ?? 0} failed · {w.stats.waiting ?? 0} waiting</span>
                <span className="flex items-center gap-2">{w.last_run && ago(w.last_run.started_at)}<span aria-hidden className="transition-transform duration-300 ease-arch group-hover:translate-x-1">→</span></span>
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
