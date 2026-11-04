"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Logo } from "@/components/Logo";
import { Constellation } from "@/components/landing/Constellation";
import { ThemeToggle } from "@/components/theme";
import { BRAND } from "@/lib/brand";
import { Button, ErrorNote, Field, inputCls } from "@/components/ui/primitives";
import { post } from "@/lib/api";

const LOGIN_HUBS = [{ label: "Operator", x: 0.25, y: 0.22 }, { label: "Approver", x: 0.7, y: 0.3 }, { label: "Reviewer", x: 0.45, y: 0.5 }, { label: "Admin", x: 0.8, y: 0.55 }];

const DEMO = [
  ["ops@orkestr.dev", "Olivia", "Operator", "Runs cases and tenders"],
  ["approver@orkestr.dev", "Priya", "Approver", "Signs off refunds and emails"],
  ["reviewer@orkestr.dev", "Rafael", "Reviewer", "Reviews proposals"],
  ["admin@orkestr.dev", "Alex", "Admin", "Policies, integrations, large refunds"],
];

function LoginForm() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/app";
  const [email, setEmail] = useState("ops@orkestr.dev");
  const [password, setPassword] = useState("orkestr-demo");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/auth/login", { email, password });
      router.push(next);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen bg-page lg:grid-cols-[1.1fr_1fr]">
      <aside className="tone-invert relative hidden overflow-hidden lg:block">
        <div className="gridlines absolute inset-0 opacity-70" aria-hidden />
        <Constellation hubs={LOGIN_HUBS} className="absolute inset-0 h-full w-full" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-page via-page/80 to-transparent p-12 pt-32">
          <p className="font-mono text-[11px] uppercase tracking-label text-ink-mute">{BRAND.name} · {BRAND.descriptor}</p>
          <p className="mt-4 max-w-md font-serif text-[40px] italic leading-[1.05] text-ink">Every consequential action passes through a person.</p>
        </div>
      </aside>
      <main className="flex flex-col px-6 py-10 sm:px-12 lg:px-16">
        <div className="flex items-center justify-between">
          <Link href="/" className="focus-ring"><Logo /></Link>
          <ThemeToggle />
        </div>
        <div className="page-enter my-auto w-full max-w-[440px] py-12">
          <span className="marker" />
          <h1 className="h-display mt-6 text-[44px]">Sign in</h1>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-mute">Demo workspace. Pick a role to see what it can do; approvals and proposal reviews need a different person than the one who requested them.</p>
          <form onSubmit={submit} className="mt-9 space-y-5">
            <Field label="Email"><input className={inputCls} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
            <Field label="Password" hint="All demo accounts use orkestr-demo">
              <input className={inputCls} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
            <ErrorNote error={error} />
            <Button variant="primary" size="lg" className="w-full" loading={busy}>Sign in</Button>
          </form>
          <div className="mt-10">
            <p className="label mb-3">Demo accounts</p>
            <div className="grid border-l border-t border-line sm:grid-cols-2">
              {DEMO.map(([e, n, r, d]) => (
                <button key={e} type="button" onClick={() => { setEmail(e); setPassword("orkestr-demo"); }}
                  className={`focus-ring relative border-b border-r border-line px-4 py-3 text-left transition-colors ${email === e ? "bg-raised" : "hover:bg-raised/50"}`}>
                  {email === e && <span className="absolute inset-y-0 left-0 w-[2px] bg-ink" aria-hidden />}
                  <span className="block text-[13.5px] font-semibold">{n} <span className="font-normal text-ink-mute">· {r}</span></span>
                  <span className="block text-xs text-ink-mute">{d}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="label text-ink-faint">{BRAND.descriptor}</p>
      </main>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
