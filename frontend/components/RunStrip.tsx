"use client";
import Link from "next/link";
import { Status } from "@/components/ui/primitives";
import { ago, cn, ms } from "@/lib/format";

const NAMES: Record<string, string> = { A: "Customer intake", B: "Incident escalation", C: "RFP processing", D: "Deadline monitor", E: "Approval & audit", Z: "Error handler" };

export function RunStrip({ run }: { run: any }) {
  const steps: any[] = run.steps || [];
  return (
    <Link href={`/app/workflows/${run.workflow_key}?run=${run.id}`}
      className="focus-ring grid grid-cols-[2.2rem_1fr_auto] items-center gap-3 rounded-lg px-2 py-2 hover:bg-white/[0.04] sm:grid-cols-[2.2rem_12rem_1fr_auto]">
      <span className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-midnight font-display font-semibold text-cyan">{run.workflow_key}</span>
      <span className="min-w-0">
        <span className="block truncate text-sm">{NAMES[run.workflow_key]}</span>
        <span className="block text-xs text-ink-mute">{run.n8n_execution_id ? `n8n #${run.n8n_execution_id}` : run.trigger} · {ago(run.started_at)}</span>
      </span>
      <span className="hidden items-center gap-1 sm:flex" aria-label={`${run.step_count} steps, ${run.retries} retries`}>
        {steps.length ? steps.slice(0, 14).map((s) => (
          <span key={s.id} title={`${s.node}: ${s.status}${s.attempt > 1 ? ` (attempt ${s.attempt})` : ""}`}
            className={cn("h-2.5 w-2.5 rounded-full", s.status === "failed" ? "bg-bad" : s.status === "waiting" ? "bg-warn" : s.attempt > 1 ? "bg-cyan" : "bg-violet")} />
        )) : <span className="text-xs text-ink-faint">{run.step_count} steps, {ms(run.duration_ms)}</span>}
        {run.retries > 0 && <span className="ml-1 text-xs text-cyan">{run.retries} retried</span>}
      </span>
      <Status value={run.status} />
    </Link>
  );
}
