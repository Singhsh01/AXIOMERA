# ADR 0001 — Modular monolith

**Status:** accepted

**Context.** Two business domains (operations, proposals) share identity, approvals, audit, agents and workflow tracking. The target machine is an 8 GB laptop.

**Decision.** One FastAPI service with strict module boundaries: `platform` provides shared services; `ops` and `rfp` depend on `platform` but never on each other.

**Consequences.** One deployable, one database transaction per request (important for approval + action + audit atomicity), low memory use. Splitting a domain into its own service later is mechanical because its only dependencies are platform interfaces. The cost is that a crash takes down both domains.
