"use client";
import { Bell, Check, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { MeCtx, type Me } from "@/components/me";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/theme";
import { post, useApi } from "@/lib/api";
import { ago, cn } from "@/lib/format";
import { NAV } from "@/lib/nav";

function Notifications() {
  const { data, mutate } = useApi<any[]>("/notifications", { live: 8000 });
  const [open, setOpen] = useState(false);
  const unread = (data || []).filter((n) => !n.read).length;
  return (
    <div className="relative">
      <button aria-label={`Notifications, ${unread} unread`} onClick={() => setOpen(!open)} className="focus-ring relative inline-flex h-8 w-8 items-center justify-center rounded-control text-ink-soft hover:bg-raised hover:text-ink">
        <Bell className="h-4 w-4" />
        {unread > 0 && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal" />}
      </button>
      {open && (
        <div className="plate-raised page-enter absolute right-0 z-40 mt-2 w-[min(400px,90vw)] p-2">
          <p className="label px-3 pb-2 pt-2">Notifications</p>
          <div className="max-h-[420px] overflow-auto">
            {(data || []).slice(0, 15).map((n) => (
              <Link key={n.id} href={n.link || "#"} onClick={() => { setOpen(false); post(`/notifications/${n.id}/read`).then(() => mutate()); }}
                className={cn("block border-t border-line px-3 py-3 hover:bg-raised", !n.read && "bg-raised/50")}>
                <span className="flex items-center gap-2 text-sm font-medium">
                  <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", n.severity === "critical" ? "bg-bad" : n.severity === "warning" ? "bg-warn" : "bg-info")} />
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
  const groups = Array.from(new Set(NAV.map((n) => n.group)));

  const nav = (
    <nav className="space-y-7">
      {groups.map((g) => (
        <div key={g}>
          <p className="label mb-2 px-3 text-ink-faint">{g}</p>
          <ul className="space-y-px">
            {NAV.map((n, i) => ({ ...n, i })).filter((n) => n.group === g).map(({ href, label, icon: Icon, i }) => {
              const active = href === "/app" ? path === "/app" : path.startsWith(href);
              return (
                <li key={href}>
                  <Link href={href} onClick={() => setMobile(false)} aria-current={active ? "page" : undefined}
                    className={cn("focus-ring group relative flex items-center gap-3 px-3 py-[7px] text-[13.5px] transition-colors duration-200",
                      active ? "bg-raised text-ink" : "text-ink-mute hover:bg-raised/60 hover:text-ink")}>
                    <span className={cn("absolute inset-y-1 left-0 w-[2px] bg-ink transition-transform duration-300 ease-arch", active ? "scale-y-100" : "scale-y-0")} aria-hidden />
                    <span className="w-5 font-mono text-[10.5px] tabular text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
                    <Icon className={cn("h-[15px] w-[15px]", active ? "text-accent" : "")} aria-hidden />
                    <span className={active ? "font-semibold" : ""}>{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  const signOut = async () => { await post("/auth/logout"); router.push("/login"); };

  return (
    <MeCtx.Provider value={me ?? null}>
      <div className="min-h-screen bg-page">
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-line bg-surface lg:flex">
          <Link href="/" className="focus-ring flex h-16 items-center border-b border-line px-6"><Logo /></Link>
          <div className="flex-1 overflow-y-auto px-3 py-6">{nav}</div>
          <div className="space-y-4 border-t border-line px-6 py-5 text-xs text-ink-mute">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className={cn("h-1.5 w-1.5 rounded-full", n8n === "healthy" ? "bg-ok live-dot" : n8n ? "bg-bad" : "bg-ink-faint")} />
                <span className="label normal-case tracking-normal">n8n {n8n ?? "checking"}</span>
              </span>
              <ThemeToggle />
            </div>
            {me && (
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-semibold text-ink">{me.name}</p>
                  <p className="truncate capitalize">{me.role} · {me.workspace.name}</p>
                </div>
                <button aria-label="Sign out" className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-control hover:bg-raised hover:text-ink" onClick={signOut}>
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </aside>

        {mobile && (
          <div className="fixed inset-0 z-40 bg-ink/25 lg:hidden" onClick={() => setMobile(false)}>
            <div className="page-enter flex h-full w-72 flex-col border-r border-line bg-surface" onClick={(e) => e.stopPropagation()}>
              <div className="flex h-16 items-center justify-between border-b border-line px-5"><Logo />
                <button aria-label="Close menu" className="focus-ring p-1" onClick={() => setMobile(false)}><X className="h-5 w-5" /></button></div>
              <div className="flex-1 overflow-y-auto px-3 py-6">{nav}</div>
              {me && <div className="flex items-center justify-between border-t border-line px-5 py-4 text-xs text-ink-mute">
                <span className="truncate">{me.name} · <span className="capitalize">{me.role}</span></span>
                <button aria-label="Sign out" className="focus-ring p-1" onClick={signOut}><LogOut className="h-4 w-4" /></button></div>}
            </div>
          </div>
        )}

        <div className="lg:pl-64">
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-line bg-page/85 px-4 backdrop-blur-md sm:px-8">
            <div className="flex items-center gap-3">
              <button aria-label="Open menu" className="focus-ring p-1.5 lg:hidden" onClick={() => setMobile(true)}><Menu className="h-5 w-5" /></button>
              <span className="lg:hidden"><Logo compact /></span>
              <p className="label hidden items-center gap-3 sm:flex">
                <span className="text-ink">{me?.workspace.name ?? "…"}</span>
                <span className="h-px w-5 bg-ink/30" aria-hidden />
                <span>{me?.role ?? ""}</span>
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Link href="/app/approvals" className="focus-ring hidden h-8 items-center gap-1.5 rounded-control px-3 text-[13px] font-medium text-ink-soft hover:bg-raised hover:text-ink sm:flex">
                <Check className="h-4 w-4" /> Approvals
              </Link>
              <span className="lg:hidden"><ThemeToggle /></span>
              <Notifications />
            </div>
          </header>
          <main className="mx-auto max-w-[1480px] px-4 py-10 sm:px-8 lg:px-12">{children}</main>
        </div>
      </div>
    </MeCtx.Provider>
  );
}
