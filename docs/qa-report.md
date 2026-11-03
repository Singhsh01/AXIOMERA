# QA report

**Scope:** functional, role-based, security and UX acceptance of the full stack (Next.js web, FastAPI, n8n 1.x with workflows A–E, PostgreSQL + pgvector, Redis), plus a load test.
**Approach:** business use cases driven through the real UI with Playwright (`qa/e2e.py`), API assertions for the rules behind each screen, the backend unit/integration suite, and a load test (`scripts/loadtest.py`, see [scalability.md](scalability.md)).
**Date:** 2026-11-03. **Build:** this repository at the commit containing this file.

## Summary

| Layer | Result |
|---|---|
| End-to-end use cases (`python qa/e2e.py --theme light\|dark`) | **18 / 18 pass in the light theme and 18 / 18 in the dark theme** (after fixes below); raw output in [`qa/results-light.json`](../qa/results-light.json) and [`qa/results-dark.json`](../qa/results-dark.json), evidence for both themes in [`qa/screens`](../qa/screens) |
| Backend suite (`cd backend && pytest`) | **81 / 81 pass** |
| Page renders checked for console and server errors | 55 (11 pages × 5 roles), 0 errors |
| Load test | 500 concurrent users 100 % success, p95 48–84 ms; 1,000–2,000 users 99.9 % success with graceful degradation on a 2-vCPU box ([details](scalability.md)) |

## Test cases

| ID | Use case | Role(s) | Result | Evidence |
|---|---|---|---|---|
| AUTH-01 | Valid sign-in lands on the command center | operator | pass | `auth-01-command-center` |
| AUTH-02 | Wrong password refused with a clear message, no session | anonymous | pass | `auth-02-bad-password` |
| AUTH-03 | 5 wrong passwords → locked (423) even with the right password; admin unlocks from the Access log | viewer, admin | pass | `auth-03-locked-account` |
| AUTH-04 | Sign-in history lists every attempt (result, IP, device); the organisation log is 403 for non-admins | viewer | pass | `auth-04-access-log` |
| AUTH-05 | Sign-out ends the session; protected pages redirect to sign-in | operator | pass | — |
| UC-01 | **Refund journey**: email → n8n Workflow A → triage, evidence, proposed €149 refund + reply → two approvals → approver approves → Workflow E executes and verifies → case resolved. Operator's attempt to decide is refused (403) | operator → approver | pass | `uc-01a…d` |
| UC-02 | Prompt-injection email is flagged, nothing executes | operator | pass | `uc-02-injection-flagged` |
| UC-03 | Approval scope binding (changed parameters block execution) | backend tests | pass | covered by `test_platform_units.py`; not reachable through the public API by design |
| UC-04 | RFP workspace: 24 requirements, evidence panel, proposal tab | reviewer | pass | `uc-04a/b` |
| UC-05 | Workflow studio: n8n graph renders, node definition opens in the editor | operator | pass | `uc-05-workflow-studio` |
| UC-06 | Policies: read-only for non-admins; an unsafe policy is rejected (422); a valid one saves | operator, admin | pass | `uc-06-policies` |
| UC-07 | Knowledge base hybrid search returns refund-policy passages | operator | pass | `uc-07-knowledge` |
| UC-08 | Every app page renders for every role without console or 5xx errors | all 5 roles | pass | — |
| UC-09 | Viewer cannot write: no write buttons; API returns 403 | viewer | pass | — |
| UC-10 | Audit hash chain verifies end to end | admin | pass | `valid: true` |
| UX-01 | Landing: stakeholder navigation, no horizontal scroll at 390 px | anonymous | pass | `ux-01-*` |
| UX-02 | App shell fits a 390 px phone | operator | pass | `ux-02-app-mobile` |
| UX-03 | Theme switch: light ↔ dark, persists across navigation and reload, heading moves 0 px | operator | pass | `ux-03-theme-*` |

## Defects found and fixed

| # | Severity | Defect | Found by | Fix |
|---|---|---|---|---|
| D-1 | **High** | Under 500+ concurrent users the API deadlocked (thread pool vs DB pool), giving 31 % success at 500 and 0 % at 1,000 | load test | Admission control (in-flight cap below pool size, then `503 Retry-After`), single-flight cache, indexes, eager loading ([scalability.md](scalability.md)) |
| D-2 | **High** | Policy and workflow JSON editors loaded Monaco from a public CDN; on offline or firewalled corporate networks they never appeared | UC-08 console errors | Monaco is served by the app (`/monaco/vs`, copied at build) via a shared `CodeEditor` component |
| D-3 | Medium | Runs whose process died stayed "running" forever, inflating "in progress" and skewing success rates | screenshot review | `sweep_stale_runs()` runs inside hourly Workflow D; closes runs with no activity for 2 h (agents: 30 min) and leaves runs waiting on approvals alone. Verified live: 8 workflow and 5 agent runs closed, 7 waiting kept |
| D-4 | Medium | First version of D-3 crashed on runs that had steps (a field-name error), so Workflow D failed after 3 n8n retries | live verification after the unit test passed | Fixed; unit test now includes steps. The failed run remains in history as an honest record |
| D-5 | Low | `waiting_in_n8n` stayed `true` after an approval was decided | UC-01 API inspection | Now true only while pending |
| D-6 | Low | Long JSON values (e.g. an e-mail body) overflowed their panel on the case Actions tab | screenshot review | JSON blocks wrap |
| D-7 | Low | Locked accounts could only wait 15 minutes; no admin remedy | AUTH-03 design review | `POST /auth/users/{id}/unlock` (admin, audited) + Unlock button |

Test-script defects (not product defects) were fixed along the way: ambiguous selectors (Next.js route announcer also has `role=alert`; "Approve" matched list items), and API field names (`security_flags` is a list, the case is nested under `approval.case`).

## Redesign regression (Axiomera rebrand, light "Travertine" theme)

The full suite was re-run in both themes after the rebrand and redesign, along with the backend suite (81 / 81), the evaluation suites (unchanged results; only timestamps moved) and a TypeScript check. The landing page was also captured at 1440, 820 and 390 px in both themes.

| # | Severity | Finding | Fix |
|---|---|---|---|
| R-1 | Medium | Light tokens `ink-faint`, `accent` and `warn` measured 4.1–4.5:1 on stone surfaces; the dark primary button had white on violet at 3.3:1 | Tokens adjusted; every text token is now ≥ 5.0:1 in both themes, button text 17.2:1 / 5.5:1 (table in [design-system.md](design-system.md)) |
| R-2 | Medium | On phones the hero copy sat on the busiest part of the render | Full-strength ivory veil below `md`; the gradient veil applies from tablet up |
| R-3 | Low | At 820 px the landing nav wrapped onto two lines | Section links show from `lg`; header items no longer wrap |
| R-4 | Low | Every dark-theme chapter reused the same image | Night-graded variants of each render |
| T-1 | Test | The suite's own re-logins tripped the product's login throttle (10 / min per e-mail) in the second run | Harness reuses one session per user, as a real browser would |
| T-2 | Test | UC-04 raced the requirements table because the new title block shows "Requirements" before the matrix loads | Waits for table rows instead |

Landing weight (light, scrolled to the end): 152 kB first-load JS, 354 kB images; images for the inactive theme are not downloaded. App routes grew by about 3 kB.

## Not covered / known limits

- Cross-browser: Chromium only (Playwright's bundled browser). Safari and Firefox were not run.
- `next lint` is not configured in this repository (it prompts to set up ESLint); type safety is checked with `tsc --noEmit`.
- Accessibility: keyboard focus rings and labels were checked where tests used them (`get_by_label`, roles); no full WCAG audit was done.
- Live third-party connectors (Slack, Jira, HubSpot, payments) were exercised against the labelled simulators only.
- The load test ran the generator on the same 2-vCPU host as the server; see [scalability.md](scalability.md) for how to read the 1,000+ user numbers.

## Re-run

```bash
docker compose up -d                       # or the native stack
pip install playwright httpx && python -m playwright install chromium   # outside the dev container
export ORKESTR_DATABASE_URL=postgresql+psycopg://orkestr:orkestr@localhost:5433/orkestr   # AUTH-03 creates a throwaway user
python qa/e2e.py --web http://localhost:3000 --api http://localhost:8000
```
