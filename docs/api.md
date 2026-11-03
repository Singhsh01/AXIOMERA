# API reference

Generated from the running service (`GET /openapi.json`; interactive docs at `http://localhost:8000/docs`). All routes are under `/api/v1` except `/health` and `/metrics`.

Authentication: users send `Authorization: Bearer <jwt>` (or the `orkestr_token` cookie set by `/auth/login`). n8n sends `X-Orkestr-Service-Token`, plus `X-N8N-Execution-Id`, `X-Orkestr-Workflow` and `X-Orkestr-Node`, which the API records as workflow steps. The service principal can never decide approvals.

## Auth

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/auth/me` | Me |

## Operations

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/cases` | List Cases |
| POST | `/api/v1/cases/intake` | Submit Intake |
| GET | `/api/v1/cases/{case_id}` | Get Case |
| POST | `/api/v1/cases/{case_id}/actions/{action_type}` | Run Internal Action |
| POST | `/api/v1/cases/{case_id}/assign` | Case Assign |
| POST | `/api/v1/cases/{case_id}/classify` | Case Classify |
| POST | `/api/v1/cases/{case_id}/execute` | Case Execute |
| POST | `/api/v1/cases/{case_id}/release-review` | Release Review |
| POST | `/api/v1/cases/{case_id}/research` | Case Research |
| POST | `/api/v1/cases/{case_id}/resolve` | Case Resolve |
| POST | `/api/v1/cases/{case_id}/transition` | Manual Transition |
| POST | `/api/v1/cases/{case_id}/verify` | Case Verify |
| GET | `/api/v1/customers` | Customers |
| POST | `/api/v1/incidents` | Create Incident |
| POST | `/api/v1/ingest/email` | Ingest Email |
| POST | `/api/v1/ops/auto-close` | Auto Close |
| POST | `/api/v1/ops/sla/scan` | Sla Scan |

## Proposals

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/exports/{art_id}/download` | Download |
| GET | `/api/v1/exports/{art_id}/manifest` | Manifest |
| GET | `/api/v1/proposals/{pid}` | Get Proposal |
| POST | `/api/v1/proposals/{pid}/comments` | Add Comment |
| GET | `/api/v1/proposals/{pid}/diff` | Diff |
| POST | `/api/v1/proposals/{pid}/export` | Export |
| POST | `/api/v1/proposals/{pid}/request-review` | Request Review |
| POST | `/api/v1/proposals/{pid}/review` | Review |
| PATCH | `/api/v1/proposals/{pid}/sections/{key}` | Edit Section |
| PATCH | `/api/v1/requirements/{req_id}` | Patch Requirement |
| PATCH | `/api/v1/requirements/{req_id}/compliance` | Patch Compliance |
| POST | `/api/v1/requirements/{req_id}/compliance/accept` | Accept Compliance |
| GET | `/api/v1/rfps` | List Rfps |
| POST | `/api/v1/rfps` | Create Rfp |
| GET | `/api/v1/rfps/deadlines/at-risk` | Deadlines |
| GET | `/api/v1/rfps/{rfp_id}` | Get Rfp |
| POST | `/api/v1/rfps/{rfp_id}/compliance/assess` | Rfp Compliance Assess |
| POST | `/api/v1/rfps/{rfp_id}/compliance/build` | Rfp Compliance Build |
| POST | `/api/v1/rfps/{rfp_id}/documents` | Upload Version |
| GET | `/api/v1/rfps/{rfp_id}/documents/{doc_id}/pages` | Pages |
| GET | `/api/v1/rfps/{rfp_id}/documents/{doc_id}/pages/{page_no}.png` | Page Image |
| POST | `/api/v1/rfps/{rfp_id}/escalate` | Escalate |
| POST | `/api/v1/rfps/{rfp_id}/extract` | Rfp Extract |
| POST | `/api/v1/rfps/{rfp_id}/intake` | Rfp Intake |
| POST | `/api/v1/rfps/{rfp_id}/process` | Process Inline |
| POST | `/api/v1/rfps/{rfp_id}/proposals` | Draft |
| POST | `/api/v1/rfps/{rfp_id}/proposals/{pid}/new-version` | New Version |
| GET | `/api/v1/rfps/{rfp_id}/requirements` | List Requirements |
| POST | `/api/v1/rfps/{rfp_id}/requirements/extract` | Rfp Requirements Extract |
| GET | `/api/v1/rfps/{rfp_id}/requirements/{req_id}/highlight` | Highlight |

## Knowledge

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/knowledge` | List Docs |
| POST | `/api/v1/knowledge` | Upload |
| GET | `/api/v1/knowledge/search` | Search |
| GET | `/api/v1/knowledge/{doc_id}` | Get Doc |
| POST | `/api/v1/knowledge/{doc_id}/approve` | Approve |

## Platform

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/agents/overview` | Agents Overview |
| GET | `/api/v1/agents/runs` | List Agent Runs |
| GET | `/api/v1/agents/runs/{run_id}` | Get Agent Run |
| POST | `/api/v1/agents/runs/{run_id}/cancel` | Cancel Agent Run |
| GET | `/api/v1/analytics/overview` | Analytics |
| GET | `/api/v1/approvals` | List Approvals |
| GET | `/api/v1/approvals/{approval_id}` | Get Approval |
| GET | `/api/v1/approvals/{approval_id}/authorize` | Authorize |
| POST | `/api/v1/approvals/{approval_id}/decision` | Decide |
| POST | `/api/v1/approvals/{approval_id}/execute` | Execute Approval |
| POST | `/api/v1/approvals/{approval_id}/outcome` | Record Outcome |
| POST | `/api/v1/approvals/{approval_id}/register-wait` | Register Wait |
| GET | `/api/v1/audit` | List Audit |
| GET | `/api/v1/audit/verify` | Verify Audit |
| GET | `/api/v1/dashboard/summary` | Dashboard |
| GET | `/api/v1/dead-letters` | List Dead Letters |
| POST | `/api/v1/dead-letters/{dl_id}/replay` | Replay Dead Letter |
| GET | `/api/v1/evals/runs` | Eval Runs |
| GET | `/api/v1/evals/runs/{run_id}` | Eval Run |
| GET | `/api/v1/integrations` | List Integrations |
| PATCH | `/api/v1/integrations/{kind}` | Set Mode |
| POST | `/api/v1/integrations/{kind}/inject-failures` | Inject Failures |
| GET | `/api/v1/integrations/{kind}/records` | Sim Records |
| GET | `/api/v1/notifications` | List Notifications |
| POST | `/api/v1/notifications` | Create Notification |
| POST | `/api/v1/notifications/{nid}/read` | Mark Read |
| GET | `/api/v1/policies/approvals` | Get Policies |
| PUT | `/api/v1/policies/approvals` | Put Policies |
| POST | `/api/v1/workflow-events` | Workflow Event |
| POST | `/api/v1/workflow-events/error` | Workflow Error |
| GET | `/api/v1/workflows` | List Workflows |
| GET | `/api/v1/workflows/runs` | List Runs |
| GET | `/api/v1/workflows/runs/{run_id}` | Get Run |
| GET | `/api/v1/workflows/{key}` | Get Workflow |
| POST | `/api/v1/workflows/{key}/trigger` | Trigger Workflow |
| GET | `/health` | Health |
