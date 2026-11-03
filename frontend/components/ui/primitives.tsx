"use client";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/format";

/* Button — shadcn/ui-style variant API */
const buttonStyles = cva(
  "focus-ring inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        primary: "bg-gradient-to-b from-[#7D6EEA] to-violet-deep text-white shadow-[0_8px_24px_-8px_rgba(106,90,224,0.4)] hover:from-[#8A7CF0]",
        secondary: "border border-line bg-ink/[0.04] text-ink hover:bg-ink/[0.08]",
        ghost: "text-ink-soft hover:bg-ink/[0.06] hover:text-ink",
        danger: "border border-bad/30 bg-bad/10 text-bad hover:bg-bad/20",
        success: "border border-ok/30 bg-ok/10 text-ok hover:bg-ok/20",
      },
      size: { sm: "h-8 px-3 text-[13px]", md: "h-9 px-4", lg: "h-11 px-5 text-[15px]", icon: "h-8 w-8" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export function Button({ className, variant, size, loading, children, ...props }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonStyles> & { loading?: boolean }) {
  return (
    <button className={cn(buttonStyles({ variant, size }), className)} disabled={loading || props.disabled} {...props}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Panel({ className, children, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("glass p-5", className)} {...p}>{children}</section>;
}

export function PanelTitle({ children, action, hint }: { children: React.ReactNode; action?: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="font-display text-[17px] font-semibold tracking-[-0.01em] text-ink">{children}</h2>
        {hint && <p className="mt-0.5 text-[13px] text-ink-mute">{hint}</p>}
      </div>
      {action && <div className="shrink-0 whitespace-nowrap">{action}</div>}
    </div>
  );
}

const tone: Record<string, string> = {
  ok: "border-ok/25 bg-ok/10 text-ok",
  warn: "border-warn/25 bg-warn/10 text-warn",
  bad: "border-bad/25 bg-bad/10 text-bad",
  info: "border-electric/30 bg-electric/10 text-electric",
  violet: "border-violet/30 bg-violet/10 text-violet-deep",
  muted: "border-line bg-ink/[0.03] text-ink-mute",
  cyan: "border-cyan/25 bg-cyan/10 text-cyan",
};

export function Badge({ children, t = "muted", className, dot }: { children: React.ReactNode; t?: keyof typeof tone; className?: string; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[12px] font-medium leading-4", tone[t], className)}>
      {dot && <span className="live-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, keyof typeof tone> = {
  succeeded: "ok", verified: "ok", resolved: "ok", closed: "muted", approved: "ok", executed: "ok", compliant: "ok", healthy: "ok", accepted: "ok", exported: "ok",
  running: "info", investigating: "info", triaged: "info", extracting: "info", action_in_progress: "info", in_review: "violet", drafted: "violet", matrix_ready: "violet", analyzed: "violet", extracted: "violet",
  waiting: "warn", pending: "warn", pending_approval: "warn", awaiting_approval: "warn", partially_compliant: "warn", degraded: "warn", needs_review: "warn", waiting_customer: "warn", changes_requested: "warn", cancel_requested: "warn",
  failed: "bad", rejected: "bad", non_compliant: "bad", escalated: "bad", down: "bad", expired: "bad", budget_exceeded: "bad", cancelled: "muted",
  unverified: "muted", new: "cyan", received: "cyan", proposed: "cyan", simulator: "cyan", live: "ok", fixture: "muted", deterministic: "muted",
};

export function Status({ value, className }: { value?: string | null; className?: string }) {
  if (!value) return <Badge>—</Badge>;
  const t = STATUS_TONE[value] ?? "muted";
  return <Badge t={t} dot={["running", "waiting", "pending"].includes(value)} className={className}>{value.replace(/_/g, " ")}</Badge>;
}

export function Priority({ p }: { p?: string | null }) {
  const t = p === "P1" ? "bad" : p === "P2" ? "warn" : p === "P3" ? "info" : "muted";
  return <Badge t={t} className="tabular font-semibold">{p ?? "—"}</Badge>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-panel border border-dashed border-line px-5 py-8">
      <p className="font-medium text-ink">{title}</p>
      {body && <p className="max-w-prose text-sm text-ink-mute">{body}</p>}
      {action && <div className="shrink-0 whitespace-nowrap">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: any }) {
  if (!error) return null;
  return <p role="alert" className="rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">{String(error.message ?? error)}</p>;
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[13px] font-medium text-ink-soft">{label}</span>
      {children}
      {hint && <span className="block text-xs text-ink-mute">{hint}</span>}
    </label>
  );
}

export const inputCls = "focus-ring w-full rounded-lg border border-line bg-abyss/60 px-3 py-2 text-sm text-ink placeholder:text-ink-faint";

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: string; count?: number }[] }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={value === it.id} onClick={() => onChange(it.id)}
          className={cn("focus-ring relative -mb-px whitespace-nowrap px-3 py-2.5 text-sm transition-colors",
            value === it.id ? "text-ink" : "text-ink-mute hover:text-ink-soft")}>
          {it.label}{it.count !== undefined && <span className="ml-1.5 tabular text-ink-faint">{it.count}</span>}
          {value === it.id && <span className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-gradient-to-r from-violet to-cyan" />}
        </button>
      ))}
    </div>
  );
}

export function Stat({ label, value, sub, tone: t }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className="glass px-4 py-3.5">
      <p className="text-[13px] text-ink-mute">{label}</p>
      <p className={cn("mt-1 font-display text-[28px] font-semibold tabular tracking-tight",
        t === "bad" ? "text-bad" : t === "warn" ? "text-warn" : t === "ok" ? "text-ok" : "text-ink")}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-mute">{sub}</p>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }) {
  React.useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 p-4 backdrop-blur-sm sm:items-center" onClick={onClose}>
      <div role="dialog" aria-modal aria-label={title} onClick={(e) => e.stopPropagation()}
        className={cn("glass-strong max-h-[90vh] w-full overflow-auto p-6", wide ? "max-w-3xl" : "max-w-lg")}>
        <h2 className="mb-4 font-display text-xl font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="h-display text-[34px] font-semibold sm:text-[40px]">{title}</h1>
        {sub && <p className="mt-2 max-w-2xl text-[15px] text-ink-mute">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return (
    <pre className={cn("max-h-80 min-w-0 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-abyss/70 p-3 font-mono text-[12px] leading-5 text-ink-soft", className)}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
