"use client";
import { Bell, BookOpen, Bot, Check, FileText, Gauge, Inbox, LogOut, Menu, PlugZap, Settings, ShieldCheck, Telescope, Workflow, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { MeCtx, type Me } from "@/components/me";
import { Logo } from "@/components/Logo";
import { Badge } from "@/components/ui/primitives";
import { post, useApi } from "@/lib/api";
import { ago, cn } from "@/lib/format";


const NAV = [
  { href: "/app", label: "Command center", icon: Gauge },
  { href: "/app/cases", label: "Cases", icon: Inbox },
  { href: "/app/approvals", label: "Approvals", icon: ShieldCheck },
  { href: "/app/rfps", label: "Proposals", icon: FileText },
  { href: "/app/workflows", label: "Workflows", icon: Workflow },
  { href: "/app/agents", label: "Agents", icon: Bot },
  { href: "/app/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/app/observability", label: "Observability", icon: Telescope },
  { href: "/app/integrations", label: "Integrations", icon: PlugZap },
  { href: "/app/settings", label: "Policies", icon: Settings },
];

function Notifications() {
  const { data, mutate } = useApi<any[]>("/notifications", { live: 8000 });
  const [open, setOpen] = useState(false);
  const unread = (data || []).filter((n) => !n.read).length;
  return (
    <div className="relative">
      <button aria-label={`Notifications, ${unread} unread`} onClick={() => setOpen(!open)} className="focus-ring relative rounded-lg p-2 text-ink-soft hover:bg-white/[0.06]">
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-cyan" />}
      </button>
      {open && (
        <div className="glass-strong absolute right-0 z-40 mt-2 w-[min(380px,90vw)] p-2">
          <div className="max-h-[420px] overflow-auto">
            {(data || []).slice(0, 15).map((n) => (
              <Link key={n.id} href={n.link || "#"} onClick={() => { setOpen(false); post(`/notifications/${n.id}/read`).then(() => mutate()); }}
                className={cn("block rounded-lg px-3 py-2.5 hover:bg-white/[0.05]", !n.read && "bg-white/[0.03]")}>
                <span className="flex items-center gap-2 text-sm font-medium">
                  <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", n.severity === "critical" ? "bg-bad" : n.severity === "warning" ? "bg-warn" : "bg-electric")} />
                  <span className="line-clamp-1">{n.title}</span>
                </span>
                <span className="mt-0.5 block pl-3.5 text-xs text-ink-mute">{n.body?.slice(0, 90)} {ago(n.created_at)}</span>
              </Link>
            ))}
            {!data?.length && <p className="p-3 text-sm text-ink-mute">Nothing yet. Notifications from workflows appear here.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { data: me } = useApi<Me>("/auth/me");
  const { data: health } = useApi<any>("/workflows", { live: 15000 });
  const [mobile, setMobile] = useState(false);
  const n8n = health?.n8n?.status;

  const nav = (
    <nav className="space-y-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/app" ? path === "/app" : path.startsWith(href);
        return (
          <Link key={href} href={href} onClick={() => setMobile(false)}
            className={cn("focus-ring flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] transition-colors",
              active ? "bg-gradient-to-r from-violet/20 to-transparent text-ink" : "text-ink-mute hover:bg-white/[0.04] hover:text-ink")}>
            <Icon className={cn("h-[17px] w-[17px]", active ? "text-cyan" : "")} aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <MeCtx.Provider value={me ?? null}>
      <div className="ambient min-h-screen">
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-line bg-abyss/70 px-3 py-5 backdrop-blur-xl lg:flex">
          <Link href="/" className="focus-ring mb-7 rounded-md px-2"><Logo /></Link>
          {nav}
          <div className="mt-auto space-y-3 px-2 text-xs text-ink-mute">
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full", n8n === "healthy" ? "bg-ok live-dot" : n8n ? "bg-bad" : "bg-ink-faint")} />
              n8n {n8n ?? "checking"}
            </div>
            {me && (
              <div className="flex items-center justify-between gap-2 border-t border-line pt-3">
                <div>
                  <p className="text-sm text-ink">{me.name}</p>
                  <p className="capitalize">{me.role} · {me.workspace.name}</p>
                </div>
                <button aria-label="Sign out" className="focus-ring rounded-md p-1.5 hover:bg-white/[0.06]" onClick={async () => { await post("/auth/logout"); router.push("/login"); }}>
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </aside>

        {mobile && (
          <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setMobile(false)}>
            <div className="glass-strong h-full w-72 rounded-none p-4" onClick={(e) => e.stopPropagation()}>
              <div className="mb-6 flex items-center justify-between"><Logo /><button aria-label="Close menu" onClick={() => setMobile(false)}><X className="h-5 w-5" /></button></div>
              {nav}
            </div>
          </div>
        )}

        <div className="lg:pl-60">
          <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-line bg-abyss/70 px-4 backdrop-blur-xl sm:px-6">
            <button aria-label="Open menu" className="focus-ring rounded-md p-1.5 lg:hidden" onClick={() => setMobile(true)}><Menu className="h-5 w-5" /></button>
            <div className="hidden items-center gap-2 text-sm text-ink-mute sm:flex">
              {me?.workspace.name}
              {me && <Badge t="violet" className="capitalize">{me.role}</Badge>}
            </div>
            <div className="flex items-center gap-1">
              <Link href="/app/approvals" className="focus-ring hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-ink-soft hover:bg-white/[0.06] sm:flex">
                <Check className="h-4 w-4" /> Approvals
              </Link>
              <Notifications />
            </div>
          </header>
          <main className="mx-auto max-w-[1500px] px-4 py-7 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </MeCtx.Provider>
  );
}
