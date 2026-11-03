"use client";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Badge, JsonBlock, Status } from "@/components/ui/primitives";
import { dt, ms, usd } from "@/lib/format";

export function AgentRunCard({ run, defaultOpen = false }: { run: any; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const budget = run.budget || {};
  const tokens = (run.input_tokens || 0) + (run.output_tokens || 0);
  return (
    <div className="glass">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="focus-ring flex w-full flex-wrap items-center justify-between gap-3 rounded-panel p-4 text-left">
        <div className="min-w-0">
          <p className="font-medium">{run.agent} <span className="font-normal text-ink-mute">· {run.task}</span></p>
          <p className="mt-0.5 text-xs text-ink-mute">{dt(run.started_at)} · {run.provider}/{run.model} · prompt {run.prompt_version} · {ms(run.latency_ms)} · {tokens} tokens · {usd(run.cost_usd)}</p>
        </div>
        <span className="flex items-center gap-2">
          {run.security_flags?.length > 0 && <Badge t="warn">{run.security_flags.length} flag(s)</Badge>}
          <Status value={run.status} />
          <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </span>
      </button>
      {open && (
        <div className="grid gap-4 border-t border-line p-4 lg:grid-cols-2">
          <div className="space-y-3">
            {run.reasoning_summary && <div><p className="text-xs text-ink-mute">Reasoning summary</p><p className="mt-1 text-sm">{run.reasoning_summary}</p></div>}
            <div>
              <p className="mb-1.5 text-xs text-ink-mute">Tool calls</p>
              <ol className="space-y-1.5">
                {(run.tool_calls || []).map((t: any) => (
                  <li key={t.id} className="rounded-lg border border-line px-3 py-2 text-sm">
                    <div className="flex items-center justify-between gap-2"><span className="font-mono text-[13px] text-cyan">{t.tool}</span><span className="flex items-center gap-2 text-xs text-ink-mute">{t.latency_ms} ms <Status value={t.status === "ok" ? "succeeded" : t.status === "denied" ? "rejected" : "failed"} /></span></div>
                    <p className="mt-1 line-clamp-2 font-mono text-[11px] text-ink-faint">{JSON.stringify(t.arguments)}</p>
                  </li>
                ))}
                {!run.tool_calls?.length && <li className="text-sm text-ink-mute">No tool calls.</li>}
              </ol>
            </div>
            {run.context_refs?.length > 0 && (
              <div><p className="mb-1.5 text-xs text-ink-mute">Context sources</p>
                <div className="flex flex-wrap gap-1.5">{run.context_refs.slice(0, 12).map((c: any, i: number) => <Badge key={i} t="violet">{c.type}: {c.label ?? c.id}</Badge>)}</div></div>
            )}
          </div>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2 text-xs">
              {[["Tool calls", run.tool_calls?.length ?? 0, budget.max_tool_calls], ["Tokens", tokens, budget.max_tokens], ["Cost $", run.cost_usd ?? 0, budget.max_cost_usd]].map(([l, v, m]) => (
                <div key={l as string} className="rounded-lg border border-line p-2">
                  <p className="text-ink-mute">{l}</p><p className="tabular text-ink">{v as number} / {m as number}</p>
                  <div className="mt-1 h-1 rounded bg-white/5"><div className="h-1 rounded bg-gradient-to-r from-violet to-cyan" style={{ width: `${Math.min(100, ((v as number) / ((m as number) || 1)) * 100)}%` }} /></div>
                </div>
              ))}
            </div>
            {run.error && <p className="rounded-lg border border-bad/30 bg-bad/10 p-2 text-sm text-bad">{run.error}</p>}
            {run.output && <JsonBlock value={run.output} className="max-h-64" />}
          </div>
        </div>
      )}
    </div>
  );
}
