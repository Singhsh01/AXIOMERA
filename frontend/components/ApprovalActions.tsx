"use client";
import { Lock } from "lucide-react";
import { useState } from "react";
import { can, useMe } from "@/components/me";
import { Button, ErrorNote, inputCls } from "@/components/ui/primitives";
import { post } from "@/lib/api";

const RANK: Record<string, number> = { viewer: 0, reviewer: 1, operator: 2, approver: 3, admin: 4 };

export function ApprovalActions({ approval, onDone }: { approval: any; onDone: () => void }) {
  const me = useMe();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [err, setErr] = useState<unknown>(null);
  if (!can(me, "approval.decide") || (RANK[me!.role] ?? 0) < (RANK[approval.required_role] ?? 9)) {
    const article = /^[aeiou]/i.test(approval.required_role ?? "") ? "an" : "a";
    return (
      <p className="flex items-start gap-2.5 border-l-[3px] border-ink/30 bg-raised/60 px-3 py-2.5 text-[13px] text-ink-soft">
        <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span>This decision needs {article} <strong className="font-semibold text-ink">{approval.required_role}</strong>. You are signed in as {me?.role ?? "…"}, so you can review it but not decide.</span>
      </p>
    );
  }
  async function decide(approve: boolean) {
    setBusy(approve ? "approve" : "reject"); setErr(null);
    try { await post(`/approvals/${approval.id}/decision`, { approve, note: note || null }); onDone(); }
    catch (e) { setErr(e); } finally { setBusy(null); }
  }
  return (
    <div className="space-y-2">
      <input aria-label="Decision note" placeholder="Note for the audit log (optional)" className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="flex gap-2">
        <Button size="sm" variant="success" loading={busy === "approve"} onClick={() => decide(true)}>Approve</Button>
        <Button size="sm" variant="danger" loading={busy === "reject"} onClick={() => decide(false)}>Reject</Button>
      </div>
      <ErrorNote error={err} />
    </div>
  );
}
