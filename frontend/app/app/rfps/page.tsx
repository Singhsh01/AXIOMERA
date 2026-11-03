"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { can, useMe } from "@/components/me";
import { Badge, Button, Empty, ErrorNote, Field, inputCls, Modal, PageHeader, Skeleton, Status } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { ago, until } from "@/lib/format";

const ORDER = ["compliant", "partially_compliant", "non_compliant", "unverified"];
const COLOR: Record<string, string> = { compliant: "bg-ok", partially_compliant: "bg-warn", non_compliant: "bg-bad", unverified: "bg-ink-faint" };

export default function Rfps() {
  const { data, mutate } = useApi<any[]>("/rfps", { live: 5000 });
  const me = useMe();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const form = useRef<HTMLFormElement>(null);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await post("/rfps", new FormData(form.current!)); setOpen(false); mutate(); }
    catch (x) { setErr(x); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="Proposals" sub="Upload a tender and n8n Workflow C extracts its requirements, checks them against approved company knowledge and drafts a proposal for review."
        actions={can(me, "rfp.write") && <Button variant="primary" onClick={() => setOpen(true)}>Upload tender</Button>} />
      <div className="grid gap-3">
        {!data && <Skeleton className="h-40" />}
        {data && !data.length && <Empty title="No tenders yet" body="Upload a PDF or DOCX. The demo tender lives in backend/seed/rfps." />}
        {data?.map((r) => {
          const total = ORDER.reduce((a, k) => a + (r.compliance[k] ?? 0), 0) || 1;
          return (
            <Link key={r.id} href={`/app/rfps/${r.id}`} className="focus-ring plate grid gap-4 p-5 transition-colors hover:bg-ink/[0.04] md:grid-cols-[1.4fr_1fr_auto] md:items-center">
              <div className="min-w-0">
                <p className="truncate font-display text-lg font-semibold">{r.title}</p>
                <p className="text-sm text-ink-mute">{r.issuer ?? "Unknown issuer"}{r.reference && `, ref. ${r.reference}`} · uploaded {ago(r.created_at)}</p>
                <div className="mt-2 flex flex-wrap gap-1.5"><Status value={r.status} />{r.security_flags?.length > 0 && <Badge t="warn">{r.security_flags.length} manipulation flag(s)</Badge>}
                  {r.latest_proposal && <Badge t="accent">proposal v{r.latest_proposal.version} {r.latest_proposal.status.replace("_", " ")}</Badge>}</div>
              </div>
              <div>
                <p className="mb-1.5 text-xs text-ink-mute">{r.requirements} requirements</p>
                <div className="flex h-2 overflow-hidden rounded-full bg-ink/5" role="img" aria-label={ORDER.map((k) => `${r.compliance[k] ?? 0} ${k}`).join(", ")}>
                  {ORDER.map((k) => <span key={k} className={`${COLOR[k]} h-full border-r-2 border-surface last:border-0`} style={{ width: `${((r.compliance[k] ?? 0) / total) * 100}%` }} />)}
                </div>
                <p className="mt-1.5 text-xs text-ink-mute">{ORDER.filter((k) => r.compliance[k]).map((k) => `${r.compliance[k]} ${k.replace("_", " ")}`).join(", ") || "Not assessed yet"}</p>
              </div>
              <div className={`text-sm md:text-right ${r.hours_left !== null && r.hours_left < 72 ? "text-warn" : "text-ink-soft"}`}>
                {r.submission_due_at ? <>Due {until(r.submission_due_at)}</> : "No deadline found"}
              </div>
            </Link>
          );
        })}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Upload a tender">
        <form ref={form} onSubmit={upload} className="space-y-4">
          <Field label="Title"><input name="title" required minLength={3} className={inputCls} placeholder="Digital case management platform" /></Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Issuer"><input name="issuer" className={inputCls} /></Field>
            <Field label="Reference"><input name="reference" className={inputCls} /></Field>
          </div>
          <Field label="Document" hint="PDF or DOCX, up to 25 MB. Instructions inside the document are treated as data, never as commands.">
            <input name="file" type="file" accept=".pdf,.docx" required className="block w-full text-sm text-ink-soft file:mr-3 file:rounded-control file:border-0 file:bg-accent/20 file:px-3 file:py-1.5 file:text-ink" />
          </Field>
          <ErrorNote error={err} />
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button variant="primary" loading={busy}>Upload and process</Button></div>
        </form>
      </Modal>
    </>
  );
}
