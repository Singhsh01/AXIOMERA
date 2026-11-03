"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Logo } from "@/components/Logo";
import { Button, ErrorNote, Field, inputCls } from "@/components/ui/primitives";
import { post } from "@/lib/api";

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
    <div className="ambient flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-[920px] gap-10 md:grid md:grid-cols-[1fr_1fr] md:items-center">
        <div className="mb-10 md:mb-0">
          <Link href="/" className="focus-ring inline-block rounded-md"><Logo /></Link>
          <h1 className="h-display mt-10 text-[44px] font-semibold">Sign in to the demo workspace</h1>
          <p className="mt-4 text-ink-mute">Pick a role to see what it can do. Approvals and proposal reviews need a different person than the one who requested them.</p>
        </div>
        <div className="glass-strong p-6 sm:p-8">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Email"><input className={inputCls} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
            <Field label="Password" hint="All demo accounts use orkestr-demo">
              <input className={inputCls} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
            <ErrorNote error={error} />
            <Button variant="primary" size="lg" className="w-full" loading={busy}>Sign in</Button>
          </form>
          <div className="mt-6 border-t border-line pt-5">
            <p className="mb-3 text-[13px] text-ink-mute">Demo accounts</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {DEMO.map(([e, n, r, d]) => (
                <button key={e} type="button" onClick={() => { setEmail(e); setPassword("orkestr-demo"); }}
                  className={`focus-ring rounded-lg border px-3 py-2 text-left transition-colors ${email === e ? "border-violet/60 bg-violet/10" : "border-line hover:bg-white/[0.04]"}`}>
                  <span className="block text-sm font-medium">{n} <span className="text-ink-mute">· {r}</span></span>
                  <span className="block text-xs text-ink-faint">{d}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
