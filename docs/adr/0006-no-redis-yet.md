# ADR 0006 — Redis for shared cache and rate limits (supersedes "No Redis yet")

**Status:** accepted (revised). The original decision was "no Redis"; its stated trigger, more than one API process, has now happened.

**Context.** The API now runs several uvicorn workers (`WEB_CONCURRENCY`) and is meant to run as several replicas. An in-process rate limiter lets each worker apply its own limit, and an in-process cache means every worker recomputes the same dashboard.

**Decision.** Add a small Redis (64 MB, `allkeys-lru`) used for exactly two things:
- per-user fixed-window rate limits, plus login throttling by IP and by e-mail;
- a short-TTL, single-flight, stale-while-revalidate read cache for the workspace-wide views every open page polls (dashboard, analytics, case/approval/notification lists, workflows, integrations).

Queuing, retries and scheduling stay with n8n. Idempotency stays a PostgreSQL unique constraint. Redis holds nothing that cannot be lost: if it is unreachable, the API falls back to in-process limits and cache and keeps serving.

**Consequences.** One more container (about 10 MB RSS). Cached reads can be up to a few seconds stale, and writes that matter for the reader (approval decisions, notification reads) invalidate their keys immediately.
