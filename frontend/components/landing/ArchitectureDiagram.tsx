/** Static SVG architecture with signals on the edges that carry live traffic. */
const BOX = [
  { id: "sources", x: 20, y: 40, w: 190, h: 150, title: "Event sources", lines: ["Email bridge", "Customer portal", "Monitoring alerts", "Tender uploads"] },
  { id: "n8n", x: 300, y: 40, w: 220, h: 150, title: "n8n", lines: ["Workflows A–E", "Retries and waits", "Schedules", "Error workflow → dead letters"] },
  { id: "api", x: 610, y: 40, w: 240, h: 150, title: "Axiomera API", lines: ["Cases and RFP state", "Approval engine", "Hash-chained audit", "OpenTelemetry + metrics"] },
  { id: "agents", x: 610, y: 240, w: 240, h: 110, title: "Agent runtime", lines: ["Scoped tools, budgets", "LangGraph resolution", "Claude / OpenAI / fixtures"] },
  { id: "data", x: 940, y: 40, w: 200, h: 110, title: "PostgreSQL", lines: ["pgvector + full-text", "Business records"] },
  { id: "conn", x: 940, y: 240, w: 200, h: 110, title: "Connectors", lines: ["Jira, Slack, HubSpot", "Simulators by default"] },
  { id: "web", x: 300, y: 240, w: 220, h: 110, title: "Web app", lines: ["Command center", "Approvals, RFP workspace"] },
];
const EDGES = [
  ["M210 115 H300", true], ["M520 95 H610", true], ["M610 135 H520", true], ["M850 95 H940", false],
  ["M730 190 V240", true], ["M850 295 H940", true], ["M520 295 H560 V160 H610", false],
] as const;

export function ArchitectureDiagram() {
  return (
    <div className="overflow-x-auto">
      <svg viewBox="0 0 1160 370" className="min-w-[760px] w-full" role="img" aria-label="Architecture: event sources call n8n, n8n calls the Axiomera API, which uses the agent runtime, PostgreSQL and connectors; the web app reads the API.">
        {EDGES.map(([d, live], i) => (
          <g key={i}>
            <path d={d} style={{ stroke: "rgb(var(--ink) / 0.3)" }} strokeWidth="1" fill="none" />
            {live && <path d={d} strokeWidth="2.5" fill="none" className="signal" style={{ stroke: "rgb(var(--accent))", animationDelay: `${i * 0.35}s` }} />}
          </g>
        ))}
        {BOX.map((b) => (
          <g key={b.id}>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} style={{ fill: b.id === "api" ? "rgb(var(--inverse))" : "rgb(var(--surface))", stroke: b.id === "api" ? "rgb(var(--inverse))" : "rgb(var(--ink) / 0.22)" }} />
            <text x={b.x + 16} y={b.y + 30} style={{ fill: b.id === "api" ? "rgb(var(--on-inverse))" : "rgb(var(--ink))" }} fontSize="16" fontFamily="Manrope Variable" fontWeight="700">{b.title}</text>
            {b.lines.map((l, i) => <text key={l} x={b.x + 16} y={b.y + 56 + i * 22} style={{ fill: b.id === "api" ? "rgb(var(--on-inverse) / 0.7)" : "rgb(var(--ink-mute))" }} fontSize="12" fontFamily="IBM Plex Mono">{l}</text>)}
          </g>
        ))}
      </svg>
    </div>
  );
}
