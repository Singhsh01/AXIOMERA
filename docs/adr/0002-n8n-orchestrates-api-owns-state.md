# ADR 0002 — n8n orchestrates, the API owns state

**Status:** accepted

**Context.** n8n is required to be central and genuinely executing, not decorative. n8n is excellent at triggers, retries, waits and schedules, but storing business state in workflow variables makes idempotency, auditing and authorisation hard.

**Decision.**
- Every business transition is an idempotent API endpoint. n8n calls them in order and owns retries (`retryOnFail`, `maxTries`, back-off), waits (Wait node with resume URL) and schedules.
- The API signals retryability through status codes: 503 for transient connector failures (n8n retries), 4xx for permanent problems (the execution fails and the error workflow files a dead letter).
- Each call carries the n8n execution id, workflow key and node name; the API records steps, so business records link to executions without polling n8n's API.
- If n8n is unreachable, the API runs the same stages in-process and records the run with `trigger = api-fallback`.

**Consequences.** Retries and redeliveries are safe; the workflow studio can render real executions; the system degrades instead of stopping when n8n is down. Workflow logic lives in two places (JSON stage order, API stage semantics), which the generator and CI drift check keep honest.
