import { BRAND } from "@/lib/brand";

/**
 * The Axiomera mark: a portal (two columns under an overhanging lintel) bisected by a single axis,
 * with a square node where decisions are taken. Drawn with currentColor plus the accent token, so it
 * works on light and dark surfaces and down to 16 px.
 */
export function Mark({ className = "h-7 w-7", title }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role={title ? "img" : undefined} aria-hidden={title ? undefined : true} aria-label={title}>
      <path d="M4 7.5h24" stroke="currentColor" strokeWidth="2.6" strokeLinecap="square" />
      <path d="M8.5 9v16.5M23.5 9v16.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="square" />
      <path d="M16 9v16.5" stroke="currentColor" strokeWidth="1" />
      <rect x="13" y="14" width="6" height="6" style={{ fill: "rgb(var(--accent))" }} />
      <path d="M3 27.5h26" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return <span className={`font-display text-[15px] font-bold uppercase tracking-wordmark ${className}`}>{BRAND.name}</span>;
}

export function Logo({ className = "", compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-2.5 text-ink ${className}`}>
      <Mark title={compact ? BRAND.name : undefined} />
      {!compact && <Wordmark />}
    </span>
  );
}
