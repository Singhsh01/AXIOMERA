export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function ago(iso?: string | null) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 0) return until(iso);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function until(iso?: string | null) {
  if (!iso) return "—";
  const s = (new Date(iso).getTime() - Date.now()) / 1000;
  const a = Math.abs(s);
  const txt = a < 3600 ? `${Math.round(a / 60)}m` : a < 172800 ? `${Math.round(a / 3600)}h` : `${Math.round(a / 86400)}d`;
  return s >= 0 ? `in ${txt}` : `${txt} overdue`;
}

export function dt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const pct = (v?: number | null) => (v === null || v === undefined ? "—" : `${v}%`);
export const usd = (v?: number | null) => (v === null || v === undefined ? "—" : v === 0 ? "$0.00" : `$${v.toFixed(v < 1 ? 4 : 2)}`);
export const human = (s?: string | null) => (s ? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "—");
export const ms = (v?: number | null) => (v === null || v === undefined ? "—" : v < 1000 ? `${v} ms` : `${(v / 1000).toFixed(1)} s`);
