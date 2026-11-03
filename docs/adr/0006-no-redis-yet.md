# ADR 0006 — No Redis (yet)

**Status:** accepted

**Context.** Redis is commonly added for queues, caching and rate limiting.

**Decision.** Not included. Queuing, retries and scheduling are n8n's job; idempotency is a PostgreSQL unique constraint; rate limiting is in-process because the API runs as a single instance.

**Consequences.** One fewer service on an 8 GB machine. When running more than one API replica, move rate limiting (and SSE fan-out if added) to Redis; that is the trigger to revisit this ADR.
