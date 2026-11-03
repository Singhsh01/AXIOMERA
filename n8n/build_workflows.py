"""Generates the version-controlled n8n workflow definitions in ./workflows.

The JSON files are the artefacts n8n imports; this script exists so that every workflow uses
the same authentication headers, retry policies, timeouts and error-workflow wiring.
Run: python n8n/build_workflows.py   (then commit the JSON)
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "workflows"
NS = uuid.UUID("6f1c3d1e-6a8b-4e5a-9c2e-0b7f0a0d4e11")
IDS = {"A": "OrkA0CustomerIntk", "B": "OrkB0IncidentEscl", "C": "OrkC0RfpProcessng", "D": "OrkD0DeadlineMntr", "E": "OrkE0ApprovalAudt", "Z": "OrkZ0ErrorHandler"}
API = "={{ $env.ORKESTR_API_URL }}/api/v1"

VERIFY_JS = r"""// Verify the HMAC signature of the incoming webhook (timestamp + '.' + raw body).
const crypto = require('crypto');
const item = $input.first();
const headers = item.json.headers || {};
const ts = headers['x-orkestr-timestamp'];
const sig = headers['x-orkestr-signature'];
let raw;
try { raw = await this.helpers.getBinaryDataBuffer(0, 'data'); }
catch (e) { raw = Buffer.from(JSON.stringify(item.json.body ?? {})); }
const secret = $env.ORKESTR_WEBHOOK_SECRET;
const now = Math.floor(Date.now() / 1000);
let valid = false; let reason = '';
if (!ts || !sig) reason = 'missing signature headers';
else if (Math.abs(now - parseInt(ts, 10)) > 300) reason = 'timestamp outside tolerance';
else {
  const expected = crypto.createHmac('sha256', secret).update(ts + '.').update(raw).digest('hex');
  valid = expected.length === sig.length && crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sig));
  if (!valid) reason = 'signature mismatch';
}
let body = item.json.body;
if (!body || typeof body !== 'object' || Object.keys(body).length === 0) { try { body = JSON.parse(raw.toString('utf8')); } catch (e) { body = {}; } }
return [{ json: { valid, reason, status: valid ? 200 : 401, payload: body,
  correlation_id: body.correlation_id || headers['x-correlation-id'] || String($execution.id),
  workspace_id: body.workspace_id || '' } }];"""

VALIDATE_EMAIL_JS = r"""// Validate the intake payload shape before it reaches the API.
const v = $input.first().json;
if (!v.valid) return [{ json: v }];
const p = v.payload || {};
const missing = ['message_id', 'from', 'subject', 'body'].filter(k => !p[k] || String(p[k]).trim() === '');
const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(p.from || '');
if (missing.length || !emailOk) {
  return [{ json: { ...v, valid: false, status: 422, reason: missing.length ? 'missing fields: ' + missing.join(', ') : 'invalid sender address' } }];
}
return [{ json: { ...v, payload: { message_id: String(p.message_id).slice(0, 200), from: p.from.trim().toLowerCase(),
  subject: String(p.subject).slice(0, 500), body: String(p.body).slice(0, 50000), correlation_id: v.correlation_id } } }];"""

VERIFY_RESUME_JS = r"""// The decision callback is signed as HMAC(ts + '.' + approval_id + '.' + decision).
// Authorisation itself is re-checked against the database by the next node.
const crypto = require('crypto');
const item = $input.first().json;
const h = item.headers || {};
const b = item.body || {};
const req = $('Normalize Request').first().json;
if (!b.approval_id) return [{ json: { approval_id: req.approval_id, resumed_by: 'timeout' } }];
const expected = crypto.createHmac('sha256', $env.ORKESTR_WEBHOOK_SECRET).update(`${h['x-orkestr-timestamp']}.${b.approval_id}.${b.decision}`).digest('hex');
const ok = !!h['x-orkestr-signature'] && expected === h['x-orkestr-signature'] && b.approval_id === req.approval_id;
if (!ok) throw new Error('Approval callback signature invalid');
return [{ json: { approval_id: req.approval_id, decision: b.decision, resumed_by: 'decision' } }];"""


def nid(wf: str, name: str) -> str:
    return str(uuid.uuid5(NS, f"{wf}:{name}"))


class WF:
    def __init__(self, key: str, name: str, description: str):
        self.key, self.name, self.description = key, name, description
        self.nodes: list[dict] = []
        self.connections: dict[str, dict] = {}

    def add(self, node: dict, x: int, y: int) -> str:
        node.setdefault("id", nid(self.key, node["name"]))
        node["position"] = [x, y]
        self.nodes.append(node)
        return node["name"]

    def link(self, src: str, dst: str, branch: int = 0) -> None:
        outs = self.connections.setdefault(src, {"main": []})["main"]
        while len(outs) <= branch:
            outs.append([])
        outs[branch].append({"node": dst, "type": "main", "index": 0})

    def chain(self, *names: str) -> None:
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    def version_id(self) -> str:
        # Content-addressed: n8n resolves the active version by versionId, so it must change whenever the workflow does.
        body = json.dumps({"n": self.nodes, "c": self.connections}, sort_keys=True)
        return str(uuid.uuid5(NS, f"{self.key}:{hashlib.sha256(body.encode()).hexdigest()}"))

    def dump(self) -> dict:
        settings = {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveDataErrorExecution": "all",
                    "saveManualExecutions": True, "callerPolicy": "workflowsFromSameOwner", "executionTimeout": 900}
        if self.key != "Z":
            settings["errorWorkflow"] = IDS["Z"]
        return {"id": IDS[self.key], "name": f"Orkestr {self.key} — {self.name}", "active": self.key != "Z", "nodes": self.nodes,
                "connections": self.connections, "settings": settings, "pinData": {}, "versionId": self.version_id(),
                "meta": {"templateCredsSetupCompleted": True}, "tags": [],
                "staticData": None}


def headers(wf: str, node: str, corr: str | None) -> list[dict]:
    h = [{"name": "X-Orkestr-Service-Token", "value": "={{ $env.ORKESTR_SERVICE_TOKEN }}"},
         {"name": "X-N8N-Execution-Id", "value": "={{ $execution.id }}"},
         {"name": "X-Orkestr-Workflow", "value": wf}, {"name": "X-Orkestr-Node", "value": node}]
    if corr:
        h.append({"name": "X-Correlation-Id", "value": corr})
    return h


def http(wf: str, name: str, method: str, path: str, *, body: str | None = None, corr: str | None = None, retries: int = 3,
         wait_ms: int = 2000, timeout: int = 30000, notes: str | None = None, continue_on_fail: bool = False, once: bool = False) -> dict:
    params: dict = {"method": method, "url": f"{API}{path}", "sendHeaders": True,
                    "headerParameters": {"parameters": headers(wf, name, corr)}, "options": {"timeout": timeout}}
    if body is not None:
        params.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    n = {"name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "parameters": params,
         "retryOnFail": retries > 1, "maxTries": retries, "waitBetweenTries": wait_ms}
    if notes:
        n["notes"], n["notesInFlow"] = notes, True
    if continue_on_fail:
        n["onError"] = "continueRegularOutput"
    if once:
        n["executeOnce"] = True
    return n


def webhook(wf: str, name: str, path: str, respond: str = "responseNode") -> dict:
    return {"name": name, "type": "n8n-nodes-base.webhook", "typeVersion": 2, "webhookId": nid(wf, "hook:" + path),
            "parameters": {"httpMethod": "POST", "path": path, "responseMode": respond, "options": {"rawBody": True}}}


def code(name: str, js: str) -> dict:
    return {"name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "parameters": {"mode": "runOnceForAllItems", "jsCode": js}}


def if_true(name: str, expr: str) -> dict:
    return {"name": name, "type": "n8n-nodes-base.if", "typeVersion": 2, "parameters": {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                       "conditions": [{"id": str(uuid.uuid5(NS, name)), "leftValue": expr, "rightValue": "",
                                       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                       "combinator": "and"}, "options": {}}}


def respond(name: str, body: str, code_expr: str | int = 200) -> dict:
    return {"name": name, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
            "parameters": {"respondWith": "json", "responseBody": body, "options": {"responseCode": code_expr}}}


def split(name: str, field: str) -> dict:
    return {"name": name, "type": "n8n-nodes-base.splitOut", "typeVersion": 1, "parameters": {"fieldToSplitOut": field, "options": {}}}


def schedule(name: str, minutes: int) -> dict:
    return {"name": name, "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
            "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": minutes}]}}}


def report(wf: str, name: str, status: str, corr: str, entity: str = "", finish: bool = True, detail: str = "{}", once: bool = True) -> dict:
    body = ("={{ JSON.stringify({ workflow: '%s', node: '%s', status: '%s', correlation_id: %s, finish: %s, %s detail: %s }) }}"
            % (wf, name, status, corr.strip("={} "), "true" if finish else "false", entity, detail))
    return http(wf, name, "POST", "/workflow-events", body=body, corr=corr, retries=3, once=once)


def sticky(wf: WF, text: str, x: int, y: int, w: int = 420, h: int = 180) -> None:
    wf.add({"name": f"Note {len(wf.nodes)}", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "parameters": {"content": text, "width": w, "height": h}}, x, y)


# =========================================================================== A
def workflow_a() -> WF:
    w = WF("A", "Customer Request Intake", "Email/Webhook → Validate → Deduplicate → Create Case → Classify → Retrieve Evidence → Propose Resolution → Approval → Execute → Verify → Notify")
    C = "={{ $('Verify Signature').first().json.correlation_id }}"
    CASE = "$('Create Case').first().json.case_id"
    sticky(w, "## Workflow A — Customer Request Intake\nSigned email/portal/webhook events become cases. The Orkestr API is the source of truth; "
              "this workflow sequences the stages, retries transient failures and hands consequential actions to Workflow E for human approval.", 0, -260, 620)
    w.add(webhook("A", "Intake Webhook", "orkestr/intake"), 0, 0)
    w.add(code("Verify Signature", VERIFY_JS), 220, 0)
    w.add(code("Validate Payload", VALIDATE_EMAIL_JS), 440, 0)
    w.add(if_true("Is Valid?", "={{ $json.valid }}"), 660, 0)
    w.add(respond("Reject", "={{ JSON.stringify({ accepted: false, reason: $json.reason }) }}", "={{ $json.status }}"), 880, 200)
    w.add(http("A", "Create Case", "POST", "/ingest/email", corr=C, retries=4, wait_ms=3000,
               body="={{ JSON.stringify($('Validate Payload').first().json.payload) }}",
               notes="Idempotent on Message-ID; content-level dedup for resends"), 880, 0)
    w.add(if_true("Duplicate?", "={{ $json.duplicate }}"), 1100, 0)
    w.add(respond("Respond Duplicate", "={{ JSON.stringify({ accepted: true, duplicate: true, case_number: $json.number }) }}", 200), 1320, 200)
    w.add(respond("Respond Accepted", "={{ JSON.stringify({ accepted: true, case_number: $json.number, case_id: $json.case_id, execution_id: $execution.id }) }}", 202), 1320, 0)
    w.add(report("A", "Duplicate Suppressed", "succeeded", C, f"entity_type: 'case', entity_id: {CASE},", detail="{ reason: $('Create Case').first().json.reason }"), 1540, 200)
    w.add(http("A", "Classify", "POST", "/cases/{{ %s }}/classify" % CASE, corr=C), 1540, 0)
    w.add(if_true("Continue Automation?", "={{ $json.next === 'research' }}"), 1760, 0)
    w.add(report("A", "Held For Human Review", "succeeded", C, f"entity_type: 'case', entity_id: {CASE},", detail="{ reason: $('Classify').first().json.next }"), 1980, 200)
    w.add(http("A", "Retrieve Evidence", "POST", "/cases/{{ %s }}/research" % CASE, corr=C), 1980, 0)
    w.add(http("A", "Propose Resolution", "POST", "/cases/{{ %s }}/resolve" % CASE, corr=C, timeout=60000), 2200, 0)
    w.add(http("A", "Execute", "POST", "/cases/{{ %s }}/execute" % CASE, corr=C, retries=4, wait_ms=3000,
               notes="Runs only actions approved by policy (internal, low-risk). Consequential actions wait for E."), 2420, 0)
    w.add(http("A", "Verify", "POST", "/cases/{{ %s }}/verify" % CASE, corr=C), 2640, 0)
    w.add(if_true("Needs Approval?", "={{ $('Propose Resolution').first().json.needs_approval }}"), 2860, 0)
    w.add(code("Approval Items", "const r = $('Propose Resolution').first().json;\nreturn r.approvals.map(id => ({ json: { approval_id: id, case_id: r.case_id, correlation_id: r.correlation_id } }));"), 3080, -120)
    w.add({"name": "Request Approval (Workflow E)", "type": "n8n-nodes-base.executeWorkflow", "typeVersion": 1.2,
           "parameters": {"source": "database", "workflowId": {"__rl": True, "value": IDS["E"], "mode": "id"}, "mode": "each",
                          "options": {"waitForSubWorkflow": False}},
           "notes": "Reusable sub-workflow: each approval waits independently for a human decision", "notesInFlow": True}, 3300, -120)
    w.add(http("A", "Notify Awaiting Approval", "POST", "/notifications", corr=C, continue_on_fail=True, once=True,
               body="={{ JSON.stringify({ title: `Case #${$('Create Case').first().json.number} awaiting approval`, body: $('Propose Resolution').first().json.rationale, severity: 'warning', link: `/app/cases/${$('Create Case').first().json.case_id}` }) }}"), 3520, -120)
    w.add(http("A", "Notify Resolved", "POST", "/notifications", corr=C, continue_on_fail=True,
               body="={{ JSON.stringify({ title: `Case #${$('Create Case').first().json.number} ${$('Verify').first().json.status}`, body: $('Propose Resolution').first().json.rationale, severity: 'info', link: `/app/cases/${$('Create Case').first().json.case_id}` }) }}"), 3080, 120)
    w.add(report("A", "Complete", "succeeded", C, f"entity_type: 'case', entity_id: {CASE},"), 3740, 0)
    w.chain("Intake Webhook", "Verify Signature", "Validate Payload", "Is Valid?")
    w.link("Is Valid?", "Create Case", 0)
    w.link("Is Valid?", "Reject", 1)
    w.chain("Create Case", "Duplicate?")
    w.link("Duplicate?", "Respond Duplicate", 0)
    w.link("Respond Duplicate", "Duplicate Suppressed")
    w.link("Duplicate?", "Respond Accepted", 1)
    w.chain("Respond Accepted", "Classify", "Continue Automation?")
    w.link("Continue Automation?", "Retrieve Evidence", 0)
    w.link("Continue Automation?", "Held For Human Review", 1)
    w.chain("Retrieve Evidence", "Propose Resolution", "Execute", "Verify", "Needs Approval?")
    w.link("Needs Approval?", "Approval Items", 0)
    w.link("Needs Approval?", "Notify Resolved", 1)
    w.chain("Approval Items", "Request Approval (Workflow E)")
    w.link("Request Approval (Workflow E)", "Notify Awaiting Approval")
    w.link("Notify Awaiting Approval", "Complete")
    w.link("Notify Resolved", "Complete")
    return w


# =========================================================================== E
def workflow_e() -> WF:
    w = WF("E", "Approval & Audit", "Approval Request → Send Notification → Wait for Authorized Decision → Verify Identity and Scope → Execute or Reject → Record Outcome")
    C = "={{ $('Normalize Request').first().json.correlation_id }}"
    A = "$('Normalize Request').first().json.approval_id"
    sticky(w, "## Workflow E — Approval & Audit\nWaits (up to 72h) for a human decision recorded in Orkestr. On resume it re-verifies the decider's identity, role "
              "and the scope hash against the database before executing. Every step is written to the hash-chained audit log.", 0, -300, 640)
    w.add({"name": "From Workflow A", "type": "n8n-nodes-base.executeWorkflowTrigger", "typeVersion": 1.1, "parameters": {"inputSource": "passthrough"}}, 0, -60)
    w.add(webhook("E", "Approval Webhook", "orkestr/approval-requested", respond="onReceived"), 0, 160)
    w.add(code("Verify Signature", VERIFY_JS), 220, 160)
    w.add(if_true("Signature Valid?", "={{ $json.valid }}"), 440, 160)
    w.add({"name": "Stop: Invalid Signature", "type": "n8n-nodes-base.stopAndError", "typeVersion": 1, "parameters": {"errorMessage": "Invalid webhook signature"}}, 660, 320)
    w.add(code("Normalize Request", "const j = $input.first().json;\nconst p = j.payload || j;\nreturn [{ json: { approval_id: p.approval_id, case_id: p.case_id || null, correlation_id: p.correlation_id || j.correlation_id || String($execution.id) } }];"), 660, 40)
    w.add(http("E", "Send Notification", "POST", "/approvals/{{ %s }}/register-wait" % A, corr=C,
               body="={{ JSON.stringify({ resume_url: $execution.resumeUrl }) }}", notes="Notifies approvers and registers this execution's resume URL"), 880, 40)
    w.add(if_true("Already Decided?", "={{ $json.already_decided }}"), 1100, 40)
    w.add({"name": "Wait for Authorized Decision", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "webhookId": nid("E", "wait"),
           "parameters": {"resume": "webhook", "httpMethod": "POST", "limitWaitTime": True, "limitType": "afterTimeInterval",
                          "resumeAmount": 72, "resumeUnit": "hours", "options": {}}}, 1320, 160)
    w.add(code("Verify Callback", VERIFY_RESUME_JS), 1540, 160)
    w.add(http("E", "Verify Identity and Scope", "GET", "/approvals/{{ %s }}/authorize" % A, corr=C), 1760, 40)
    w.add(if_true("Authorized?", "={{ $json.authorized }}"), 1980, 40)
    w.add(http("E", "Execute Approved Action", "POST", "/approvals/{{ %s }}/execute" % A, corr=C, retries=4, wait_ms=4000, timeout=60000,
               notes="Idempotent; transient connector failures (HTTP 503) are retried"), 2200, -60)
    w.add(http("E", "Notify Outcome", "POST", "/notifications", corr=C, continue_on_fail=True,
               body="={{ JSON.stringify({ title: `Approved action executed (case #${$json.case_number})`, body: `Case status: ${$json.case_status}`, severity: 'info', slack_channel: '#ops-approvals' }) }}"), 2420, -60)
    w.add(http("E", "Record Outcome", "POST", "/approvals/{{ %s }}/outcome" % A, corr=C,
               body="={{ JSON.stringify({ outcome: 'executed', detail: { verification: $('Execute Approved Action').first().json.verification } }) }}"), 2640, -60)
    w.add(http("E", "Record Rejection", "POST", "/approvals/{{ %s }}/outcome" % A, corr=C,
               body="={{ JSON.stringify({ outcome: $('Verify Identity and Scope').first().json.status, detail: { reasons: $('Verify Identity and Scope').first().json.reasons } }) }}"), 2200, 160)
    w.link("From Workflow A", "Normalize Request")
    w.chain("Approval Webhook", "Verify Signature", "Signature Valid?")
    w.link("Signature Valid?", "Normalize Request", 0)
    w.link("Signature Valid?", "Stop: Invalid Signature", 1)
    w.chain("Normalize Request", "Send Notification", "Already Decided?")
    w.link("Already Decided?", "Verify Identity and Scope", 0)
    w.link("Already Decided?", "Wait for Authorized Decision", 1)
    w.chain("Wait for Authorized Decision", "Verify Callback", "Verify Identity and Scope", "Authorized?")
    w.link("Authorized?", "Execute Approved Action", 0)
    w.link("Authorized?", "Record Rejection", 1)
    w.chain("Execute Approved Action", "Notify Outcome", "Record Outcome")
    return w


# =========================================================================== B
def workflow_b() -> WF:
    w = WF("B", "Enterprise Incident Escalation", "Incident Event → Categorize → Retrieve Context → Assign Owner → Create Jira Task → Notify Slack → Monitor SLA → Escalate → Close")
    C = "={{ $('Verify Signature').first().json.correlation_id }}"
    CASE = "$('Categorize').first().json.case_id"
    sticky(w, "## Workflow B — Incident Escalation\nTop: event-driven incident handling. Bottom: SLA monitor every 10 minutes escalates breaches and closes "
              "resolved incidents. Jira/Slack calls go through Orkestr connectors (live or clearly-labelled simulators).", 0, -300, 640)
    w.add(webhook("B", "Incident Webhook", "orkestr/incident"), 0, 0)
    w.add(code("Verify Signature", VERIFY_JS), 220, 0)
    w.add(if_true("Signature Valid?", "={{ $json.valid }}"), 440, 0)
    w.add(respond("Reject", "={{ JSON.stringify({ accepted: false, reason: $json.reason }) }}", 401), 660, 200)
    w.add(respond("Respond Accepted", "={{ JSON.stringify({ accepted: true, execution_id: $execution.id }) }}", 202), 660, 0)
    w.add(http("B", "Categorize", "POST", "/incidents", corr=C, retries=4,
               body="={{ JSON.stringify({ ...$('Verify Signature').first().json.payload, correlation_id: $('Verify Signature').first().json.correlation_id }) }}"), 880, 0)
    w.add(if_true("New Incident?", "={{ !$json.duplicate }}"), 1100, 0)
    w.add(http("B", "Retrieve Context", "POST", "/cases/{{ %s }}/research" % CASE, corr=C), 1320, 0)
    w.add(http("B", "Assign Owner", "POST", "/cases/{{ %s }}/assign" % CASE, corr=C), 1540, 0)
    w.add(http("B", "Create Jira Task", "POST", "/cases/{{ %s }}/actions/create_jira_issue" % CASE, corr=C, retries=4, wait_ms=3000,
               notes="Retries transient Jira failures (HTTP 503 from the connector)"), 1760, 0)
    w.add(http("B", "Notify Slack", "POST", "/cases/{{ %s }}/actions/post_slack_message" % CASE, corr=C, retries=4, wait_ms=3000), 1980, 0)
    w.add(report("B", "Incident Routed", "succeeded", C, f"entity_type: 'case', entity_id: {CASE},",
                 detail="{ jira: $('Create Jira Task').first().json.jira, owner: $('Assign Owner').first().json.assignee }"), 2200, 0)
    w.add(schedule("SLA Monitor (10 min)", 10), 0, 420)
    w.add(http("B", "Monitor SLA", "POST", "/ops/sla/scan"), 220, 420)
    w.add(if_true("Breaches?", "={{ $json.count > 0 }}"), 440, 420)
    w.add(split("Each Breach", "newly_breached"), 660, 360)
    w.add(http("B", "Escalate", "POST", "/notifications", continue_on_fail=False,
               body="={{ JSON.stringify({ title: `SLA breached: case #${$json.number} (${$json.priority})`, body: `${$json.title} · escalation level ${$json.level} · team ${$json.team}`, severity: 'critical', slack_channel: '#ops-escalations', link: `/app/cases/${$json.case_id}` }) }}"), 880, 360)
    w.add(http("B", "Close Resolved", "POST", "/ops/auto-close", once=True), 1100, 480)
    w.add(http("B", "Monitor Complete", "POST", "/workflow-events", once=True,
               body="={{ JSON.stringify({ workflow: 'B', node: 'Monitor Complete', status: 'succeeded', finish: true, detail: { closed: $json.closed } }) }}"), 1320, 480)
    w.chain("Incident Webhook", "Verify Signature", "Signature Valid?")
    w.link("Signature Valid?", "Respond Accepted", 0)
    w.link("Signature Valid?", "Reject", 1)
    w.chain("Respond Accepted", "Categorize", "New Incident?")
    w.link("New Incident?", "Retrieve Context", 0)
    w.chain("Retrieve Context", "Assign Owner", "Create Jira Task", "Notify Slack", "Incident Routed")
    w.chain("SLA Monitor (10 min)", "Monitor SLA", "Breaches?")
    w.link("Breaches?", "Each Breach", 0)
    w.link("Breaches?", "Close Resolved", 1)
    w.chain("Each Breach", "Escalate")
    w.link("Escalate", "Close Resolved")
    w.link("Close Resolved", "Monitor Complete")
    return w


# =========================================================================== C
def workflow_c() -> WF:
    w = WF("C", "RFP Processing", "Document Arrival → Validate → Store → Extract Text → Analyze Requirements → Build Compliance Matrix → Retrieve Evidence → Generate Draft → Request Review → Export")
    C = "={{ $('Verify Signature').first().json.correlation_id }}"
    R = "$('Verify Signature').first().json.payload.rfp_id"
    P = "$('Generate Draft').first().json.proposal_id"
    sticky(w, "## Workflow C — RFP Processing\nTriggered by Orkestr when a tender document is uploaded (or by an email-attachment bridge). "
              "Every stage is an idempotent API call; the draft is exported only as a watermarked DRAFT until a human approves it.", 0, -300, 640)
    w.add(webhook("C", "Document Arrival", "orkestr/rfp-arrived"), 0, 0)
    w.add(code("Verify Signature", VERIFY_JS), 220, 0)
    w.add(if_true("Signature Valid?", "={{ $json.valid && !!$json.payload.rfp_id }}"), 440, 0)
    w.add(respond("Reject", "={{ JSON.stringify({ accepted: false, reason: $json.reason || 'rfp_id missing' }) }}", 401), 660, 200)
    w.add(respond("Respond Accepted", "={{ JSON.stringify({ accepted: true, execution_id: $execution.id }) }}", 202), 660, 0)
    steps = [("Validate & Store", "intake", 60000), ("Extract Text", "extract", 120000), ("Analyze Requirements", "requirements/extract", 300000),
             ("Build Compliance Matrix", "compliance/build", 60000), ("Retrieve Evidence", "compliance/assess", 300000)]
    x = 880
    prev = "Respond Accepted"
    for name, path, to in steps:
        w.add(http("C", name, "POST", "/rfps/{{ %s }}/%s" % (R, path), corr=C, timeout=to), x, 0)
        w.link(prev, name)
        prev, x = name, x + 220
    w.add(http("C", "Generate Draft", "POST", "/rfps/{{ %s }}/proposals" % R, corr=C, timeout=300000), x, 0)
    w.add(http("C", "Request Review", "POST", "/proposals/{{ %s }}/request-review" % P, corr=C), x + 220, 0)
    w.add(http("C", "Export Draft", "POST", "/proposals/{{ %s }}/export?format=docx&final=false" % P, corr=C, timeout=120000), x + 440, 0)
    w.add(http("C", "Notify Owner", "POST", "/notifications", corr=C, continue_on_fail=True,
               body="={{ JSON.stringify({ title: 'Proposal draft ready for review', body: `Compliance: ${JSON.stringify($('Retrieve Evidence').first().json.counts)}`, severity: 'info', link: `/app/rfps/${$('Verify Signature').first().json.payload.rfp_id}` }) }}"), x + 660, 0)
    w.chain("Document Arrival", "Verify Signature", "Signature Valid?")
    w.link("Signature Valid?", "Respond Accepted", 0)
    w.link("Signature Valid?", "Reject", 1)
    w.chain(prev, "Generate Draft", "Request Review", "Export Draft", "Notify Owner")
    return w


# =========================================================================== D
def workflow_d() -> WF:
    w = WF("D", "Proposal Deadline Monitoring", "Scheduled Trigger → Query Active RFPs → Calculate Deadlines → Identify At-Risk Items → Notify Owners → Escalate")
    sticky(w, "## Workflow D — Deadline Monitoring\nHourly (and on demand via signed webhook). Orkestr computes hours left and open mandatory requirements; "
              "owners are notified for anything due within 72h and escalations go to #bids inside 24h (rate-limited to once per 6h).", 0, -300, 640)
    w.add(schedule("Hourly Schedule", 60), 0, 0)
    w.add(webhook("D", "Manual Scan Webhook", "orkestr/deadline-scan", respond="onReceived"), 0, 200)
    w.add(code("Verify Signature", VERIFY_JS), 220, 200)
    w.add(if_true("Signature Valid?", "={{ $json.valid }}"), 440, 200)
    w.add(http("D", "Query Active RFPs", "GET", "/rfps/deadlines/at-risk?horizon_hours=72"), 660, 0)
    w.add(code("Identify At-Risk Items", "const r = $input.first().json;\nreturn r.items.filter(i => i.hours_left > -24).map(i => ({ json: i }));"), 880, 0)
    w.add(http("D", "Notify Owners", "POST", "/notifications",
               body="={{ JSON.stringify({ title: `RFP due in ${$json.hours_left}h: ${$json.title}`, body: `${$json.open_mandatory} mandatory requirement(s) not yet evidenced · status ${$json.status}`, severity: $json.severity, link: `/app/rfps/${$json.rfp_id}` }) }}"), 1100, 0)
    w.add(code("Needs Escalation", "return $('Identify At-Risk Items').all().filter(i => i.json.escalate).map(i => ({ json: i.json }));"), 1320, 0)
    w.add(http("D", "Scan Complete", "POST", "/workflow-events", once=True,
               body="={{ JSON.stringify({ workflow: 'D', node: 'Scan Complete', status: 'succeeded', finish: true, detail: { at_risk: $json.count } }) }}"), 880, 200)
    w.add(http("D", "Escalate", "POST", "/rfps/{{ $json.rfp_id }}/escalate",
               body="={{ JSON.stringify({ reason: `Due in ${$json.hours_left}h with ${$json.open_mandatory} open mandatory requirement(s)` }) }}"), 1540, 0)
    w.link("Hourly Schedule", "Query Active RFPs")
    w.chain("Manual Scan Webhook", "Verify Signature", "Signature Valid?")
    w.link("Signature Valid?", "Query Active RFPs", 0)
    w.chain("Query Active RFPs", "Identify At-Risk Items", "Notify Owners", "Needs Escalation", "Escalate")
    w.link("Query Active RFPs", "Scan Complete")
    return w


# =========================================================================== Z
def workflow_z() -> WF:
    w = WF("Z", "Error Handler (dead-letter)", "Any failed execution → dead letter in Orkestr → critical notification")
    w.add({"name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "typeVersion": 1, "parameters": {}}, 0, 0)
    w.add(http("Z", "Report Dead Letter", "POST", "/workflow-events/error", retries=5, wait_ms=5000,
               body="={{ JSON.stringify({ workflow_name: $json.workflow.name, workflow_id: $json.workflow.id, execution_id: String($json.execution.id ?? ''), last_node: $json.execution.lastNodeExecuted, error: ($json.execution.error && $json.execution.error.message) || 'unknown error', payload: { mode: $json.execution.mode } }) }}"), 220, 0)
    w.link("Error Trigger", "Report Dead Letter")
    return w


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"A": "A-customer-request-intake.json", "B": "B-incident-escalation.json", "C": "C-rfp-processing.json",
             "D": "D-proposal-deadline-monitoring.json", "E": "E-approval-and-audit.json", "Z": "Z-error-handler.json"}
    for key, fn in [("A", workflow_a), ("B", workflow_b), ("C", workflow_c), ("D", workflow_d), ("E", workflow_e), ("Z", workflow_z)]:
        wf = fn().dump()
        (OUT / files[key]).write_text(json.dumps(wf, indent=2) + "\n")
        print(f"{files[key]}: {len(wf['nodes'])} nodes")
