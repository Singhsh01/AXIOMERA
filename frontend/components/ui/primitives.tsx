"use client";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { cn } from "@/lib/format";
import { sectionFor } from "@/lib/nav";

/* ------------------------------------------------------------------ Button (shadcn-style variant API) */
const buttonStyles = cva(
  "focus-ring inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control text-[13px] font-semibold tracking-[0.01em] transition-[background-color,color,border-color,transform] duration-200 ease-arch active:translate-y-px disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-fg hover:bg-primary/85",
        secondary: "border border-line bg-surface text-ink hover:border-ink/40",
        ghost: "text-ink-soft hover:bg-raised hover:text-ink",
        danger: "border border-bad/35 text-bad hover:bg-bad/10",
        success: "border border-ok/35 text-ok hover:bg-ok/10",
      },
      size: { sm: "h-8 px-3", md: "h-9 px-4", lg: "h-12 px-6 text-[12px] uppercase tracking-label", icon: "h-8 w-8" },
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

/* ------------------------------------------------------------------ Surfaces */
export function Panel({ className, children, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("plate p-6", className)} {...p}>{children}</section>;
}

/** Panel heading: a small mono index or label above a quiet title. */
export function PanelTitle({ children, action, hint, label }: { children: React.ReactNode; action?: React.ReactNode; hint?: React.ReactNode; label?: string }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-3">
      <div>
        {label && <p className="label mb-1.5">{label}</p>}
        <h2 className="font-display text-[16px] font-semibold tracking-[-0.01em] text-ink">{children}</h2>
        {hint && <p className="mt-1 text-[13px] leading-relaxed text-ink-mute">{hint}</p>}
      </div>
      {action && <div className="shrink-0 whitespace-nowrap text-[13px]">{action}</div>}
    </div>
  );
}

/** A page section without a box: lettered index, title, hint, action, closed by a hairline. */
export function Section({ index, title, hint, action, children, className }: {
  index?: string; title: React.ReactNode; hint?: React.ReactNode; action?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={cn("min-w-0", className)}>
      <div className="mb-5 flex items-end justify-between gap-4 border-b border-line pb-3">
        <div className="min-w-0">
          <h2 className="flex items-baseline gap-3 font-display text-[17px] font-bold tracking-[-0.015em] text-ink">
            {index && <span className="font-mono text-[11px] font-medium text-accent">{index}</span>}{title}
          </h2>
          {hint && <p className="mt-1 text-[13px] text-ink-mute">{hint}</p>}
        </div>
        {action && <div className="shrink-0 whitespace-nowrap text-[13px]">{action}</div>}
      </div>
      {children}
    </section>
  );
}

/** Text link with an arrow, used for "see all" actions. */
export function More({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className="focus-ring group inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-label text-ink-soft hover:text-ink">
    {children}<span aria-hidden className="transition-transform duration-300 ease-arch group-hover:translate-x-1">→</span></Link>;
}

/* ------------------------------------------------------------------ Badges & status */
const tone: Record<string, string> = {
  ok: "border-ok/30 text-ok",
  warn: "border-warn/35 text-warn",
  bad: "border-bad/35 text-bad",
  info: "border-info/30 text-info",
  accent: "border-accent/35 text-accent",
  muted: "border-line text-ink-mute",
  signal: "border-signal/30 text-signal",
};

export function Badge({ children, t = "muted", className, dot }: { children: React.ReactNode; t?: keyof typeof tone; className?: string; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-[2px] border bg-surface/60 px-1.5 py-[3px] font-mono text-[10.5px] font-medium uppercase leading-none tracking-[0.06em]", tone[t], className)}>
      {dot && <span className="live-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, keyof typeof tone> = {
  succeeded: "ok", verified: "ok", resolved: "ok", closed: "muted", approved: "ok", executed: "ok", compliant: "ok", healthy: "ok", accepted: "ok", exported: "ok",
  running: "info", investigating: "info", triaged: "info", extracting: "info", action_in_progress: "info", in_review: "accent", drafted: "accent", matrix_ready: "accent", analyzed: "accent", extracted: "accent",
  waiting: "warn", pending: "warn", pending_approval: "warn", awaiting_approval: "warn", partially_compliant: "warn", degraded: "warn", needs_review: "warn", waiting_customer: "warn", changes_requested: "warn", cancel_requested: "warn",
  failed: "bad", rejected: "bad", non_compliant: "bad", escalated: "bad", down: "bad", expired: "bad", budget_exceeded: "bad", cancelled: "muted",
  unverified: "muted", new: "signal", received: "signal", proposed: "signal", simulator: "signal", live: "ok", fixture: "muted", deterministic: "muted",
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

/* ------------------------------------------------------------------ States */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 border-l-[3px] border-ink/15 py-6 pl-5">
      <p className="label">Nothing here</p>
      <p className="font-display text-[17px] font-semibold text-ink">{title}</p>
      {body && <p className="max-w-prose text-sm leading-relaxed text-ink-mute">{body}</p>}
      {action && <div className="mt-1 shrink-0 whitespace-nowrap">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: any }) {
  if (!error) return null;
  return <p role="alert" className="border-l-[3px] border-bad bg-bad/[0.06] px-3 py-2 text-sm text-bad">{String(error.message ?? error)}</p>;
}

/* ------------------------------------------------------------------ Forms */
export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="label block text-ink-soft">{label}</span>
      {children}
      {hint && <span className="block text-xs text-ink-mute">{hint}</span>}
    </label>
  );
}

export const inputCls = "focus-ring w-full rounded-control border border-line bg-surface px-3 py-2.5 text-sm text-ink transition-colors placeholder:text-ink-faint hover:border-ink/30 focus:border-ink/50";

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: string; count?: number }[] }) {
  return (
    <div role="tablist" className="flex gap-6 overflow-x-auto border-b border-line">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={value === it.id} onClick={() => onChange(it.id)}
          className={cn("focus-ring relative -mb-px whitespace-nowrap pb-3 pt-1 text-[13px] font-medium transition-colors",
            value === it.id ? "text-ink" : "text-ink-mute hover:text-ink")}>
          {it.label}{it.count !== undefined && <span className="ml-1.5 font-mono text-[11px] tabular text-ink-faint">{it.count}</span>}
          <span className={cn("absolute inset-x-0 -bottom-px h-[2px] origin-left bg-ink transition-transform duration-300 ease-arch", value === it.id ? "scale-x-100" : "scale-x-0")} />
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Metrics */
/** One figure in a metric strip: annotation label, large numeral, footnote. Separated by hairlines, not boxes. */
export function Stat({ label, value, sub, tone: t }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className="border-l border-line py-1 pl-5">
      <p className="label">{label}</p>
      <p className={cn("mt-3 font-display text-[40px] font-semibold leading-none tabular tracking-[-0.04em]",
        t === "bad" ? "text-bad" : t === "warn" ? "text-warn" : t === "ok" ? "text-ok" : "text-ink")}>{value}</p>
      {sub && <p className="mt-2.5 text-[12.5px] leading-snug text-ink-mute">{sub}</p>}
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
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/25 p-4 backdrop-blur-[3px] sm:items-center" onClick={onClose}>
      <div role="dialog" aria-modal aria-label={title} onClick={(e) => e.stopPropagation()}
        className={cn("plate-raised page-enter max-h-[90vh] w-full overflow-auto p-7", wide ? "max-w-3xl" : "max-w-lg")}>
        <span className="marker mb-5" />
        <h2 className="mb-5 font-display text-[22px] font-bold tracking-[-0.02em]">{title}</h2>
        {children}
      </div>
    </div>
  );
}

/** Editorial page header: section number and name, display title, standfirst, actions; closed by a rule. */
export function PageHeader({ title, sub, actions, eyebrow }: { title: string; sub?: React.ReactNode; actions?: React.ReactNode; eyebrow?: string }) {
  const s = sectionFor(usePathname() ?? "");
  return (
    <header className="page-enter mb-9 border-b border-line pb-7">
      <p className="label mb-5 flex items-center gap-3">
        <span className="text-ink">{s?.index ?? "—"}</span>
        <span className="h-px w-8 bg-ink/30" aria-hidden />
        <span>{eyebrow ?? (s ? `${s.group} · ${s.label}` : "")}</span>
      </p>
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <h1 className="h-display text-[36px] sm:text-[48px]">{title}</h1>
          {sub && <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-mute">{sub}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  );
}

/** Header for a single record: numbered breadcrumb back to its section, display title, metadata, actions. */
export function DetailHeader({ crumb, title, prefix, meta, actions }: { crumb: string; title: React.ReactNode; prefix?: React.ReactNode; meta?: React.ReactNode; actions?: React.ReactNode }) {
  const s = sectionFor(usePathname() ?? "");
  return (
    <header className="page-enter mb-8 border-b border-line pb-7">
      <p className="label mb-5 flex items-center gap-3">
        <span className="text-ink">{s?.index}</span><span className="h-px w-8 bg-ink/30" aria-hidden />
        <Link href={s?.href ?? "/app"} className="hover:text-ink">{s?.label}</Link><span aria-hidden>/</span><span className="truncate">{crumb}</span>
      </p>
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <h1 className="h-display text-[32px] sm:text-[44px]">{prefix && <span className="mr-3 font-mono text-[0.55em] font-medium tracking-normal text-ink-faint">{prefix}</span>}{title}</h1>
          {meta && <div className="mt-4 flex flex-wrap items-center gap-2">{meta}</div>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  );
}

export function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return (
    <pre className={cn("max-h-80 min-w-0 overflow-auto whitespace-pre-wrap break-words border-l-2 border-accent/40 bg-raised/50 p-3 font-mono text-[12px] leading-5 text-ink-soft", className)}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
