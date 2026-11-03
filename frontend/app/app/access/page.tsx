"use client";
import { useState } from "react";
import { can, useMe } from "@/components/me";
import { Badge, Button, Empty, ErrorNote, PageHeader, Panel, PanelTitle, Skeleton, Stat, Tabs } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { ago, dt } from "@/lib/format";

const REASON: Record<string, [string, "ok" | "warn" | "bad" | "muted"]> = {
  ok: ["Signed in", "ok"],
  bad_password: ["Wrong password", "warn"],
  bad_password_locked: ["Wrong password, account locked", "bad"],
  locked: ["Refused: account locked", "bad"],
  unknown_user: ["Unknown e-mail", "muted"],
  inactive: ["Refused: account disabled", "bad"],
};

function agent(ua?: string | null) {
  if (!ua) return "—";
  const b = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : ua.split(" ")[0];
  const os = /Mac OS X/.test(ua) ? "macOS" : /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${b} on ${os}` : b;
}

function EventTable({ rows, showUser }: { rows: any[]; showUser?: boolean }) {
  if (!rows.length) return <Empty title="No sign-in attempts yet" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line text-left text-xs text-ink-mute">
          <th className="py-2 pr-4 font-medium">When</th>
          {showUser && <th className="py-2 pr-4 font-medium">Account</th>}
          <th className="py-2 pr-4 font-medium">Result</th>
          <th className="py-2 pr-4 font-medium">IP address</th>
          <th className="py-2 font-medium">Device</th>
        </tr></thead>
        <tbody>
          {rows.map((e) => {
            const [label, t] = REASON[e.reason] ?? [e.reason, "muted"];
            return (
              <tr key={e.id} className="border-b border-line/60 last:border-0">
                <td className="py-2.5 pr-4 tabular" title={dt(e.created_at)}>{ago(e.created_at)}</td>
                {showUser && <td className="py-2.5 pr-4"><span className="text-ink">{e.user_name ?? e.email}</span>{e.user_name && <span className="ml-2 text-xs text-ink-faint">{e.user_role}</span>}</td>}
                <td className="py-2.5 pr-4"><Badge t={t} dot>{label}</Badge></td>
                <td className="py-2.5 pr-4 font-mono text-[12.5px] text-ink-soft">{e.ip ?? "—"}</td>
                <td className="py-2.5 text-ink-soft">{agent(e.user_agent)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function AccessLog() {
  const me = useMe();
  const admin = can(me, "admin");
  const [tab, setTab] = useState<"mine" | "org">("mine");
  const [failedOnly, setFailedOnly] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const mine = useApi<any[]>("/auth/login-history?limit=100");
  const org = useApi<any>(admin && tab === "org" ? `/auth/login-history/all?limit=300${failedOnly ? "&success=false" : ""}` : null, { live: 15000 });
  const events: any[] = mine.data ?? [];
  const lastOk = events.find((e) => e.success);
  const prevOk = events.filter((e) => e.success)[1];
  const failed30 = events.filter((e) => !e.success && Date.now() - new Date(e.created_at).getTime() < 30 * 864e5).length;

  async function unlock(id: string) {
    setErr(null);
    try { await post(`/auth/users/${id}/unlock`); org.mutate(); } catch (e) { setErr(e); }
  }

  return (
    <>
      <PageHeader title="Access log" sub="Every sign-in attempt is recorded with its result, address and device. Five wrong passwords lock an account for 15 minutes; admins can lift a lock early, and that is written to the audit chain." />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Previous sign-in" value={prevOk ? ago(prevOk.created_at) : "—"} sub={prevOk ? `${agent(prevOk.user_agent)} · ${prevOk.ip ?? "unknown IP"}` : "This is your first recorded sign-in"} />
        <Stat label="This session started" value={lastOk ? ago(lastOk.created_at) : "—"} sub={lastOk ? dt(lastOk.created_at) : undefined} />
        <Stat label="Failed attempts on your account (30 days)" value={failed30} tone={failed30 ? "warn" : "ok"} sub={failed30 ? "If these were not you, change your password" : "None"} />
      </div>
      {admin && <div className="mb-4"><Tabs value={tab} onChange={setTab} items={[{ id: "mine", label: "My sign-ins" }, { id: "org", label: "Organisation" }]} /></div>}
      <ErrorNote error={err} />
      {tab === "mine" || !admin ? (
        <Panel><PanelTitle>Your sign-in history</PanelTitle>{mine.data ? <EventTable rows={events} /> : <Skeleton className="h-48" />}</Panel>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
          <Panel>
            <PanelTitle action={<label className="flex items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} /> Failed only</label>}>
              All sign-in attempts
            </PanelTitle>
            {org.data ? <EventTable rows={org.data.events} showUser /> : <Skeleton className="h-64" />}
          </Panel>
          <Panel className="h-fit">
            <PanelTitle>Locked accounts</PanelTitle>
            {!org.data ? <Skeleton className="h-20" /> : org.data.locked_accounts.length === 0 ? <p className="text-sm text-ink-mute">No account is locked.</p> : (
              <ul className="space-y-3">
                {org.data.locked_accounts.map((a: any) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 rounded-lg border border-line p-3">
                    <div className="min-w-0"><p className="truncate text-sm text-ink">{a.name}</p><p className="truncate text-xs text-ink-mute">{a.email} · until {new Date(a.locked_until).toLocaleTimeString()}</p></div>
                    <Button size="sm" variant="secondary" onClick={() => unlock(a.id)}>Unlock</Button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}
    </>
  );
}
