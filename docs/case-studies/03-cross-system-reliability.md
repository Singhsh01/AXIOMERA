# Case study 3 — Cross-system workflow reliability

**Goal:** a failing integration, retry handling, recovery, auditability and completion verification.

Failures are injected into the local Jira/Slack simulators (`POST /integrations/{kind}/inject-failures`, admin only). The next N calls raise a transient error, which the API returns as HTTP 503 — the signal n8n's retry policy acts on. The failure counter is written in its own transaction so a rolled-back request never leaks partial state (a bug found and fixed while building this scenario, see [ADR 0007](../adr/0007-autonomous-agent-telemetry.md)).

## A. Transient failure, recovered by retry (n8n Workflow B, execution #39)

Two Jira failures injected, then a signed monitoring alert: “Payments gateway returning 503 errors for all users”.

| Step | Attempt | Offset | Result |
|---|---|---|---|
| Categorize | 1 | +1 ms | P1 `technical_outage`, team `sre` |
| Retrieve Context | 1 | +48 ms | |
| Assign Owner | 1 | +76 ms | on-call operator with the fewest open cases |
| Create Jira Task | 1 | +114 ms | **failed** — `[simulator] injected transient failure for 'jira'` → HTTP 503 |
| Create Jira Task | 2 | +3,166 ms | **failed** |
| Create Jira Task | 3 | +6,220 ms | succeeded → `OPS-1006`, read back and verified |
| Notify Slack | 1 | +6,269 ms | `SLK-1012`, verified |
| Incident Routed | 1 | +6,304 ms | run finished |

Case #1014 ends with exactly **one** verified Jira action and one Slack action; the two failed attempts appear as failed `action-executor` runs in agent mission control. The case stays `investigating` because creating a ticket does not resolve an incident.

**How this scenario found a bug.** The first time it ran (execution #6, before the fix) the simulator's failure counter committed the request's transaction while the action was mid-flight. The retry succeeded, but two half-executed `create_jira_issue` rows were left in state `executing` on case #1002 and the case never settled. The counter now uses its own session with an atomic update, agent telemetry is written autonomously, and the evaluation suite asserts “503, 503, 200 and exactly one verified action” on every run.

## B. Retries exhausted → dead letter → replay (executions #27 and #29)

Six (later four) Slack failures injected — more than the node's four tries.

1. n8n retried *Notify Slack* four times, then failed the execution (9.2 s).
2. The workspace error workflow (Z) posted to `/workflow-events/error`. The API looked up the run by n8n execution id, attached the case id and the failing node, marked the run failed, and raised a critical notification.
3. After clearing the injected failures, an admin replayed the dead letter from *Observability → Incident explorer*. The API mapped the failed node to its action (`post_slack_message`), executed it once (`SLK-1005`), verified it and closed the dead letter. Operators get 403 on replay; the replay is audited.

## C. Idempotency under redelivery

- The same email Message-ID delivered again returns the existing case (`duplicate: true, reason: idempotency_key`).
- A resend with a new Message-ID but the same sender/subject/body (“RE: …”) is caught by content dedup (`reason: content`).
- The evaluation suite repeats this three times plus a resend and asserts one case.

## D. Auditability

Every step above is in the hash-chained audit log with the n8n execution id. Tampering with one historical row (`UPDATE audit_events SET data = … WHERE seq = 10`) made `GET /audit/verify` report `{"valid": false, "broken_at_seq": 10}`; reverting it restored `valid: true`.

## Measured, overall (development session)

From `/analytics/overview` at the end of the session: 31 workflow runs, 85% success (the failures are the deliberate dead-letter scenarios above), p50 0.56 s, p95 128.8 s (dominated by executions waiting for a human approval), approval turnaround 1.3 min average, RFP upload-to-draft 11.7 s average (including the earlier runs before n8n was started).
