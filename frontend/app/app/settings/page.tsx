"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { can, useMe } from "@/components/me";
import { Badge, Button, ErrorNote, PageHeader, Panel, PanelTitle, Skeleton } from "@/components/ui/primitives";
import { put, useApi } from "@/lib/api";

const Monaco = dynamic(() => import("@monaco-editor/react"), { ssr: false, loading: () => <Skeleton className="h-[520px]" /> });

export default function Policies() {
  const { data, mutate } = useApi<any>("/policies/approvals");
  const me = useMe();
  const [text, setText] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setText(JSON.stringify(data, null, 2)); }, [data]);
  const admin = can(me, "admin");

  async function save() {
    setBusy(true); setErr(null); setSaved(false);
    try { await put("/policies/approvals", JSON.parse(text)); setSaved(true); mutate(); }
    catch (e: any) { setErr(e instanceof SyntaxError ? new Error(`Invalid JSON: ${e.message}`) : e); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="Approval policies" sub="Which actions need a human, at what risk level, and which role may decide. The first matching rule wins; anything unmatched requires approval." />
      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <Panel className="p-3">
          <div className="overflow-hidden rounded-lg border border-line">
            {data ? <Monaco height="560px" defaultLanguage="json" theme="vs-dark" value={text} onChange={(v) => { setText(v ?? ""); setSaved(false); }}
              options={{ readOnly: !admin, minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false, tabSize: 2 }} /> : <Skeleton className="h-[560px]" />}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3 px-1">
            {admin ? <Button variant="primary" loading={busy} onClick={save}>Save policies</Button> : <Badge>Read only. Admins can edit.</Badge>}
            {saved && <span className="text-sm text-ok">Policies saved and recorded in the audit log.</span>}
          </div>
          <div className="mt-3"><ErrorNote error={err} /></div>
        </Panel>
        <Panel className="h-fit">
          <PanelTitle>Rules the server enforces on save</PanelTitle>
          <ul className="space-y-3 text-sm leading-relaxed text-ink-soft">
            <li>Refunds, credits, customer emails, account changes and proposal submissions must always require approval.</li>
            <li>The default rule must require approval, so a new action type can never run unreviewed.</li>
            <li>Risk must be low, medium, high or critical; the required role must exist.</li>
            <li>Approvals are bound to a hash of the exact parameters. If an agent or a person changes them afterwards, execution is refused.</li>
            <li>Whoever requested an action cannot approve it.</li>
          </ul>
        </Panel>
      </div>
    </>
  );
}
