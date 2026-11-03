"use client";
import { AlertTriangle, Download, FileText } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, use, useEffect, useMemo, useState } from "react";
import { RunStrip } from "@/components/RunStrip";
import { can, useMe } from "@/components/me";
import { Badge, Button, DetailHeader, ErrorNote, Panel, PanelTitle, Skeleton, Status, Tabs, inputCls } from "@/components/ui/primitives";
import { patch, post, useApi } from "@/lib/api";
import { ago, cn, dt, human, until } from "@/lib/format";

const STATUSES = ["compliant", "partially_compliant", "non_compliant", "unverified"];

function SourceViewer({ rfp, req }: { rfp: any; req: any | null }) {
  const doc = rfp.documents[rfp.documents.length - 1];
  const [page, setPage] = useState(1);
  const { data: hl } = useApi<any>(req ? `/rfps/${rfp.id}/requirements/${req.id}/highlight` : null);
  useEffect(() => { if (req) setPage(req.page); }, [req]);
  if (!doc) return null;
  const isPdf = doc.mime === "application/pdf";
  return (
    <Panel className="p-3">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="flex min-w-0 items-center gap-2 text-sm"><FileText className="h-4 w-4 shrink-0 text-ink-mute" /><span className="truncate">{doc.filename}</span><Badge>v{doc.version}</Badge></p>
        <div className="flex items-center gap-1 text-sm">
          <Button size="sm" variant="ghost" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</Button>
          <span className="whitespace-nowrap tabular text-ink-mute">{page} / {doc.page_count}</span>
          <Button size="sm" variant="ghost" aria-label="Next page" disabled={page >= doc.page_count} onClick={() => setPage(page + 1)}>›</Button>
        </div>
      </div>
      {isPdf ? (
        <div className="relative overflow-hidden rounded-[2px] bg-white shadow-lift">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/api/v1/rfps/${rfp.id}/documents/${doc.id}/pages/${page}.png`} alt={`Page ${page} of ${doc.filename}`} className="w-full" />
          {hl?.page === page && hl.rects.map((r: any, i: number) => (
            <span key={i} className="absolute bg-accent/20 ring-2 ring-accent" style={{ left: `${r.x * 100 - 0.5}%`, top: `${r.y * 100 - 0.3}%`, width: `${r.w * 100 + 1}%`, height: `${r.h * 100 + 0.6}%` }} />
          ))}
        </div>
      ) : <p className="p-4 text-sm text-ink-mute">DOCX files are shown as extracted text; page references are logical pages.</p>}
      {doc.extraction_warnings?.length > 0 && <p className="mt-2 text-xs text-warn">{doc.extraction_warnings.join(" ")}</p>}
      <p className="mt-2 px-1 text-xs text-ink-faint">Extraction: {doc.extraction_method} · sha256 {doc.sha256.slice(0, 12)}…</p>
    </Panel>
  );
}

function Matrix({ rfp, onSelect, selected }: { rfp: any; onSelect: (r: any) => void; selected: any }) {
  const { data: reqs, mutate } = useApi<any[]>(`/rfps/${rfp.id}/requirements`, { live: 6000 });
  const [filter, setFilter] = useState<string>("all");
  const me = useMe();
  const [edit, setEdit] = useState<{ status: string; rationale: string } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const rows = (reqs ?? []).filter((r) => filter === "all" || (r.compliance?.status ?? "unverified") === filter || r.category === filter);
  const sel = reqs?.find((r) => r.id === selected?.id) ?? null;

  async function saveReview() {
    setErr(null);
    try { await patch(`/requirements/${sel.id}/compliance`, { status: edit!.status, rationale: edit!.rationale }); setEdit(null); mutate(); } catch (e) { setErr(e); }
  }

  return (
    <div className="grid gap-4 2xl:grid-cols-[1fr_380px]">
      <Panel className="p-0">
        <div className="flex flex-wrap gap-1.5 border-b border-line p-3">
          {["all", ...STATUSES, "technical", "commercial", "contractual", "submission"].map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={cn("focus-ring rounded-control px-2.5 py-1 text-xs", filter === f ? "bg-accent/20 text-ink" : "text-ink-mute hover:bg-ink/[0.05]")}>
              {human(f)}{STATUSES.includes(f) && reqs ? ` ${reqs.filter((r) => (r.compliance?.status ?? "unverified") === f).length}` : ""}
            </button>
          ))}
        </div>
        <div className="max-h-[640px] overflow-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="sticky top-0 bg-surface text-left text-[12px] text-ink-mute"><tr>{["ID", "Requirement", "Type", "Src", "Status"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => onSelect(r)} className={cn("cursor-pointer border-t border-line/60", sel?.id === r.id ? "bg-accent/10" : "hover:bg-ink/[0.03]")}>
                  <td className="whitespace-nowrap px-3 py-2.5 font-mono text-xs text-ink-mute">{r.code}</td>
                  <td className="px-3 py-2.5"><p className="line-clamp-2">{r.text}</p>{r.human_verified && <Badge t="accent" className="mt-1">corrected by a person</Badge>}</td>
                  <td className="px-3 py-2.5 text-xs"><p className={r.obligation === "mandatory" ? "text-ink" : "text-ink-mute"}>{r.obligation}</p><p className="text-ink-faint">{r.category}</p></td>
                  <td className="px-3 py-2.5 tabular text-xs text-ink-mute">p.{r.page}</td>
                  <td className="px-3 py-2.5"><Status value={r.compliance?.status ?? "unverified"} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!reqs && <Skeleton className="m-3 h-40" />}
        </div>
      </Panel>
      <Panel className="h-fit 2xl:sticky 2xl:top-20">
        {sel ? (
          <>
            <div className="flex items-center justify-between gap-2"><span className="font-mono text-sm text-ink-mute">{sel.code}</span><Status value={sel.compliance?.status} /></div>
            <p className="mt-2 text-[15px] leading-relaxed">{sel.text}</p>
            <p className="mt-2 text-xs text-ink-mute">Page {sel.page}{sel.section ? `, ${sel.section}` : ""} · chars {sel.char_start}–{sel.char_end} · confidence {sel.confidence} · {sel.extraction_method}</p>
            <div className="mt-4 rounded-control border border-line p-3 text-sm">
              <p className="text-ink-soft">{sel.compliance?.rationale}</p>
              {sel.compliance?.missing_info && <p className="mt-2 text-warn">Missing: {sel.compliance.missing_info}</p>}
              <p className="mt-2 text-xs text-ink-faint">Assessed by {sel.compliance?.assessed_by} · review {sel.compliance?.review_status}</p>
            </div>
            <p className="mb-2 mt-4 text-xs text-ink-mute">Evidence ({sel.compliance?.evidence?.length ?? 0})</p>
            <ul className="space-y-2">
              {sel.compliance?.evidence?.map((e: any) => (
                <li key={e.chunk_id} className="rounded-control border border-line p-3">
                  <p className="text-sm font-medium">{e.document}{e.heading && <span className="text-ink-mute"> / {e.heading}</span>}</p>
                  <p className="mt-1 line-clamp-4 text-xs leading-relaxed text-ink-mute">{e.excerpt}</p>
                  <p className="mt-1.5 text-[11px] text-ink-faint">coverage {Math.round(e.coverage * 100)}% · rrf {e.scores?.rrf} · lexical {e.scores?.lexical ?? "–"} · semantic {e.scores?.semantic ?? "–"}</p>
                </li>
              ))}
            </ul>
            {can(me, "rfp.review") && (
              <div className="mt-4 border-t border-line pt-4">
                {edit ? (
                  <div className="space-y-2">
                    <select aria-label="Compliance status" className={inputCls} value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>{STATUSES.map((s) => <option key={s} value={s}>{human(s)}</option>)}</select>
                    <textarea aria-label="Rationale" className={`${inputCls} min-h-20`} placeholder="Why (recorded in the audit log)" value={edit.rationale} onChange={(e) => setEdit({ ...edit, rationale: e.target.value })} />
                    <ErrorNote error={err} />
                    <div className="flex gap-2"><Button size="sm" variant="primary" onClick={saveReview}>Save review</Button><Button size="sm" variant="ghost" onClick={() => setEdit(null)}>Cancel</Button></div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button size="sm" variant="success" onClick={async () => { await post(`/requirements/${sel.id}/compliance/accept`); mutate(); }}>Accept assessment</Button>
                    <Button size="sm" onClick={() => setEdit({ status: sel.compliance?.status ?? "unverified", rationale: "" })}>Change status</Button>
                  </div>
                )}
              </div>
            )}
          </>
        ) : <p className="text-sm text-ink-mute">Select a requirement to see its source, evidence and assessment.</p>}
      </Panel>
    </div>
  );
}

function ProposalEditor({ rfp }: { rfp: any }) {
  const [pid, setPid] = useState<string | null>(rfp.proposals[0]?.id ?? null);
  const { data: p, mutate } = useApi<any>(pid ? `/proposals/${pid}` : null, { live: 8000 });
  const [diffAgainst, setDiffAgainst] = useState<string>("");
  const { data: diff } = useApi<any>(pid && diffAgainst ? `/proposals/${pid}/diff?against=${diffAgainst}` : null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [comment, setComment] = useState<Record<string, string>>({});
  const me = useMe();
  if (!pid) return <p className="text-ink-mute">No proposal yet. It is generated after the compliance matrix is assessed.</p>;
  if (!p) return <Skeleton className="h-96" />;
  const locked = ["approved", "exported"].includes(p.status);

  async function act(key: string, fn: () => Promise<any>) {
    setBusy(key); setErr(null);
    try { await fn(); await mutate(); } catch (e) { setErr(e); } finally { setBusy(null); }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        {p.sections.map((s: any, i: number) => (
          <Panel key={s.key} id={`sec-${s.key}`}>
            <PanelTitle hint={s.edited_at ? `Edited ${ago(s.edited_at)}` : `Generated by ${p.generator.provider}/${p.generator.model}`}>{i + 1}. {s.title}</PanelTitle>
            {s.unsupported_claims?.length > 0 && (
              <div className="mb-3 flex gap-2 rounded-control border border-warn/30 bg-warn/10 p-3 text-sm">
                <AlertTriangle className="h-4 w-4 shrink-0 text-warn" />
                <div><p className="text-warn">{s.unsupported_claims.length} claim(s) not supported by cited evidence{s.edited_at ? " (flagged in your edit)" : " were removed"}</p>
                  <ul className="mt-1 text-xs text-ink-soft">{s.unsupported_claims.map((u: any, j: number) => <li key={j}>{u.claims.join(", ")}: “{u.sentence.slice(0, 120)}”</li>)}</ul></div>
              </div>
            )}
            <textarea aria-label={`${s.title} content`} disabled={locked || !can(me, "rfp.edit")} className={`${inputCls} min-h-36 font-sans leading-relaxed`}
              value={drafts[s.key] ?? s.content} onChange={(e) => setDrafts({ ...drafts, [s.key]: e.target.value })} />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-1.5">{s.citations?.filter((c: any) => c.ref).map((c: any) => <Badge key={c.ref + c.chunk_id} t="accent"><span title={c.excerpt}>[{c.ref}] {c.document}</span></Badge>)}</div>
              {drafts[s.key] !== undefined && drafts[s.key] !== s.content && (
                <Button size="sm" variant="primary" loading={busy === s.key} onClick={() => act(s.key, async () => { await patch(`/proposals/${p.id}/sections/${s.key}`, { content: drafts[s.key] }); setDrafts({ ...drafts, [s.key]: undefined as any }); })}>Save section</Button>
              )}
            </div>
            <div className="mt-3 space-y-1.5 border-t border-line pt-3">
              {p.comments.filter((c: any) => c.section_key === s.key).map((c: any) => <p key={c.id} className="text-sm"><span className="font-medium">{c.author_name}</span> <span className="text-ink-faint">{ago(c.created_at)}</span><br /><span className="text-ink-soft">{c.body}</span></p>)}
              <div className="flex gap-2">
                <input aria-label="Add review comment" placeholder="Add a review comment" className={inputCls} value={comment[s.key] ?? ""} onChange={(e) => setComment({ ...comment, [s.key]: e.target.value })} />
                <Button size="sm" disabled={!comment[s.key]} onClick={() => act(`c-${s.key}`, async () => { await post(`/proposals/${p.id}/comments`, { section_key: s.key, body: comment[s.key] }); setComment({ ...comment, [s.key]: "" }); })}>Comment</Button>
              </div>
            </div>
          </Panel>
        ))}
        {diff && (
          <Panel>
            <PanelTitle>Changes from v{diff.from} to v{diff.to}</PanelTitle>
            {diff.sections.filter((s: any) => s.changed).map((s: any) => (
              <div key={s.key} className="mb-4"><p className="mb-1 font-medium">{s.title}</p>
                <p className="text-sm leading-relaxed">{s.ops.map((o: any, i: number) => o.op === "equal" ? <span key={i} className="text-ink-mute">{o.new} </span> : <span key={i}>{o.old && <del className="bg-bad/15 text-bad">{o.old} </del>}{o.new && <ins className="bg-ok/15 text-ok no-underline">{o.new} </ins>}</span>)}</p></div>
            ))}
            {!diff.sections.some((s: any) => s.changed) && <p className="text-sm text-ink-mute">No differences.</p>}
          </Panel>
        )}
      </div>
      <div className="space-y-4 xl:sticky xl:top-20 xl:h-fit">
        <Panel>
          <div className="flex items-center justify-between"><p className="font-display text-lg font-semibold">Version {p.version}</p><Status value={p.status} /></div>
          <select aria-label="Proposal version" className={`${inputCls} mt-3`} value={pid} onChange={(e) => setPid(e.target.value)}>
            {rfp.proposals.map((x: any) => <option key={x.id} value={x.id}>v{x.version} · {x.status}</option>)}
          </select>
          <p className="mt-3 text-xs text-ink-mute">{p.generator.unsupported_claims_removed} unsupported claim(s) removed at generation · prompt {p.generator.prompt_version}</p>
          {p.review_note && <p className="mt-2 text-sm text-ink-soft">Review note: “{p.review_note}”</p>}
          <ErrorNote error={err} />
          <div className="mt-4 space-y-2">
            {["draft", "changes_requested"].includes(p.status) && can(me, "rfp.write") && <Button className="w-full" loading={busy === "rr"} onClick={() => act("rr", () => post(`/proposals/${p.id}/request-review`))}>Request review</Button>}
            {p.status === "in_review" && can(me, "rfp.review") && (
              <div className="flex gap-2">
                <Button className="flex-1" variant="success" loading={busy === "ap"} onClick={() => act("ap", () => post(`/proposals/${p.id}/review`, { approve: true }))}>Approve</Button>
                <Button className="flex-1" variant="danger" loading={busy === "rj"} onClick={() => act("rj", () => post(`/proposals/${p.id}/review`, { approve: false, note: "Changes requested" }))}>Request changes</Button>
              </div>
            )}
            {locked && can(me, "rfp.edit") && <Button className="w-full" variant="ghost" onClick={() => act("nv", async () => { const r = await post(`/rfps/${rfp.id}/proposals/${p.id}/new-version`); setPid(r.id); })}>Start a new version</Button>}
          </div>
        </Panel>
        <Panel>
          <PanelTitle hint={locked ? "Approved: final exports available" : "Drafts are watermarked until approved"}>Export</PanelTitle>
          <div className="grid grid-cols-2 gap-2">
            {(["docx", "pdf"] as const).map((f) => (
              <Button key={f} size="sm" loading={busy === `x-${f}`} onClick={() => act(`x-${f}`, async () => {
                const r = await post(`/proposals/${p.id}/export?format=${f}&final=${locked}`); window.open(r.download, "_blank");
              })}><Download className="h-3.5 w-3.5" />{f.toUpperCase()}{locked ? "" : " draft"}</Button>
            ))}
          </div>
          <ul className="mt-3 space-y-1 text-xs text-ink-mute">
            {p.exports.slice(0, 5).map((x: any) => <li key={x.id}><a className="hover:text-signal" href={`/api/v1/exports/${x.id}/download`}>{x.format.toUpperCase()} {x.final ? "final" : "draft"}, {dt(x.created_at)}</a> <a className="text-ink-faint hover:text-signal" href={`/api/v1/exports/${x.id}/manifest`} target="_blank">manifest</a></li>)}
          </ul>
        </Panel>
        {rfp.proposals.length > 1 && (
          <Panel>
            <PanelTitle>Compare versions</PanelTitle>
            <select aria-label="Compare against" className={inputCls} value={diffAgainst} onChange={(e) => setDiffAgainst(e.target.value)}>
              <option value="">Choose a version</option>
              {rfp.proposals.filter((x: any) => x.id !== pid).map((x: any) => <option key={x.id} value={x.id}>v{x.version}</option>)}
            </select>
          </Panel>
        )}
      </div>
    </div>
  );
}

function Workspace({ id }: { id: string }) {
  const tabParam = useSearchParams().get("tab");
  const { data: rfp } = useApi<any>(`/rfps/${id}`, { live: 5000 });
  const [tab, setTab] = useState<"matrix" | "proposal" | "pipeline">(tabParam === "proposal" ? "proposal" : "matrix");
  const [sel, setSel] = useState<any>(null);
  const deadlines = useMemo(() => rfp?.deadlines ?? [], [rfp]);
  if (!rfp) return <Skeleton className="h-[600px]" />;
  return (
    <>
      <DetailHeader crumb={rfp.reference || "Tender"} title={rfp.title} meta={<Status value={rfp.status} />} />
      {/* Title block, as on a drawing sheet: who, what, and the dates that matter. */}
      <dl className="mb-10 grid grid-cols-2 border-l border-t border-line md:grid-cols-4 xl:grid-cols-7">
        {[["Issuer", rfp.issuer], ["Reference", rfp.reference || "—"], ["Requirements", rfp.requirements]].map(([k, v]) => (
          <div key={k as string} className="border-b border-r border-line px-4 py-3"><dt className="label">{k}</dt><dd className="mt-1.5 truncate text-[14px] font-semibold">{v as any}</dd></div>
        ))}
        {deadlines.map((d: any) => (
          <div key={d.kind + d.at} className={cn("relative border-b border-r border-line px-4 py-3", d.kind === "submission" && "bg-raised")}>
            {d.kind === "submission" && <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" aria-hidden />}
            <dt className="label">{human(d.kind)} · p.{d.page}</dt>
            <dd className="mt-1.5 text-[14px] font-semibold tabular">{dt(d.at)}</dd>
            <dd className="font-mono text-[10.5px] text-ink-mute">{until(d.at)}</dd>
          </div>
        ))}
      </dl>
      {rfp.security_flags?.length > 0 && (
        <div role="alert" className="mb-6 flex gap-3 border-l-[3px] border-warn bg-warn/[0.07] p-4 text-sm">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warn" />
          <div><p className="font-medium text-warn">The document contains text addressed to automated reviewers. It was excluded from the requirements.</p>
            <ul className="mt-1 text-ink-soft">{rfp.security_flags.map((f: any, i: number) => <li key={i}>Page {f.page}: “{f.excerpt}”</li>)}</ul></div>
        </div>
      )}
      <Tabs value={tab} onChange={setTab} items={[{ id: "matrix", label: "Requirements & compliance" }, { id: "proposal", label: "Proposal", count: rfp.proposals.length }, { id: "pipeline", label: "Pipeline runs", count: rfp.workflow_runs.length }]} />
      <div className="mt-8">
        {tab === "matrix" && (
          <div className="grid gap-8 xl:grid-cols-[minmax(340px,0.85fr)_1.6fr]">
            <div className="xl:sticky xl:top-24 xl:h-fit"><SourceViewer rfp={rfp} req={sel} /></div>
            <Matrix rfp={rfp} onSelect={setSel} selected={sel} />
          </div>
        )}
        {tab === "proposal" && <ProposalEditor rfp={rfp} />}
        {tab === "pipeline" && (
          <Panel>
            <PanelTitle hint="n8n Workflow C stages for this tender, plus the agent runs they triggered">Pipeline</PanelTitle>
            {rfp.workflow_runs.map((w: any) => <RunStrip key={w.id} run={{ ...w, step_count: w.steps.length, retries: w.steps.filter((s: any) => s.attempt > 1).length }} />)}
            <ul className="mt-4 divide-y divide-line text-sm">
              {rfp.agent_runs.map((a: any) => <li key={a.id} className="flex items-center justify-between gap-3 py-2"><span><span className="font-medium">{a.agent}</span> <span className="text-ink-mute">{a.reasoning_summary}</span></span><Status value={a.status} /></li>)}
            </ul>
          </Panel>
        )}
      </div>
    </>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Suspense><Workspace id={id} /></Suspense>;
}
