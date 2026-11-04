import Link from "next/link";
import { ArchitectureDiagram } from "@/components/landing/ArchitectureDiagram";
import { Constellation } from "@/components/landing/Constellation";
import { AgentNetwork, GovernanceGate, OpsConsole, TenderReader } from "@/components/landing/Demos";
import { EvalResults } from "@/components/landing/EvalResults";
import { HeroTrace } from "@/components/landing/HeroTrace";
import { Rail, Reveal, RiseLines, SceneController, SiteHeader, ThemedImage } from "@/components/landing/Motion";
import { Mark, Wordmark } from "@/components/Logo";
import { BRAND } from "@/lib/brand";

/** The systems and agents the platform coordinates, as named stars in the hero constellation. */
const HUBS = [
  { label: "n8n", x: 0.62, y: 0.24 }, { label: "Triage agent", x: 0.78, y: 0.36 }, { label: "Approval", x: 0.7, y: 0.62 },
  { label: "Jira", x: 0.9, y: 0.2 }, { label: "Payments ledger", x: 0.88, y: 0.72 }, { label: "RFP · p.1", x: 0.62, y: 0.84 },
  { label: "Evidence", x: 0.94, y: 0.48 }, { label: "Audit chain", x: 0.66, y: 0.42 }, { label: "Slack", x: 0.8, y: 0.88 },
];
const CLOSING_HUBS = [{ label: "Case #1001", x: 0.72, y: 0.35 }, { label: "Approver", x: 0.84, y: 0.62 }, { label: "Proposal v2", x: 0.6, y: 0.7 }];

const GUARANTEES = [
  ["Approvals bound to scope", "Each approval stores a hash of the exact parameters. Change the amount afterwards and execution is refused."],
  ["Separation of duties", "Requesters cannot approve their own requests, authors cannot sign off their own drafts, services can never decide."],
  ["Untrusted content stays data", "Emails and tender pages are scanned; passages that try to instruct the AI are excluded and flagged."],
  ["Evidence or it is unverified", "A requirement is compliant only when approved, unexpired company knowledge covers it."],
  ["Tamper-evident audit", "Every consequential event is hash-chained per workspace; editing one row breaks verification there."],
  ["Fail closed", "Unknown actions require approval by default; policies that would remove approval from refunds are rejected."],
];

const CONNECTORS = [
  ["n8n", "Orchestration", "Live"], ["E-mail (Gmail-compatible)", "Intake and replies", "Simulator · live-ready"], ["Slack", "Escalation notices", "Simulator · live-ready"],
  ["Jira", "Incident tickets", "Simulator · live-ready"], ["HubSpot CRM", "Customer records", "Simulator · live-ready"], ["Generic REST", "Any HTTP system", "Simulator · live-ready"],
  ["Payments ledger", "Refunds and credits", "Simulator only, by design"],
];

function Kicker({ n, children }: { n: string; children: React.ReactNode }) {
  return <p className="flex items-center gap-4 font-mono text-[11px] uppercase tracking-label text-ink-mute"><span className="text-ink">{n}</span><span className="h-px w-10 bg-ink/30" />{children}</p>;
}

function Chapter({ n, kicker, title, children }: { n: string; kicker: string; title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <Reveal className="max-w-xl">
      <Kicker n={n}>{kicker}</Kicker>
      <h2 className="h-display mt-6 text-[40px] sm:text-[56px]">{title}</h2>
      {children && <div className="mt-6 space-y-4 text-[16px] leading-relaxed text-ink-soft">{children}</div>}
    </Reveal>
  );
}

function Shot({ name, alt }: { name: string; alt: string }) {
  return (
    <figure className="border border-line bg-surface p-2 shadow-lift">
      <ThemedImage light={`/screens/${name}-light.webp`} dark={`/screens/${name}-dark.webp`} alt={alt} imgClassName="w-full" />
    </figure>
  );
}

export default function Landing() {
  return (
    <div className="bg-page xl:pl-14">
      <SceneController />
      <Rail />
      <SiteHeader />

      {/* ------------------------------------------------------------- hero: the descriptor, over a live constellation */}
      <section data-tone="base" className="relative flex min-h-[100svh] flex-col overflow-hidden">
        <div className="gridlines absolute inset-0 opacity-60" aria-hidden />
        <Constellation hubs={HUBS} className="absolute inset-0 h-full w-full" fadeLeft />
        <div className="absolute inset-0 bg-page/75 lg:hidden" aria-hidden />
        <div className="pointer-events-none relative mx-auto flex w-full max-w-[1400px] flex-1 flex-col justify-center px-5 pb-10 pt-28 sm:px-10">
          <p className="font-mono text-[11px] uppercase tracking-label text-ink-soft">{BRAND.name} — automation built on axioms</p>
          <h1 className="h-display mt-7 text-[44px] sm:text-[72px] lg:text-[88px]">
            <RiseLines lines={["Autonomous", "Enterprise Operations", <span key="p" className="font-serif text-[1.06em] font-normal italic tracking-[-0.02em] text-accent">&amp; Proposal Intelligence</span>]} />
          </h1>
          <Reveal delay={0.6} className="pointer-events-auto mt-8 max-w-[36rem]">
            <p className="font-mono text-[11px] uppercase tracking-label text-ink">Platform</p>
            <p className="mt-3 text-[17px] leading-relaxed text-ink-soft">
              Customer cases and tender responses run through n8n workflows and AI agents. Every recommendation cites its evidence, and nothing consequential
              happens until an authorised person approves it.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-6">
              <Link href="/login" className="focus-ring inline-flex h-12 items-center gap-3 bg-primary px-7 font-mono text-[11px] uppercase tracking-label text-primary-fg transition-colors hover:bg-primary/85">
                Open the command center <span aria-hidden>→</span>
              </Link>
              <a href="#journey" className="focus-ring group inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-label text-ink">
                <span className="border-b border-ink/40 pb-1 group-hover:border-ink">▶ Watch the demo journey</span>
              </a>
            </div>
          </Reveal>
        </div>
        <div className="relative mx-auto flex w-full max-w-[1400px] items-end justify-between gap-6 px-5 pb-8 sm:px-10">
          <a href="#engines" className="focus-ring flex items-center gap-4 font-mono text-[10px] uppercase tracking-[0.3em] text-ink-mute">
            <span className="relative block h-14 w-px overflow-hidden bg-line"><span className="scroll-cue absolute inset-0 bg-ink" /></span>Scroll
          </a>
          <dl className="hidden gap-10 md:flex">
            {[["49 / 49", "consequential actions gated by approval"], ["100 %", "injection recall on the labelled set"], ["A–E", "n8n workflows, version-controlled"]].map(([v, l]) => (
              <div key={l} className="max-w-[12rem] border-l border-ink/25 bg-page/60 pl-4 backdrop-blur-[2px]">
                <dt className="font-display text-[26px] font-bold tabular tracking-[-0.03em]">{v}</dt>
                <dd className="mt-1 text-[12px] leading-snug text-ink-mute">{l}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <main className="relative">
        {/* ------------------------------------------------------- two engines, one control plane */}
        <section id="engines" data-tone="base" className="mx-auto max-w-[1400px] scroll-mt-20 px-5 py-24 sm:px-10 lg:py-32">
          <Reveal className="flex flex-wrap items-end justify-between gap-6 border-b border-ink pb-6">
            <h2 className="h-display text-[32px] sm:text-[44px]">Two engines. One control plane.</h2>
            <p className="max-w-md text-[14.5px] text-ink-mute">Both run on the same approval engine, audit chain, agent runtime and n8n orchestration.</p>
          </Reveal>
          <div className="mt-12 grid gap-14 lg:grid-cols-2">
            <Reveal className="min-w-0">
              <p className="font-mono text-[11px] uppercase tracking-label text-accent">Engine I</p>
              <h3 className="mt-3 font-display text-[28px] font-bold tracking-[-0.025em]">Autonomous Enterprise Operations</h3>
              <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-ink-soft">Refund requests, incidents and account changes: triaged, researched and resolved by agents; executed only after approval; verified by reading the record back.</p>
              <div className="mt-7"><OpsConsole /></div>
              <a href="#platform" className="mt-5 inline-block font-mono text-[11px] uppercase tracking-label text-ink-soft hover:text-ink">How operations work →</a>
            </Reveal>
            <Reveal delay={0.12} className="min-w-0">
              <p className="font-mono text-[11px] uppercase tracking-label text-accent">Engine II</p>
              <h3 className="mt-3 font-display text-[28px] font-bold tracking-[-0.025em]">Proposal Intelligence</h3>
              <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-ink-soft">Tenders read line by line: every obligation extracted with its page, rated against approved evidence, drafted into a cited proposal. Hidden instructions are flagged, not obeyed.</p>
              <div className="mt-7"><TenderReader /></div>
              <a href="#proposals" className="mt-5 inline-block font-mono text-[11px] uppercase tracking-label text-ink-soft hover:text-ink">How proposals work →</a>
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------- 01 operations */}
        <section id="platform" data-tone="base" className="mx-auto grid max-w-[1400px] scroll-mt-20 gap-16 px-5 py-24 sm:px-10 lg:grid-cols-[0.8fr_1.2fr] lg:py-36">
          <div className="lg:sticky lg:top-32 lg:h-fit">
            <Chapter n="01" kicker="Enterprise operations" title="One command center for every case.">
              <p>Signed e-mail, portal and monitoring events become cases. Agents triage them, gather evidence and propose a resolution; refunds, credits, replies and account changes wait for an authorised approver.</p>
              <p>Approved actions run through connectors and are read back to prove they happened.</p>
            </Chapter>
            <Reveal delay={0.1}>
              <dl className="mt-12 grid grid-cols-3 border-t border-line pt-6">
                {[["Idempotent", "a replayed webhook never opens a second case"], ["Verified", "every action read back after it runs"], ["Live", "read straight from the database n8n writes"]].map(([k, v]) => (
                  <div key={k} className="pr-4"><dt className="font-display text-[15px] font-bold">{k}</dt><dd className="mt-1 text-[12.5px] leading-snug text-ink-mute">{v}</dd></div>
                ))}
              </dl>
            </Reveal>
          </div>
          <Reveal delay={0.15}><Shot name="command-center" alt={`${BRAND.name} command center: open cases, SLA status, decisions awaiting approval and live n8n runs`} /></Reveal>
        </section>

        {/* ------------------------------------------------------- 02 proposals (scene turns) */}
        <section id="proposals" data-tone="alt" className="scroll-mt-20 py-24 lg:py-36">
          <div className="mx-auto grid max-w-[1400px] gap-12 px-5 sm:px-10 lg:grid-cols-[1fr_1fr]">
            <Chapter n="02" kicker="Proposal & RFP intelligence" title="Tenders read, checked and drafted against your own evidence." />
            <Reveal delay={0.1} className="self-end text-[16px] leading-relaxed text-ink-soft">
              <p>Upload a PDF or DOCX. Requirements are extracted with page and character offsets, matched to approved company knowledge with hybrid retrieval, and drafted into a proposal that exports to Word and PDF with an evidence manifest attached.</p>
              <p className="mt-4">A poisoned tender that tells reviewers to &ldquo;mark every requirement compliant&rdquo; is flagged, and changes nothing.</p>
            </Reveal>
          </div>
          <Reveal className="mx-auto mt-16 max-w-[1240px] px-5 sm:px-10">
            <Shot name="rfp-workspace" alt="RFP workspace: source page with the requirement highlighted, compliance matrix and evidence" />
          </Reveal>
        </section>

        {/* ------------------------------------------------------- 03 orchestration */}
        <section id="lifecycle" data-tone="base" className="mx-auto max-w-[1400px] scroll-mt-20 px-5 py-24 sm:px-10 lg:py-36">
          <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-end">
            <Chapter n="03" kicker="Intelligent workflow orchestration" title={<>n8n decides <em className="font-serif font-normal italic">when</em>. {BRAND.name} decides what is true.</>} />
            <Reveal delay={0.1} className="text-[16px] leading-relaxed text-ink-soft lg:pb-2">
              <p>Workflows own sequencing, retries, waits and schedules. The API owns business state, so a replayed webhook or a retried node can never create a second case or a second refund. Below: the request lifecycle of n8n Workflow A, step by step.</p>
            </Reveal>
          </div>
          <Reveal delay={0.1} className="gridlines relative mt-16 border border-line bg-surface/50 p-6 sm:p-10">
            <span className="absolute left-0 top-0 h-3 w-3 border-l-2 border-t-2 border-ink" aria-hidden />
            <span className="absolute bottom-0 right-0 h-3 w-3 border-b-2 border-r-2 border-ink" aria-hidden />
            <HeroTrace />
          </Reveal>
        </section>

        {/* ------------------------------------------------------- 04 agents (scene turns): live collaboration constellation */}
        <section data-tone="alt" className="relative overflow-hidden py-24 lg:py-36">
          <Constellation className="absolute inset-0 h-full w-full opacity-60" density={0.6} pulses={false} />
          <div className="relative mx-auto grid max-w-[1400px] items-center gap-12 px-5 sm:px-10 lg:grid-cols-[0.8fr_1.2fr]">
            <Chapter n="04" kicker="AI agent collaboration" title="Nine specialists. One human in the loop.">
              <p>Each agent has scoped tools, a budget and a prompt version on record. They hand work to each other in a fixed order, and the human approver sits at the centre: nothing crosses from proposal to execution without them.</p>
            </Chapter>
            <Reveal delay={0.1}><AgentNetwork /></Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------- 05 governance: the approval gate in motion */}
        <section id="governance" data-tone="base" className="mx-auto max-w-[1400px] scroll-mt-20 px-5 py-24 sm:px-10 lg:py-36">
          <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-end">
            <Chapter n="05" kicker="Human-governed automation" title="Every consequential action passes through a person." />
            <Reveal delay={0.1} className="text-[16px] leading-relaxed text-ink-soft lg:pb-2">
              <p>Guardrails are enforced in code, not in prompts. Manipulated input is held at the scan; policy decides who must sign off; n8n waits on a real Wait node until that person decides; only approved actions whose parameters still match are executed and read back.</p>
            </Reveal>
          </div>
          <Reveal delay={0.1} className="mt-14 border-y border-line"><GovernanceGate /></Reveal>
          <dl className="mt-16 grid gap-x-12 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {GUARANTEES.map(([t, d], i) => (
              <Reveal key={t} delay={(i % 3) * 0.08}>
                <dt className="flex items-baseline gap-4 border-t-[3px] border-ink pt-5">
                  <span className="font-mono text-[11px] text-accent">{String(i + 1).padStart(2, "0")}</span>
                  <span className="font-display text-[19px] font-bold tracking-[-0.015em]">{t}</span>
                </dt>
                <dd className="mt-3 pl-9 text-[14.5px] leading-relaxed text-ink-mute">{d}</dd>
              </Reveal>
            ))}
          </dl>
        </section>

        {/* ------------------------------------------------------- 06 integrations (scene turns) */}
        <section data-tone="alt" className="border-t border-line">
          <div className="mx-auto max-w-[1400px] px-5 py-24 sm:px-10 lg:py-36">
            <div className="grid gap-16 lg:grid-cols-[0.8fr_1.2fr]">
              <Chapter n="06" kicker="Enterprise integrations" title="Connected, and honest about it.">
                <p>Every connector reports its effective mode. Without credentials, records come from clearly labelled simulators; payments never leave the simulator in this project.</p>
              </Chapter>
              <Reveal delay={0.1}>
                <table className="w-full text-left">
                  <thead><tr className="border-b border-ink/80"><th className="label pb-3 font-normal">System</th><th className="label pb-3 font-normal">Role</th><th className="label pb-3 text-right font-normal">Mode</th></tr></thead>
                  <tbody>
                    {CONNECTORS.map(([s, r, m]) => (
                      <tr key={s} className="border-b border-line">
                        <td className="py-4 pr-4 font-display text-[16px] font-bold">{s}</td>
                        <td className="py-4 pr-4 text-[13.5px] text-ink-mute">{r}</td>
                        <td className="py-4 text-right font-mono text-[11px] uppercase tracking-[0.06em] text-ink-soft">{m}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Reveal>
            </div>
            <Reveal delay={0.1} className="mt-20 border border-line bg-page p-5 sm:p-8"><ArchitectureDiagram /></Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------- 07 observability */}
        <section id="evidence" data-tone="base" className="mx-auto max-w-[1400px] scroll-mt-20 px-5 py-24 sm:px-10 lg:py-36">
          <div className="grid gap-16 lg:grid-cols-[1.25fr_0.75fr] lg:items-center">
            <Reveal><Shot name="observability" alt="Observability: workflow success rate, case resolution time, approval turnaround and AI cost" /></Reveal>
            <Chapter n="07" kicker="Observability & analytics" title="Measured, not asserted.">
              <p>Workflow success, approval turnaround, tool failure rate and AI cost are computed from stored events. Prometheus metrics and OpenTelemetry traces are exported; the audit chain can be verified end to end.</p>
              <p className="text-[13.5px] text-ink-mute">The evaluation datasets are small and written alongside the rules they test: they show the system behaves as designed on known cases, not that it generalises.</p>
            </Chapter>
          </div>
          <div className="mt-20"><EvalResults /></div>
        </section>

        {/* ------------------------------------------------------- demo journey video (scene turns) */}
        <section id="journey" data-tone="alt" className="scroll-mt-20 border-t border-line py-24 lg:py-36">
          <div className="mx-auto max-w-[1400px] px-5 sm:px-10">
            <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-end">
              <Chapter n="08" kicker="The demo journey" title="From an ordinary refund to an attack, an outage and a poisoned tender." />
              <Reveal delay={0.1} className="text-[16px] leading-relaxed text-ink-soft lg:pb-2">
                <p>Recorded from real runs of this stack: the everyday path, then the extremes it is built for. A manipulation attempt, a flaky integration that n8n retries and finally dead-letters, a tender with hidden instructions, a self-approval attempt, a brute-force lockout and a thousand concurrent users.</p>
              </Reveal>
            </div>
            <Reveal delay={0.1} className="mt-14 border border-line bg-surface p-2 shadow-lift">
              <video className="w-full" controls preload="none" poster="/media/journey-poster.jpg" playsInline>
                <source src="/media/journey.mp4" type="video/mp4" />
              </video>
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------- closing */}
        <section data-tone="alt" className="relative overflow-hidden">
          <Constellation hubs={CLOSING_HUBS} className="absolute inset-0 h-full w-full" fadeLeft density={0.8} />
          <div className="pointer-events-none relative mx-auto max-w-[1400px] px-5 py-32 sm:px-10 lg:py-44">
            <Reveal className="pointer-events-auto">
              <p className="font-serif text-[48px] italic leading-[1.02] sm:text-[80px]">Every decision,<br />on the record.</p>
              <div className="mt-12 flex flex-wrap items-center gap-6">
                <Link href="/login" className="focus-ring inline-flex h-12 items-center gap-3 bg-primary px-7 font-mono text-[11px] uppercase tracking-label text-primary-fg hover:bg-primary/85">Open the demo workspace <span aria-hidden>→</span></Link>
                <span className="text-[13.5px] text-ink-soft">Sign in as an operator, approver or reviewer. All companies, customers and tenders are fictional.</span>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer data-tone="alt" className="border-t border-line">
        <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-14 sm:px-10 md:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <span className="inline-flex items-center gap-3 text-ink"><Mark className="h-9 w-9" /><Wordmark className="text-[17px]" /></span>
            <p className="mt-4 max-w-sm text-[13.5px] leading-relaxed text-ink-mute">{BRAND.descriptor}.</p>
          </div>
          <nav aria-label="Platform" className="space-y-2 text-[13.5px]">
            <p className="label mb-3">Platform</p>
            {[["Two engines", "#engines"], ["Request lifecycle", "#lifecycle"], ["Governance", "#governance"], ["Demo journey", "#journey"]].map(([l, h]) => <a key={h} href={h} className="block text-ink-soft hover:text-ink">{l}</a>)}
          </nav>
          <div className="space-y-2 text-[13.5px] text-ink-mute">
            <p className="label mb-3">About this build</p>
            <p>Portfolio project. Integrations run against labelled local simulators unless live credentials are configured.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
