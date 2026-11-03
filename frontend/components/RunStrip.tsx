"use client";
import Link from "next/link";
import { Status } from "@/components/ui/primitives";
import { ago, cn, ms } from "@/lib/format";

const NAMES: Record<string, string> = { A: "Customer intake", B: "Incident escalation", C: "RFP processing", D: "Deadline monitor", E: "Approval & audit", Z: "Error handler" };

export function RunStrip({ run }: { run: any }) {
  const steps: any[] = run.steps || [];
  return (
    <Link href={`/app/workflows/${run.workflow_key}?run=${run.id}`}
      className="focus-ring grid grid-cols-[2rem_1fr_auto] items-center gap-4 border-b border-line py-3 transition-colors last:border-0 hover:bg-raised/50 sm:grid-cols-[2rem_13rem_1fr_auto]">
      <span className="grid h-8 w-8 place-items-center border border-ink/20 font-mono text-[13px] font-medium text-ink">{run.workflow_key}</span>
      <span className="min-w-0">
        <span className="block truncate text-[13.5px] font-semibold">{NAMES[run.workflow_key]}</span>
        <span className="block font-mono text-[10.5px] text-ink-mute">{run.n8n_execution_id ? `n8n #${run.n8n_execution_id}` : run.trigger} · {ago(run.started_at)}</span>
      </span>
      <span className="hidden items-center gap-1 sm:flex" aria-label={`${run.step_count} steps, ${run.retries} retries`}>
        {steps.length ? steps.slice(0, 14).map((s) => (
          <span key={s.id} title={`${s.node}: ${s.status}${s.attempt > 1 ? ` (attempt ${s.attempt})` : ""}`}
            className={cn("h-3 w-[7px]", s.status === "failed" ? "bg-bad" : s.status === "waiting" ? "bg-warn" : s.attempt > 1 ? "bg-signal" : "bg-ink/70")} />
        )) : <span className="text-xs text-ink-faint">{run.step_count} steps, {ms(run.duration_ms)}</span>}
        {run.retries > 0 && <span className="ml-2 font-mono text-[10.5px] text-signal">{run.retries} retried</span>}
      </span>
      <Status value={run.status} />
    </Link>
  );
}
