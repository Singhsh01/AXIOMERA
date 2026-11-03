# ADR 0005 — Offline feature-hashing embeddings by default

**Status:** accepted

**Context.** Local models are too heavy for an 8 GB laptop alongside PostgreSQL, n8n and Node; hosted embeddings need a key and send company documents to a third party.

**Decision.** Default to a deterministic 384-dimension feature-hashing embedder (word unigrams, bigrams, character trigrams) stored in pgvector, fused with PostgreSQL full-text search via reciprocal rank fusion. `ORKESTR_EMBEDDING_PROVIDER=openai` switches to an OpenAI-compatible embedding endpoint with the same dimension.

**Consequences.** Zero downloads, reproducible results, good lexical-semantic recall on domain vocabulary. Weaker on paraphrase than learned embeddings; the lexical leg and RRF compensate for the evaluated corpus.
