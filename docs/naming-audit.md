# Naming audit: Orkestr → Axiomera

The product was first built as **Orkestr** and renamed **Axiomera**. The first rename pass changed the
brand, UI and copy, but left the old name in demo credentials, environment variables, webhook paths,
HTTP headers, metrics and setup instructions. This audit inventories every remaining reference,
renames everything a user or operator touches, and keeps the old names working where an existing
installation depends on them.

## Scope and method

- `git grep -i orkestr` on the pre-audit commit (`5e106d0`), plus a scan of binary and zipped files
  (PDF metadata, DOCX core properties, images, video).
- Each occurrence was classified as **renamed**, **renamed with compatibility**, or **kept**.
- The change was verified on a database seeded before the rename:
  - backend suite: 87 tests, 6 of them new compatibility tests;
  - end-to-end suite: 19 / 19 use cases in each theme;
  - all three demo case studies sent through the new n8n webhook paths;
  - the API running on legacy `ORKESTR_*` settings only;
  - a refund approval that was waiting in an n8n execution started on the pre-rename workflow, approved after the upgrade: the execution resumed and the refund ran.

| | Occurrences | Files |
|---|---:|---:|
| Before the audit | 830 | 62 |
| After the audit | 76 | 18 |

The 76 left are all deliberate: the compatibility code and its tests, the upgrade notes, and the
legacy header fallback inside each n8n workflow. They are listed under [What is kept](#what-is-kept).

### Where the old name was

| Form | Count | Where |
|---|---:|---|
| `X-Orkestr-*` headers | 478 | n8n workflow JSON (every HTTP node), OpenAPI spec, backend, tests |
| `ORKESTR_*` settings (incl. `$env.ORKESTR_*` in n8n) | 183 | `.env.example`, Compose, Dockerfiles, n8n, CI, scripts, docs |
| Demo accounts `*@orkestr.dev` / password `orkestr-demo` | 57 | seed, login page, scripts, QA, README, docs |
| Webhook paths `orkestr/*` | 24 | n8n workflows, API catalog, scripts, docs |
| `orkestr_*` identifiers (metrics, cookie, test DB) | 19 | observability, auth, CI, tests, docs |
| Database name/user `orkestr` in URLs | 13 | config default, Compose, CI, README, docs |
| Product name in prose, package and service names | ~56 | docs, `package.json`, OTel `service.name`, Prometheus job, MCP server, Jira labels, export metadata |

## What changed

### Renamed with backwards compatibility

The contract lives in one module, `backend/app/core/naming.py`.

| Surface | New | Still accepted | How |
|---|---|---|---|
| Settings | `AXIOMERA_*` | `ORKESTR_*` (env and `.env`) | Copied onto the new name only when the new name is unset; the new name always wins. A startup warning lists every legacy key in use. |
| Inbound headers | `X-Axiomera-Service-Token`, `-Workflow`, `-Node` | `X-Orkestr-*` | Read in `deps.py`, `routers/common.py` and the rate limiter. Hidden from the OpenAPI schema. |
| Signed calls to n8n | `X-Axiomera-Timestamp` / `-Signature` | — | Each call **sends both** header sets, so executions that started before the upgrade still verify when an approval resumes them. |
| n8n signature checks | `x-axiomera-*` | `x-orkestr-*` | Fallback in each workflow's verify code (`?? headers['x-orkestr-…']`). |
| n8n environment | `AXIOMERA_API_URL`, `AXIOMERA_SERVICE_TOKEN`, `AXIOMERA_WEBHOOK_SECRET` | `ORKESTR_*` | Compose also sets the legacy names from the same values, so executions created by old workflow versions still resolve `$env.ORKESTR_*`. |
| Session cookie | `axiomera_session` | `orkestr_token` | Read if the new cookie is absent; logout clears both. Users stay signed in across the upgrade. |
| Web build | `AXIOMERA_API_URL` | `ORKESTR_API_URL` | Fallback in `next.config.mjs`. |
| Demo accounts | `admin\|ops\|approver\|reviewer\|viewer@axiomera.dev` / `axiomera-demo` | — | Alembic migration `0003` renames the accounts **in place**; details below. |

What migration `0003` does to the demo accounts:

- Ids, approvals and audit records stay attached to each account.
- The password changes to `axiomera-demo` only if it is still the old default; a changed password is left alone.
- If an `@axiomera.dev` account already exists, the old one is left untouched.
- Sign-in history keeps the address that was actually used.
- It is reversible.

### Renamed outright

- **n8n webhook paths:** `orkestr/intake`, `/incident`, `/rfp-arrived`, `/deadline-scan` and `/approval-requested` all become `axiomera/…`. This is a breaking change for external senders; see the upgrade steps below.
- **Prometheus metrics:** `orkestr_*` becomes `axiomera_*`:
  - HTTP requests and latency;
  - workflow steps;
  - agent runs and run seconds;
  - tool calls;
  - LLM tokens;
  - approvals;
  - integration calls;
  - duplicate events.

  The Prometheus job is now `axiomera-api`.
- **OpenTelemetry:** `service.name` is `axiomera-api` and the tracer is `axiomera`.
- **Default database:** `axiomera` (URL `postgresql+psycopg://axiomera:axiomera@…/axiomera`). The test database is `axiomera_test`.
- **Containers and packages:**
  - container user `axiomera` (uid unchanged at 10001, so volume ownership is unaffected);
  - web package `axiomera-web`;
  - MCP server name `axiomera`.
- **Labels and metadata:**
  - Jira issue label `axiomera` (written, never queried, so old issues are unaffected);
  - DOCX/PDF export keywords;
  - the sample proposals in `docs/samples`, re-exported through the API (only the date and manifest hash differ).
- **Docs and tooling:**
  - README, every document in `docs/`, `.env.example`;
  - CI, Makefile, demo, load-test and screenshot scripts;
  - QA harness and video scripts;
  - `docs/openapi.json` (regenerated, no legacy names left in it).

### What is kept

| Identifier | Why |
|---|---|
| n8n workflow IDs `OrkA0CustomerIntk` … `OrkZ0ErrorHandler` | Stored in n8n executions, the API's workflow runs and dead letters, and the error-workflow link. Changing them would orphan history and break re-imports. They are internal and never shown as the product name. Display names are now "Axiomera A … Z". |
| Docker Compose project, Postgres user and database for **existing** installs | Docker names volumes after the project (`orkestr_pgdata`, `orkestr_n8ndata`, `orkestr_storage`). Fresh installs use `axiomera`. Existing ones pin the old names in `.env` (below) so they keep their data. A volume can't be renamed in place. |
| Compatibility code, tests and upgrade notes | `naming.py`, the fallbacks listed above, `tests/test_naming_compat.py`, migration `0003`, the legacy n8n env lines in Compose, and the notes in `.env.example`, the README and the design system. |

## Upgrading an installation created before the rename

1. **Keep your data.** Add these lines to `.env`, or the stack starts with new, empty volumes:
   ```
   COMPOSE_PROJECT_NAME=orkestr
   POSTGRES_USER=orkestr
   POSTGRES_DB=orkestr
   ```
2. **Rename settings** from `ORKESTR_` to `AXIOMERA_` in `.env`, keeping the values. This step is optional; the old names still work, with a warning in the API log.
3. **Rebuild and restart:** `docker compose up -d --build --force-recreate`. The API runs `alembic upgrade head` on start, which moves the demo accounts to `@axiomera.dev` / `axiomera-demo`.
4. **n8n workflows:** with Docker Compose, the `n8n-init` service re-imports them on every start, so n8n serves the `axiomera/*` paths. Without Compose, re-import `n8n/workflows` yourself.
5. **Point external senders** that post straight to n8n at `/webhook/axiomera/<name>`. Senders can keep `X-Orkestr-*` signature headers for now.
6. **Update dashboards and alerts** that query `orkestr_*` metrics or the `orkestr-api` service name.

Approvals already waiting in n8n when you upgrade resume normally.

## Removing the compatibility layer

The shims are small and isolated. Once no installation needs them, which needs one release where the
startup warning has stayed silent:

- delete the legacy constants and fallbacks in `naming.py`, `deps.py`, `routers/common.py`, `main.py` and `next.config.mjs`;
- drop the `?? x-orkestr-*` fallback in `n8n/build_workflows.py` and regenerate the workflows;
- remove the legacy `ORKESTR_*` lines from the n8n service in `docker-compose.yml`;
- delete `tests/test_naming_compat.py`;
- keep migration `0003`, because migrations are history.

The workflow IDs and the Compose pins for old volumes stay for as long as those installations exist.
