# ADR 0003 — Deterministic rules for policy decisions

**Status:** accepted

**Context.** Category, priority, SLA, refund eligibility, which actions need approval and compliance status have audit and fairness consequences. A model can be wrong in ways that are hard to reproduce.

**Decision.** These are rule-based and evaluated against labelled data. Models summarise, extract and draft. Model output never overrides deterministic fields; extracted requirements must be verbatim-locatable; drafted text passes a claim checker; executor and verifier agents use no model at all.

**Consequences.** Reproducible decisions and meaningful regression tests; the system is fully functional offline with fixtures. Rules need maintenance for new categories and languages; the README is explicit that the small labelled sets demonstrate behaviour, not generalisation.
