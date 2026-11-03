# ADR 0007 — Agent telemetry is an autonomous write

**Status:** accepted (found by testing)

**Context.** Agent runs and tool calls were initially written in the request's transaction. When an executor hit a transient connector failure, the transaction rolled back and the failed run disappeared, so observability under-reported failures. A related bug (the simulator's failure counter committing the caller's transaction) leaked a half-executed action.

**Decision.** `AgentExecution` writes `agent_runs` and `tool_calls` through its own session and commits at each checkpoint. Simulator side effects also use an independent session with an atomic SQL update.

**Consequences.** Failed runs are always visible; business state still rolls back atomically. A run may reference an entity id whose row was rolled back — acceptable for telemetry and documented here.
