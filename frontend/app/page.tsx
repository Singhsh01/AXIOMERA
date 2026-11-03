import Link from "next/link";
import { HeroTrace } from "@/components/landing/HeroTrace";
import { Logo } from "@/components/Logo";
import { ArchitectureDiagram } from "@/components/landing/ArchitectureDiagram";
import { EvalResults } from "@/components/landing/EvalResults";

const FLOW = [
  ["Intake", "Email, portal and monitoring events arrive at a signed n8n webhook. The Message-ID or event id makes redelivery harmless."],
  ["Classify", "Rules decide category, priority and SLA so the decision is reproducible. The triage agent only summarises and extracts."],
  ["Gather evidence", "The research agent pulls the customer, their orders and the policy passages that apply, with sources recorded."],
  ["Propose", "A LangGraph resolution graph plans actions, drafts the reply and checks it never promises what has not been approved."],
  ["Approve", "Policy decides who must sign off. n8n waits on a real Wait node until a person with the right role decides."],
  ["Execute and verify", "The approved action runs only if its parameters still hash to what was approved, then gets read back and checked."],
];

const GUARANTEES = [
  ["Approvals bound to scope", "Each approval stores a hash of the exact action parameters. Change the amount afterwards and execution is refused."],
  ["Separation of duties", "Requesters cannot approve their own requests. Proposal authors cannot sign off their own drafts. Services can never decide."],
  ["Untrusted content stays data", "Emails and tender documents are wrapped and scanned. Passages that try to instruct the AI are excluded and flagged."],
  ["Evidence or it is unverified", "A requirement is only compliant when approved, unexpired company knowledge covers it. Humans cannot override that either."],
  ["Tamper-evident audit", "Every consequential event is hash-chained per workspace. Editing one historical row breaks verification at that row."],
  ["Fail closed", "Unknown actions require approval by default. Policy edits that would remove approval from refunds are rejected."],
];

export default function Landing() {
  return (
    <div className="ambient relative min-h-screen overflow-hidden">
      <div className="gridlines pointer-events-none absolute inset-0" />
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-8">
        <Logo />
        <nav className="flex items-center gap-1 text-sm">
          <a href="#flow" className="focus-ring hidden rounded-md px-3 py-2 text-ink-mute hover:text-ink sm:block">Request lifecycle</a>
          <a href="#engines" className="focus-ring hidden rounded-md px-3 py-2 text-ink-mute hover:text-ink sm:block">Capabilities</a>
          <a href="#trust" className="focus-ring hidden rounded-md px-3 py-2 text-ink-mute hover:text-ink sm:block">Governance &amp; controls</a>
          <Link href="/login" className="focus-ring ml-2 rounded-lg border border-line bg-ink/[0.04] px-4 py-2 font-medium hover:bg-ink/[0.08]">Sign in</Link>
        </nav>
      </header>

      <main className="relative z-10">
        <section className="mx-auto max-w-7xl px-4 pb-20 pt-10 sm:px-8 sm:pt-14">
          <h1 className="h-display max-w-5xl text-[42px] font-semibold sm:text-[60px] lg:text-[68px]">
            Automate the back office. Keep a human on every decision that matters.
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-relaxed text-ink-soft">
            Orkestr runs customer cases and tender responses through n8n workflows and AI agents, cites the evidence behind every
            recommendation, and waits for an authorised person before anything leaves the building.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link href="/login" className="focus-ring rounded-lg bg-gradient-to-b from-[#7D6EEA] to-violet-deep px-5 py-3 font-medium text-white shadow-[0_10px_30px_-10px_rgba(106,90,224,0.45)]">
              Open the command center
            </Link>
            <a href="#flow" className="focus-ring rounded-lg border border-line px-5 py-3 font-medium text-ink-soft hover:text-ink">View the request lifecycle</a>
          </div>
          <div className="glass mt-12 p-5 sm:p-8">
            <HeroTrace />
          </div>
        </section>

        <section id="flow" className="mx-auto max-w-7xl px-4 py-20 sm:px-8">
          <h2 className="h-display max-w-3xl text-[36px] font-semibold sm:text-[52px]">Request lifecycle: from an inbound email to a verified, approved outcome</h2>
          <ol className="mt-12 grid gap-px overflow-hidden rounded-panel border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
            {FLOW.map(([t, d], i) => (
              <li key={t} className="bg-midnight/95 p-6">
                <span className="font-display text-[40px] font-semibold leading-none text-transparent [-webkit-text-stroke:1px_rgba(40,52,110,0.35)]">{i + 1}</span>
                <h3 className="mt-4 font-display text-xl font-semibold">{t}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-ink-mute">{d}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="engines" className="mx-auto max-w-7xl px-4 py-20 sm:px-8">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.35fr] lg:items-center">
            <div>
              <h2 className="h-display text-[36px] font-semibold sm:text-[48px]">Cases, incidents and approvals in one command center</h2>
              <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">
                Live workflow activity, SLA clocks, pending approvals and agent runs come straight from the database n8n writes into.
                Open any case to see each agent&apos;s tool calls, the policy passages it cited and the n8n execution that moved it.
              </p>
            </div>
            <figure className="glass overflow-hidden p-1.5 shadow-glow">
              <img src="/screens/command-center.webp" alt="Orkestr command center showing open cases, SLA status, pending approvals and live workflow runs" className="w-full rounded-[10px]" loading="lazy" />
            </figure>
          </div>
          <div className="mt-20 grid gap-10 lg:grid-cols-[1.35fr_1fr] lg:items-center">
            <figure className="glass order-2 overflow-hidden p-1.5 shadow-glow lg:order-1">
              <img src="/screens/rfp-workspace.webp" alt="RFP workspace with source document, extracted requirements and compliance evidence side by side" className="w-full rounded-[10px]" loading="lazy" />
            </figure>
            <div className="order-1 lg:order-2">
              <h2 className="h-display text-[36px] font-semibold sm:text-[48px]">Tenders read, checked and drafted against your own evidence</h2>
              <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">
                Upload a PDF or DOCX. Requirements are extracted with page and character offsets, matched to approved company knowledge with
                hybrid search, and drafted into a proposal that exports to Word and PDF with an evidence manifest attached.
              </p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-8">
          <h2 className="h-display max-w-3xl text-[36px] font-semibold sm:text-[48px]">n8n decides when. Orkestr decides what is true.</h2>
          <p className="mt-5 max-w-2xl text-[16px] leading-relaxed text-ink-soft">
            Workflows own sequencing, retries, waits and schedules. The API owns business state, so a replayed webhook or a retried node can never
            create a second case or a second refund.
          </p>
          <div className="glass mt-10 p-4 sm:p-8"><ArchitectureDiagram /></div>
        </section>

        <section id="trust" className="mx-auto max-w-7xl px-4 py-20 sm:px-8">
          <h2 className="h-display max-w-3xl text-[36px] font-semibold sm:text-[48px]">Governance &amp; controls enforced in code, not in prompts</h2>
          <dl className="mt-12 grid gap-x-10 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
            {GUARANTEES.map(([t, d]) => (
              <div key={t} className="border-l border-violet/40 pl-5">
                <dt className="font-display text-lg font-semibold">{t}</dt>
                <dd className="mt-2 text-[15px] leading-relaxed text-ink-mute">{d}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-8">
          <h2 className="h-display max-w-3xl text-[36px] font-semibold sm:text-[48px]">Measured on labelled data</h2>
          <p className="mt-5 max-w-2xl text-[16px] leading-relaxed text-ink-soft">
            Results from the repository&apos;s evaluation suites, regenerated with <code className="font-mono text-[14px] text-ink">make eval</code>.
            Runs without a model key use deterministic fixtures and say so.
          </p>
          <EvalResults />
        </section>

        <section className="mx-auto max-w-7xl px-4 pb-24 pt-10 sm:px-8">
          <div className="glass flex flex-col items-start justify-between gap-6 p-8 sm:flex-row sm:items-center sm:p-10">
            <div>
              <h2 className="font-display text-3xl font-semibold tracking-tight">Try it with the demo workspace</h2>
              <p className="mt-2 text-ink-mute">Sign in as an operator, approver or reviewer. All companies, customers and tenders are fictional.</p>
            </div>
            <Link href="/login" className="focus-ring rounded-lg bg-gradient-to-b from-[#7D6EEA] to-violet-deep px-5 py-3 font-medium text-white">Open the command center</Link>
          </div>
        </section>
      </main>
      <footer className="relative z-10 border-t border-line px-4 py-8 text-sm text-ink-faint sm:px-8">
        <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-3">
          <Logo className="opacity-70" />
          <span>Portfolio project. Integrations run against local simulators unless live credentials are configured.</span>
        </div>
      </footer>
    </div>
  );
}
