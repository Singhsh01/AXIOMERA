# Evaluation

```bash
cd backend && python -m evals.run_evals            # all suites
python -m evals.run_evals --suite rfp               # one suite
```

Results go to `backend/evals/results/<suite>.json` (full per-item results) and `summary.json` (copied to the web app's landing page), and are stored as `eval_runs` rows shown under *Observability → Analytics*. Each case runs inside a database transaction that is rolled back.

## Suites

**Operations** (`datasets/cases.jsonl`, 36 messages: 29 ordinary, 7 adversarial)
- classification and priority accuracy against labels (rules only);
- prompt-injection recall and false-positive rate;
- full triage → research → resolution pipeline per message: share of consequential actions that are pending an approval (must be 100%), and injected messages held in `needs_review` with zero actions;
- duplicate handling through the API (three idempotent replays + a content-level resend);
- recovery after transient failure: two injected Jira failures must produce `503, 503, 200` and exactly one verified Jira action (no double execution).

**RFP** (`datasets/rfp_lindenfeld_truth.json`, 24 hand-labelled requirements)
- extraction precision and recall; obligation and category accuracy; deadline recall;
- compliance-matrix accuracy vs. labels; compliant items whose first evidence passage has ≥ 60 % key-term coverage or is a certificate;
- poisoned twin document: matrix must be identical and the injected instruction flagged;
- DOCX export checks: status line, TOC, numbered sections, matrix table size, metadata, page-number footer, evidence-manifest hashes;
- claim checker on `datasets/claims.json` (5 supported, 5 unsupported claims).

**Agents**
- unpermitted tools denied; invalid tool arguments rejected; tool-call budget enforced;
- consequential tool without approval blocked; provider failure falls back to the deterministic path and is labelled;
- untrusted content flagged; hallucinated (non-locatable) requirement quotes rejected;
- **LLM-as-judge** rubric scoring of customer replies — runs only with a live provider, otherwise reported as `skipped`.

## Latest results

Deterministic fixtures (`AXIOMERA_LLM_PROVIDER=fixture`). See `backend/evals/results/*.json` for timestamps and per-item detail.

| Metric | Result |
|---|---|
| Classification / priority accuracy | 100% / 100% (29 messages) |
| Injection recall / false positives | 100% (7/7) / 0% |
| Consequential actions gated | 49 / 49 |
| Duplicate suppression; retry recovery without double execution | pass; pass |
| Requirement extraction precision / recall | 100% / 100% (24) |
| Obligation / category / compliance accuracy | 100% / 100% / 100% |
| Deadline recall | 3 / 3 |
| Export checks | 7 / 7 |
| Unsupported claims caught / false flags | 5 of 5 / 0 |
| Poisoned tender changed the matrix | no |
| Agent safety checks | 7 / 7 |
| LLM-as-judge | skipped (no key) |

## How to read this

- The datasets are **small and were written alongside the rules they test**. Perfect scores mean the system does what it was designed to do on these cases; they are not evidence of generalisation to real inboxes or real tenders. Extend the datasets with real (anonymised) material before trusting the numbers.
- The suites found two real defects during development: the tool-call budget allowed one call too many, and a recovery probe was not unique (so a second run was correctly deduplicated and looked like a failure). Both are fixed; the first is covered by a regression test.
- With a live model, extraction and drafting results will differ run to run; the deterministic guards (verbatim quotes, claim checker, deterministic policy fields) are what keep those differences from reaching decisions.
