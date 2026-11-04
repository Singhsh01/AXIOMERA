# Security model

## Principals and permissions

| Principal | Authentication | Permissions |
|---|---|---|
| viewer | JWT | read |
| reviewer | JWT | read, review/correct compliance, approve proposals |
| operator | JWT | read, cases, tenders, knowledge uploads, trigger workflows |
| approver | JWT | operator-level work plus deciding approvals up to its rank |
| admin | JWT | everything, incl. critical approvals, policies, integrations, dead-letter replay, evaluations |
| n8n service | `X-Axiomera-Service-Token` | read, move cases/RFPs forward, report workflow steps, execute *already approved* actions, notify — **never decide** |

Every query filters by the principal's workspace; users only see workspaces they are members of.

## Consequential actions

1. A proposed action is evaluated against the workspace policy (`platform/approval_policies.json`, editable by admins in the UI). First matching rule wins; unknown actions use the default rule, which must require approval.
2. An approval stores the risk level, required role, expiry and `scope_hash = sha256(action_type | canonical(params))`.
3. Deciding requires the `approval.decide` permission, a role rank ≥ the rule's required role, an unexpired approval and a decider different from the requester.
4. Workflow E calls `GET /approvals/{id}/authorize`, which re-checks decider status, role and the current parameters' hash.
5. The consequential tool itself calls `assert_executable` immediately before touching the connector. This is the boundary: even a fully compromised agent prompt cannot run a refund without an approved record whose hash matches the exact refund.
6. Execution uses an idempotency key per action, then a verification agent reads the record back.

Policy updates are validated server-side: refunds, credits, customer emails, account modifications and proposal submissions cannot be set to "no approval", and the default must fail closed.

## Untrusted content

Emails, tender documents and tool outputs are data:

- `core/guard.py` detects instruction-override, role hijack, delimiter spoofing, approval bypass, exfiltration, compliance forcing and tool-invocation phrasing.
- Model prompts keep trusted instructions in the system prompt; untrusted text only appears inside `<untrusted_content>` envelopes, with spoofed closing delimiters neutralised.
- Flagged cases move to `needs_review` with no actions until a human releases them; flagged tender sentences are excluded from requirements and shown to the user.
- Model-extracted requirements are accepted only if the quote is found verbatim in the page; drafted proposal sentences making certification, numeric or customer claims not present in their cited evidence are removed and listed for the reviewer.

## Integrity and auditability

- Audit events are hash-chained per workspace (`prev_hash`, `hash`), serialised with an advisory lock; `GET /audit/verify` reports the first broken sequence. Tested by modifying a historical row.
- Audit data is passed through redaction (IBANs, card numbers, API keys, bearer tokens, passwords, sensitive keys).
- Workflow steps, agent runs and tool calls carry correlation ids and n8n execution ids.

## Transport and storage

- Webhooks signed in both directions (see [n8n.md](n8n.md#security)).
- Uploads: size limit, content sniffing (PDF magic bytes / DOCX zip), encrypted PDFs rejected, active PDF content (JavaScript/Launch) flagged and never executed, files stored by SHA-256 outside the web root, sanitised filenames.
- Secrets come from environment variables; the database stores only the *name* of the variable holding an integration credential.
- Rate limiting per client (in-process); `X-Content-Type-Options: nosniff`; CORS restricted to the web origin.

## Known gaps

- Single-instance rate limiting; no account lockout or MFA for the demo login.
- JWT revocation is by expiry only.
- Data retention is configurable (`AXIOMERA_RETENTION_DAYS`) but no purge job ships yet; n8n execution data is pruned after 14 days.
- Injection detection is pattern-based; it is a tripwire, not a guarantee — the approval boundary is what prevents harm.
