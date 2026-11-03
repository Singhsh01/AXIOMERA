"use client";
import { useRef, useState } from "react";
import { can, useMe } from "@/components/me";
import { Badge, Button, ErrorNote, Field, inputCls, Modal, PageHeader, Panel, PanelTitle, Skeleton } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { dt, human } from "@/lib/format";

export default function Knowledge() {
  const { data, mutate } = useApi<any[]>("/knowledge");
  const [q, setQ] = useState("availability per calendar month");
  const [query, setQuery] = useState(q);
  const { data: hits } = useApi<any[]>(query.length > 2 ? `/knowledge/search?q=${encodeURIComponent(query)}&k=6` : null);
  const me = useMe();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const form = useRef<HTMLFormElement>(null);
  const now = Date.now();

  return (
    <>
      <PageHeader title="Company knowledge" sub="The only material agents may cite: capability statements, certificates, product documentation, reference projects, approved bid answers and policies. Expired certificates are excluded from retrieval automatically."
        actions={can(me, "knowledge.write") && <Button variant="primary" onClick={() => setOpen(true)}>Add document</Button>} />
      <div className="grid gap-5 xl:grid-cols-[1fr_1.1fr]">
        <Panel className="p-0">
          <ul className="divide-y divide-line">
            {!data && <Skeleton className="m-4 h-60" />}
            {data?.map((d) => {
              const expired = d.valid_until && new Date(d.valid_until).getTime() < now;
              return (
                <li key={d.id} className="flex items-start justify-between gap-3 px-5 py-3.5">
                  <div className="min-w-0"><p className="font-medium">{d.title}</p><p className="text-xs text-ink-mute">{human(d.kind)} · {d.chunks} chunks · {d.source}</p></div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
                    {!d.approved && <Badge t="warn">awaiting approval</Badge>}
                    {d.valid_until && <Badge t={expired ? "bad" : "ok"}>{expired ? "expired" : "valid until"} {dt(d.valid_until).slice(0, 6)}</Badge>}
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
        <Panel>
          <PanelTitle hint="PostgreSQL full-text and pgvector results fused with reciprocal rank fusion">Retrieval playground</PanelTitle>
          <form onSubmit={(e) => { e.preventDefault(); setQuery(q); }} className="flex gap-2">
            <input aria-label="Search query" className={inputCls} value={q} onChange={(e) => setQ(e.target.value)} />
            <Button variant="primary">Search</Button>
          </form>
          <ol className="mt-4 space-y-2.5">
            {hits?.map((h, i) => (
              <li key={h.chunk_id} className="rounded-control border border-line p-3">
                <div className="flex items-center justify-between gap-2"><p className="text-sm font-medium">{i + 1}. {h.document_title}{h.heading && <span className="text-ink-mute"> / {h.heading}</span>}</p><Badge>{human(h.kind)}</Badge></div>
                <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink-mute">{h.text}</p>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] tabular text-ink-faint">
                  <span>fused {h.scores.rrf}</span><span>lexical {h.scores.lexical ?? "no match"}</span><span>semantic {h.scores.semantic ?? "–"}</span>
                </div>
              </li>
            ))}
            {hits && !hits.length && <li className="text-sm text-ink-mute">No approved, valid passages match.</li>}
          </ol>
        </Panel>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Add a knowledge document">
        <form ref={form} className="space-y-4" onSubmit={async (e) => {
          e.preventDefault(); setBusy(true); setErr(null);
          try { await post("/knowledge", new FormData(form.current!)); setOpen(false); mutate(); } catch (x) { setErr(x); } finally { setBusy(false); }
        }}>
          <Field label="Title"><input name="title" required className={inputCls} /></Field>
          <Field label="Type"><select name="kind" className={inputCls}>{["capability", "certification", "reference_project", "product", "standard_response", "policy", "previous_proposal"].map((k) => <option key={k} value={k}>{human(k)}</option>)}</select></Field>
          <Field label="Valid until" hint="For certificates. Expired documents are never retrieved."><input name="valid_until" type="date" className={inputCls} /></Field>
          <label className="flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" name="approved" value="true" /> Publish as approved (approvers and admins only)</label>
          <Field label="File" hint="Markdown, text, PDF or DOCX"><input name="file" type="file" required className="block text-sm" /></Field>
          <ErrorNote error={err} />
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button variant="primary" loading={busy}>Add document</Button></div>
        </form>
      </Modal>
    </>
  );
}
