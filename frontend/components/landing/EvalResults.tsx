import fs from "node:fs";
import path from "node:path";

type Suite = { suite: string; title: string; uses_fixtures: boolean; provider: string; generated_at: string; headline: { label: string; value: string }[] };

/** Reads backend/evals/results/summary.json at build time; copied into public/ by `make eval`. */
function load(): Suite[] | null {
  const candidates = [path.join(process.cwd(), "public", "eval-summary.json"), path.join(process.cwd(), "..", "backend", "evals", "results", "summary.json")];
  for (const c of candidates) {
    try { return JSON.parse(fs.readFileSync(c, "utf8")).suites as Suite[]; } catch {}
  }
  return null;
}

export function EvalResults() {
  const suites = load();
  if (!suites) return <p className="mt-8 text-ink-mute">No evaluation results found. Run <code className="font-mono">make eval</code> to generate them.</p>;
  return (
    <div className="grid border-l border-t border-line md:grid-cols-3">
      {suites.map((s) => (
        <div key={s.suite} className="border-b border-r border-line p-7">
          <h3 className="font-display text-[18px] font-bold tracking-[-0.015em]">{s.title}</h3>
          <p className="mt-1 font-mono text-[10.5px] text-ink-mute">{s.uses_fixtures ? "Deterministic fixtures, no model calls" : `Provider: ${s.provider}`} · {new Date(s.generated_at).toLocaleDateString("en-GB")}</p>
          <dl className="mt-5 space-y-3">
            {s.headline.map((h) => (
              <div key={h.label} className="flex items-baseline justify-between gap-4 border-b border-line pb-2.5">
                <dt className="text-[13px] text-ink-mute">{h.label}</dt>
                <dd className="font-display text-[20px] font-bold tabular">{h.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}
