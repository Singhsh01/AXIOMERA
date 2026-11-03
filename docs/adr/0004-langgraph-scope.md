# ADR 0004 — LangGraph only where the control flow is genuinely a graph

**Status:** accepted

**Context.** Most stages are linear and already sequenced by n8n. Wrapping them in an agent framework would add a second orchestrator.

**Decision.** Use LangGraph for the resolution stage, which has real conditional loops: plan → check evidence → (gather, bounded) → plan; draft → validate → (redraft, bounded) → finalize | escalate. Everything else is plain Python inside the agent runtime.

**Consequences.** One place with cyclic agent control flow, with explicit recursion limits and budgets; no framework lock-in elsewhere.
