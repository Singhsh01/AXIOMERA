import Link from "next/link";
import { ArchitectureDiagram } from "@/components/landing/ArchitectureDiagram";
import { EvalResults } from "@/components/landing/EvalResults";
import { HeroTrace } from "@/components/landing/HeroTrace";
import { ParallaxImage, Rail, Reveal, RiseLines, SiteHeader, ThemedImage } from "@/components/landing/Motion";
import { Mark, Wordmark } from "@/components/Logo";
import { BRAND } from "@/lib/brand";

const AGENTS = [
  ["Triage", "Summarises and extracts; category and priority are decided by rules"],
  ["Research", "Pulls the customer, their orders and the policy passages that apply"],
  ["Resolution", "LangGraph loop: plan, draft, validate against what is approved"],
  ["Communication", "Writes the reply and is checked for promises it cannot keep"],
  ["Execution", "Runs approved actions only, and only if parameters still match"],
  ["Verification", "Reads the record back and compares it with what was intended"],
  ["Requirements", "Extracts tender obligations with page and character offsets"],
  ["Compliance", "Rates each requirement against approved, unexpired evidence"],
  ["Proposal", "Drafts grounded sections where every sentence carries a citation"],
];

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

function Chapter({ n, kicker, title, children, id }: { n: string; kicker: string; title: React.ReactNode; children?: React.ReactNode; id?: string }) {
  return (
    <Reveal className="max-w-xl">
      <p id={id} className="flex scroll-mt-28 items-center gap-4 font-mono text-[11px] uppercase tracking-label text-ink-mute">
        <span className="text-ink">{n}</span><span className="h-px w-10 bg-ink/30" />{kicker}
      </p>
      <h2 className="h-display mt-6 text-[40px] sm:text-[56px]">{title}</h2>
      {children && <div className="mt-6 space-y-4 text-[16px] leading-relaxed text-ink-soft">{children}</div>}
    </Reveal>
  );
}

function Shot({ name, alt, className }: { name: string; alt: string; className?: string }) {
  return (
    <figure className={`border border-line bg-surface p-2 shadow-lift ${className ?? ""}`}>
      <ThemedImage light={`/screens/${name}-light.webp`} dark={`/screens/${name}-dark.webp`} alt={alt} imgClassName="w-full" />
    </figure>
  );
}

export default function Landing() {
  return (
    <div className="bg-page xl:pl-14">
      <Rail />
      <SiteHeader />

      {/* ------------------------------------------------------------- hero */}
      <section className="relative flex min-h-[100svh] flex-col overflow-hidden">
        <ParallaxImage light="/media/hero-massing.webp" dark="/media/dusk.webp" alt="" />
        <div className="absolute inset-0 bg-page/80 md:bg-transparent md:bg-gradient-to-r md:from-page md:via-page/60 md:to-page/0" aria-hidden />
        <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-page to-transparent" aria-hidden />
        <div className="relative mx-auto flex w-full max-w-[1400px] flex-1 flex-col justify-center px-5 pb-10 pt-28 sm:px-10">
          <p className="font-mono text-[11px] uppercase tracking-label text-ink-soft">{BRAND.descriptor}</p>
          <h1 className="h-display mt-7 max-w-[15ch] text-[52px] sm:text-[80px] lg:text-[96px]">
            <RiseLines lines={["Automation,", "built on", <span key="a" className="font-serif text-[1.08em] font-normal italic tracking-[-0.02em] text-accent">axioms.</span>]} />
          </h1>
          <Reveal delay={0.55} className="mt-8 max-w-[34rem]">
            <p className="text-[17px] leading-relaxed text-ink-soft">
              {BRAND.name} runs customer cases and tender responses through n8n workflows and AI agents, cites the evidence behind every
              recommendation, and waits for an authorised person before anything consequential leaves the building.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-6">
              <Link href="/login" className="focus-ring inline-flex h-12 items-center gap-3 bg-primary px-7 font-mono text-[11px] uppercase tracking-label text-primary-fg transition-colors hover:bg-primary/85">
                Open the command center <span aria-hidden>→</span>
              </Link>
              <a href="#lifecycle" className="focus-ring group inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-label text-ink">
                <span className="border-b border-ink/40 pb-1 group-hover:border-ink">Follow a request</span>
              </a>
            </div>
          </Reveal>
        </div>
        <div className="relative mx-auto flex w-full max-w-[1400px] items-end justify-between gap-6 px-5 pb-8 sm:px-10">
          <a href="#platform" className="focus-ring flex items-center gap-4 font-mono text-[10px] uppercase tracking-[0.3em] text-ink-mute">
            <span className="relative block h-14 w-px overflow-hidden bg-line"><span className="scroll-cue absolute inset-0 bg-ink" /></span>Scroll
          </a>
          <dl className="hidden gap-10 md:flex">
            {[["49 / 49", "consequential actions gated by approval"], ["100 %", "injection recall on the labelled set"], ["A–E", "n8n workflows, version-controlled"]].map(([v, l]) => (
              <div key={l} className="max-w-[12rem] border-l border-ink/25 pl-4">
                <dt className="font-display text-[26px] font-bold tabular tracking-[-0.03em]">{v}</dt>
                <dd className="mt-1 text-[12px] leading-snug text-ink-mute">{l}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <main className="relative">
        {/* ------------------------------------------------------- 01 operations: split screen, layered */}
        <section id="platform" className="mx-auto grid max-w-[1400px] scroll-mt-20 gap-16 px-5 py-28 sm:px-10 lg:grid-cols-[0.85fr_1.15fr] lg:py-40">
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
          <div className="relative">
            <Reveal className="absolute -right-5 -top-10 hidden w-[55%] sm:block lg:-right-10">
              <ThemedImage light="/media/facade-detail.webp" dark="/media/facade-detail-night.webp" alt="" imgClassName="aspect-[4/5] w-full object-cover" />
            </Reveal>
            <Reveal delay={0.15} className="relative pt-24 sm:pr-16">
              <Shot name="command-center" alt={`${BRAND.name} command center: open cases, SLA status, decisions awaiting approval and live n8n runs`} />
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------- 02 proposals: inverse band, screenshot overhangs */}
        <section className="relative">
          <div className="bg-inverse pb-[22vw] pt-28 text-inverse-fg lg:pb-[16vw] lg:pt-36">
            <div className="mx-auto grid max-w-[1400px] gap-12 px-5 sm:px-10 lg:grid-cols-[1fr_1fr]">
              <Reveal>
                <p className="flex items-center gap-4 font-mono text-[11px] uppercase tracking-label text-inverse-fg/60"><span className="text-inverse-fg">02</span><span className="h-px w-10 bg-inverse-fg/30" />Proposal &amp; RFP intelligence</p>
                <h2 className="h-display mt-6 text-[40px] sm:text-[56px]">Tenders read, checked and drafted against your own evidence.</h2>
              </Reveal>
              <Reveal delay={0.1} className="self-end text-[16px] leading-relaxed text-inverse-fg/75">
                <p>Upload a PDF or DOCX. Requirements are extracted with page and character offsets, matched to approved company knowledge with hybrid retrieval, and drafted into a proposal that exports to Word and PDF with an evidence manifest attached.</p>
                <p className="mt-4">A poisoned tender that tells reviewers to &ldquo;mark every requirement compliant&rdquo; is flagged, and changes nothing.</p>
              </Reveal>
            </div>
          </div>
          <Reveal className="relative mx-auto -mt-[18vw] max-w-[1240px] px-5 sm:px-10 lg:-mt-[13vw]">
            <Shot name="rfp-workspace" alt="RFP workspace: source page with the requirement highlighted, compliance matrix and evidence" />
          </Reveal>
        </section>

        {/* ------------------------------------------------------- 03 orchestration: live trace on a drafting grid */}
        <section id="lifecycle" className="mx-auto max-w-[1400px] scroll-mt-20 px-5 py-28 sm:px-10 lg:py-40">
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

        {/* ------------------------------------------------------- 04 agents: image + typographic index */}
        <section className="border-y border-line bg-surface">
          <div className="mx-auto grid max-w-[1400px] lg:grid-cols-[1.1fr_1fr]">
            <div className="relative min-h-[360px] overflow-hidden lg:min-h-0">
              <ThemedImage light="/media/field.webp" dark="/media/field-night.webp" alt="" className="absolute inset-0" imgClassName="h-full w-full object-cover" />
              <div className="absolute bottom-0 left-0 bg-page p-7 sm:p-10 lg:max-w-[70%]">
                <Chapter n="04" kicker="AI agent collaboration" title="Nine specialists. Scoped tools. Budgets." />
              </div>
            </div>
            <ol className="px-5 py-14 sm:px-12 lg:py-24">
              {AGENTS.map(([a, d], i) => (
                <Reveal as="li" key={a} delay={i * 0.04} className="group grid grid-cols-[2.5rem_1fr] gap-4 border-b border-line py-4 last:border-0">
                  <span className="pt-1 font-mono text-[11px] text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
                  <span>
                    <span className="font-display text-[19px] font-bold tracking-[-0.015em] transition-colors group-hover:text-accent">{a}</span>
                    <span className="mt-1 block text-[13.5px] leading-snug text-ink-mute">{d}</span>
                  </span>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* ------------------------------------------------------- 05 governance: full-bleed portal, offset card, numbered grid */}
        <section id="governance" className="scroll-mt-20 py-28 lg:py-40">
          <div className="relative mx-auto max-w-[1400px] px-5 sm:px-10">
            <div className="relative h-[52vw] max-h-[620px] min-h-[320px] overflow-hidden">
              <ThemedImage light="/media/portal.webp" dark="/media/portal-night.webp" alt="A long colonnade under a single lintel, a bronze line running down its axis" className="h-full" imgClassName="h-full w-full object-cover" />
            </div>
            <Reveal className="relative -mt-24 ml-auto max-w-xl border border-line bg-page p-8 sm:-mt-32 sm:p-12 lg:mr-12">
              <p className="flex items-center gap-4 font-mono text-[11px] uppercase tracking-label text-ink-mute"><span className="text-ink">05</span><span className="h-px w-10 bg-ink/30" />Human-governed automation</p>
              <h2 className="h-display mt-6 text-[36px] sm:text-[48px]">Every consequential action passes through a person.</h2>
              <p className="mt-5 text-[15.5px] leading-relaxed text-ink-soft">Guardrails are enforced in code, not in prompts. Policy decides who must sign off; n8n waits on a real Wait node until a person with the right role decides.</p>
            </Reveal>
          </div>
          <dl className="mx-auto mt-20 grid max-w-[1400px] gap-x-12 gap-y-12 px-5 sm:grid-cols-2 sm:px-10 lg:grid-cols-3">
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

        {/* ------------------------------------------------------- 06 integrations: ruled schedule + architecture */}
        <section className="border-t border-line bg-surface">
          <div className="mx-auto max-w-[1400px] px-5 py-28 sm:px-10 lg:py-40">
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

        {/* ------------------------------------------------------- 07 observability: screenshot + measured results */}
        <section id="evidence" className="mx-auto max-w-[1400px] scroll-mt-20 px-5 py-28 sm:px-10 lg:py-40">
          <div className="grid gap-16 lg:grid-cols-[1.25fr_0.75fr] lg:items-center">
            <Reveal><Shot name="observability" alt="Observability: workflow success rate, case resolution time, approval turnaround and AI cost" /></Reveal>
            <Chapter n="07" kicker="Observability & analytics" title="Measured, not asserted.">
              <p>Workflow success, approval turnaround, tool failure rate and AI cost are computed from stored events. Prometheus metrics and OpenTelemetry traces are exported; the audit chain can be verified end to end.</p>
              <p className="text-[13.5px] text-ink-mute">The evaluation datasets are small and written alongside the rules they test: they show the system behaves as designed on known cases, not that it generalises.</p>
            </Chapter>
          </div>
          <div className="mt-20"><EvalResults /></div>
        </section>

        {/* ------------------------------------------------------- closing */}
        <section className="relative overflow-hidden">
          <ThemedImage light="/media/facade-detail.webp" dark="/media/hero-massing-night.webp" alt="" className="absolute inset-0" imgClassName="h-full w-full object-cover" />
          <div className="absolute inset-0 bg-page/75" aria-hidden />
          <div className="relative mx-auto max-w-[1400px] px-5 py-32 sm:px-10 lg:py-44">
            <Reveal>
              <p className="font-serif text-[48px] italic leading-[1.02] sm:text-[80px]">Every decision,<br />on the record.</p>
              <div className="mt-12 flex flex-wrap items-center gap-6">
                <Link href="/login" className="focus-ring inline-flex h-12 items-center gap-3 bg-primary px-7 font-mono text-[11px] uppercase tracking-label text-primary-fg hover:bg-primary/85">Open the demo workspace <span aria-hidden>→</span></Link>
                <span className="text-[13.5px] text-ink-soft">Sign in as an operator, approver or reviewer. All companies, customers and tenders are fictional.</span>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-14 sm:px-10 md:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <span className="inline-flex items-center gap-3 text-ink"><Mark className="h-9 w-9" /><Wordmark className="text-[17px]" /></span>
            <p className="mt-4 max-w-sm text-[13.5px] leading-relaxed text-ink-mute">{BRAND.descriptor}.</p>
          </div>
          <nav aria-label="Platform" className="space-y-2 text-[13.5px]">
            <p className="label mb-3">Platform</p>
            {[["Enterprise operations", "#platform"], ["Request lifecycle", "#lifecycle"], ["Governance", "#governance"], ["Evidence", "#evidence"]].map(([l, h]) => <a key={h} href={h} className="block text-ink-soft hover:text-ink">{l}</a>)}
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
