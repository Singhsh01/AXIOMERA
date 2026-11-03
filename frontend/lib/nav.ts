import { BookOpen, Bot, FileText, Gauge, Inbox, KeyRound, PlugZap, Settings, ShieldCheck, Telescope, Workflow } from "lucide-react";

/** Single source for the app's sections: sidebar order, page numbering and titles. */
export const NAV = [
  { href: "/app", label: "Command center", icon: Gauge, group: "Operate" },
  { href: "/app/cases", label: "Cases", icon: Inbox, group: "Operate" },
  { href: "/app/approvals", label: "Approvals", icon: ShieldCheck, group: "Operate" },
  { href: "/app/rfps", label: "Proposals", icon: FileText, group: "Operate" },
  { href: "/app/workflows", label: "Workflows", icon: Workflow, group: "Orchestrate" },
  { href: "/app/agents", label: "Agents", icon: Bot, group: "Orchestrate" },
  { href: "/app/knowledge", label: "Knowledge", icon: BookOpen, group: "Orchestrate" },
  { href: "/app/observability", label: "Observability", icon: Telescope, group: "Govern" },
  { href: "/app/integrations", label: "Integrations", icon: PlugZap, group: "Govern" },
  { href: "/app/settings", label: "Policies", icon: Settings, group: "Govern" },
  { href: "/app/access", label: "Access log", icon: KeyRound, group: "Govern" },
] as const;

export function sectionFor(path: string) {
  const i = NAV.findIndex((n) => (n.href === "/app" ? path === "/app" : path.startsWith(n.href)));
  return i < 0 ? null : { index: String(i + 1).padStart(2, "0"), ...NAV[i] };
}
