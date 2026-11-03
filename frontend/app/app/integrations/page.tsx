"use client";
import { useState } from "react";
import { can, useMe } from "@/components/me";
import { Badge, Button, ErrorNote, JsonBlock, PageHeader, Panel, Skeleton, Status } from "@/components/ui/primitives";
import { patch, post, useApi } from "@/lib/api";
import { ago } from "@/lib/format";

export default function Integrations() {
  const { data, mutate } = useApi<any[]>("/integrations", { live: 10000 });
  const me = useMe();
  const [sel, setSel] = useState<string | null>(null);
  const { data: records } = useApi<any[]>(sel ? `/integrations/${sel}/records` : null);
  const [err, setErr] = useState<unknown>(null);
  const admin = can(me, "integration.manage");

  return (
    <>
      <PageHeader title="Integrations" sub="Connectors run against local simulators unless live credentials are present in the environment. Simulated records are always labelled as such; payments are never live in this project." />
      <ErrorNote error={err} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {!data && [0, 1, 2].map((i) => <Skeleton key={i} className="h-44" />)}
        {data?.map((c) => (
          <Panel key={c.kind}>
            <div className="flex items-start justify-between gap-2">
              <div><h2 className="font-display text-lg font-semibold">{c.display_name}</h2><p className="text-xs text-ink-mute">{c.kind === "n8n" ? c.health?.url : `${c.simulator_records ?? 0} simulator records${c.last_check_at ? ` · checked ${ago(c.last_check_at)}` : ""}`}</p></div>
              <div className="flex gap-1.5"><Status value={c.health?.status} /><Badge t={c.effective_mode === "live" ? "ok" : "cyan"}>{c.effective_mode}</Badge></div>
            </div>
            {c.kind !== "n8n" && (
              <>
                <p className="mt-3 text-sm text-ink-soft">{c.live_credentials_present ? "Live credentials found." : c.secret_ref ? `Set ${c.secret_ref} to enable live mode.` : "Simulator only."}
                  {c.health?.injected_failures_pending > 0 && <span className="text-warn"> {c.health.injected_failures_pending} injected failure(s) pending.</span>}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setSel(sel === c.kind ? null : c.kind)}>{sel === c.kind ? "Hide records" : "Show records"}</Button>
                  {admin && c.kind !== "payments" && c.live_credentials_present && (
                    <Button size="sm" onClick={async () => { setErr(null); try { await patch(`/integrations/${c.kind}`, { mode: c.mode === "live" ? "simulator" : "live" }); mutate(); } catch (e) { setErr(e); } }}>
                      Switch to {c.mode === "live" ? "simulator" : "live"}
                    </Button>
                  )}
                  {admin && c.effective_mode === "simulator" && (
                    <Button size="sm" variant="danger" title="Next calls fail with HTTP 503 so n8n retry and dead-letter paths can be observed"
                      onClick={async () => { await post(`/integrations/${c.kind}/inject-failures`, { count: c.health?.injected_failures_pending ? 0 : 2 }); mutate(); }}>
                      {c.health?.injected_failures_pending ? "Clear failures" : "Inject 2 failures"}
                    </Button>
                  )}
                </div>
              </>
            )}
          </Panel>
        ))}
      </div>
      {sel && (
        <Panel className="mt-5">
          <h2 className="mb-3 font-display text-lg font-semibold">Simulator records: {sel}</h2>
          <div className="space-y-2">{records?.map((r) => (
            <details key={r.id} className="rounded-lg border border-line p-3 text-sm"><summary className="cursor-pointer"><span className="font-mono text-cyan">{r.external_id}</span> {r.operation} <span className="text-ink-mute">· {ago(r.created_at)}</span></summary><JsonBlock value={r.payload} className="mt-2" /></details>
          ))}{records && !records.length && <p className="text-sm text-ink-mute">No records yet.</p>}</div>
        </Panel>
      )}
    </>
  );
}
