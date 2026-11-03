# ADR 0008 — Simulators by default, live adapters behind the same interface

**Status:** accepted

**Context.** Demos must be reproducible without credentials, and a portfolio project must never pass off a mock as a live connection.

**Decision.** Every connector implements `execute / fetch / health`. Simulators persist records with idempotency keys and support failure injection; every response carries `mode: simulator` and the UI labels it. Live adapters (Slack incoming webhook, Jira Cloud REST v3, HubSpot CRM v3) are used only when credentials are present *and* an admin switches the connection to live. Payments are simulator-only by design.

**Consequences.** Retry, recovery and dead-letter paths are demonstrable on demand. Live adapters are implemented against public APIs but were not exercised against real accounts in this repository.
