"""Platform endpoints: approvals, audit, notifications, workflows, agents, integrations, analytics."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.runtime import TOOLS
from app.config import get_settings
from app.core.naming import signature_headers
from app.core.cache import cached, invalidate
from app.core.security import sign_payload
from app.db import get_db, new_id, session_factory, utcnow
from app.deps import Principal, get_principal, require
from app.integrations import connectors
from app.models import (
    AgentRun,
    Approval,
    AuditEvent,
    Case,
    CaseAction,
    DeadLetter,
    EvalRun,
    IntegrationConnection,
    Notification,
    Proposal,
    Requirement,
    Rfp,
    SimRecord,
    ToolCall,
    WorkflowRun,
    Workspace,
)
from app.ops import service as ops
from app.platform import approvals, audit, notifications, workflows
from app.routers.common import WfCtx, map_errors, not_found, wf_ctx
from app.routers.serialize import to_dict

log = logging.getLogger(__name__)
router = APIRouter(tags=["platform"])


# =========================================================================== approvals
def _approval_view(db: Session, a: Approval) -> dict[str, Any]:
    d = to_dict(a, {"resume_url"})
    d["waiting_in_n8n"] = bool(a.resume_url) and a.status == "pending"  # only while n8n is actually paused on it
    if a.entity_type == "case_action":
        act = db.get(CaseAction, a.entity_id)
        if act:
            c = db.get(Case, act.case_id)
            d["case"] = {"id": c.id, "number": c.number, "title": c.title, "priority": c.priority, "category": c.category}
            d["rationale"] = act.rationale
    return d


@router.get("/approvals")
def list_approvals(status: str | None = None, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"appr:{p.workspace_id}:{status}", 2, lambda: _list_approvals(status, p, db))


def _list_approvals(status, p, db):
    q = select(Approval).where(Approval.workspace_id == p.workspace_id)
    if status:
        q = q.where(Approval.status == status)
    return [_approval_view(db, a) for a in db.scalars(q.order_by(Approval.created_at.desc()).limit(200))]


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return _approval_view(db, not_found(db.get(Approval, approval_id), p.workspace_id, "Approval"))


class DecisionIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


def _resume_or_fallback(approval_id: str) -> None:
    """After a decision is committed: resume the waiting n8n execution (Workflow E). If no
    execution is waiting (n8n down or E not deployed), run the same steps inline and record that
    the fallback path was used."""
    db = session_factory()()
    try:
        a = db.get(Approval, approval_id)
        s = get_settings()
        if a.resume_url and s.n8n_enabled:
            u = urlparse(a.resume_url)
            url = s.n8n_base_url.rstrip("/") + u.path  # n8n's public URL may differ from the internal one
            body = json.dumps({"approval_id": a.id, "decision": a.status}).encode()
            ts = str(int(time.time()))
            sig = hmac.new(s.webhook_secret.encode(), f"{ts}.{a.id}.{a.status}".encode(), hashlib.sha256).hexdigest()
            try:
                r = httpx.post(url, content=body, timeout=10, headers={"Content-Type": "application/json", **signature_headers(ts, sig), "X-Correlation-Id": a.correlation_id or ""})
                if r.status_code < 400:
                    return
                log.warning("n8n resume failed %s: %s", r.status_code, r.text[:200])
            except httpx.HTTPError as e:
                log.warning("n8n resume unreachable: %s", e)
        run = workflows.get_or_create_run(db, a.workspace_id, workflow_key="E", n8n_execution_id=None, correlation_id=a.correlation_id,
                                          entity_type="approval", entity_id=a.id, trigger_kind="api-fallback")
        if a.status == "approved":
            try:
                res = _execute_approval(db, a, "system:api-fallback")
                workflows.record_step(db, run, "Execute Approved Action", "succeeded", detail=res)
            except Exception as e:  # noqa: BLE001
                db.rollback()
                run = workflows.get_or_create_run(db, a.workspace_id, workflow_key="E", n8n_execution_id=None, correlation_id=a.correlation_id,
                                                  entity_type="approval", entity_id=a.id, trigger_kind="api-fallback")
                workflows.record_step(db, run, "Execute Approved Action", "failed", error=str(e))
                db.add(DeadLetter(workspace_id=a.workspace_id, source="approval-execution", workflow_key="E", payload={"approval_id": a.id}, error=str(e)))
        workflows.finish(db, run, "succeeded" if run.status != "failed" else "failed", run.error)
        db.commit()
    finally:
        db.close()


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: str, body: DecisionIn, bg: BackgroundTasks, p: Principal = Depends(require("approval.decide")), db: Session = Depends(get_db)):
    if p.kind != "user":
        raise HTTPException(403, "Only authenticated humans can decide approvals")
    a = not_found(db.get(Approval, approval_id), p.workspace_id, "Approval")
    try:
        approvals.decide(db, a, user_id=p.id, user_role=p.role, approve=body.approve, note=body.note)
    except approvals.ApprovalError as e:
        db.commit()  # persist expiry transitions
        raise HTTPException(e.code, str(e)) from e
    ops.on_approval_decided(db, a, p.actor)
    db.commit()
    invalidate(f"dash:{p.workspace_id}")
    invalidate(f"appr:{p.workspace_id}")
    bg.add_task(_resume_or_fallback, a.id)
    return _approval_view(db, a)


class WaitIn(BaseModel):
    resume_url: str


@router.post("/approvals/{approval_id}/register-wait")
def register_wait(approval_id: str, body: WaitIn, p: Principal = Depends(require("workflow.report")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    a = not_found(db.get(Approval, approval_id), p.workspace_id, "Approval")
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="approval", entity_id=a.id, correlation_id=a.correlation_id) as t:
        a.resume_url, a.n8n_execution_id = body.resume_url, p.n8n_execution_id
        notifications.notify(db, a.workspace_id, f"Decision required: {a.summary}", f"Policy {a.policy_rule} · requires role {a.required_role}",
                             severity="warning", link=f"/app/approvals?focus={a.id}")
        audit.record(db, a.workspace_id, p.actor, "approval.waiting", "approval", a.id, {"n8n_execution_id": p.n8n_execution_id},
                     correlation_id=a.correlation_id, n8n_execution_id=p.n8n_execution_id)
        t.detail = {"approval_id": a.id}
    if t.run:
        t.run.status = "waiting"
    db.commit()
    # A decision may already have been made before n8n registered its wait.
    already = a.status != "pending"
    return {"approval_id": a.id, "status": a.status, "already_decided": already}


@router.get("/approvals/{approval_id}/authorize")
def authorize(approval_id: str, p: Principal = Depends(require("approval.execute")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    """Re-verify identity, role and scope of the decision before anything executes."""
    a = not_found(db.get(Approval, approval_id), p.workspace_id, "Approval")
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="approval", entity_id=a.id, correlation_id=a.correlation_id) as t:
        reasons = []
        from app.core.security import ROLE_RANK
        from app.models import User

        if a.status == "pending" and a.expires_at and a.expires_at < utcnow():
            a.status = "expired"
        decider = db.get(User, a.decided_by) if a.decided_by else None
        if a.status == "approved":
            if not decider or not decider.is_active:
                reasons.append("decider not found or inactive")
            elif ROLE_RANK.get(decider.role, -1) < ROLE_RANK[a.required_role]:
                reasons.append("decider role insufficient")
            if a.entity_type == "case_action":
                act = db.get(CaseAction, a.entity_id)
                if approvals.scope_hash(act.action_type, act.params) != a.scope_hash:
                    reasons.append("action parameters changed after approval")
        authorized = a.status == "approved" and not reasons
        t.detail = {"authorized": authorized, "status": a.status, "reasons": reasons}
        audit.record(db, a.workspace_id, p.actor, "approval.authorization_checked", "approval", a.id, t.detail,
                     correlation_id=a.correlation_id, n8n_execution_id=p.n8n_execution_id)
    db.commit()
    return {"approval_id": a.id, "authorized": authorized, "status": a.status, "reasons": reasons, "decided_by": decider.email if decider else None}


def _execute_approval(db: Session, a: Approval, actor: str) -> dict[str, Any]:
    if a.entity_type != "case_action":
        raise approvals.ApprovalError(f"No executor for entity type {a.entity_type}", 422)
    act = db.get(CaseAction, a.entity_id)
    case = db.get(Case, act.case_id)
    ex = ops.execute_actions(db, case, actor, action_ids=[act.id])
    ver = ops.verify_actions(db, case, actor)
    return {"executed": ex["executed"], "failed": ex["failed"], "verification": ver["verified"], "case_status": case.status, "case_number": case.number}


@router.post("/approvals/{approval_id}/execute")
@map_errors
def execute_approval(approval_id: str, p: Principal = Depends(require("approval.execute")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    a = not_found(db.get(Approval, approval_id), p.workspace_id, "Approval")
    if a.status == "executed":
        return {"approval_id": a.id, "idempotent": True, "status": a.status}
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="approval", entity_id=a.id, correlation_id=a.correlation_id) as t:
        res = _execute_approval(db, a, p.actor)
        t.detail = res
    db.commit()
    return {"approval_id": a.id, **res}


class OutcomeIn(BaseModel):
    outcome: str
    detail: dict[str, Any] = Field(default_factory=dict)


@router.post("/approvals/{approval_id}/outcome")
def record_outcome(approval_id: str, body: OutcomeIn, p: Principal = Depends(require("workflow.report")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    a = not_found(db.get(Approval, approval_id), p.workspace_id, "Approval")
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="approval", entity_id=a.id, correlation_id=a.correlation_id) as t:
        audit.record(db, a.workspace_id, p.actor, "approval.outcome_recorded", "approval", a.id, {"outcome": body.outcome, **body.detail},
                     correlation_id=a.correlation_id, n8n_execution_id=p.n8n_execution_id)
        t.detail = {"outcome": body.outcome}
    if t.run:
        workflows.finish(db, t.run, "succeeded")
    db.commit()
    return {"ok": True}


# =========================================================================== audit
@router.get("/audit")
def list_audit(entity_id: str | None = None, action: str | None = None, correlation_id: str | None = None, limit: int = Query(100, le=500),
               p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    q = select(AuditEvent).where(AuditEvent.workspace_id == p.workspace_id)
    if entity_id:
        q = q.where(AuditEvent.entity_id == entity_id)
    if action:
        q = q.where(AuditEvent.action.like(f"{action}%"))
    if correlation_id:
        q = q.where(AuditEvent.correlation_id == correlation_id)
    return [to_dict(e) for e in db.scalars(q.order_by(AuditEvent.seq.desc()).limit(limit))]


@router.get("/audit/verify")
def verify_audit(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return audit.verify_chain(db, p.workspace_id)


# =========================================================================== notifications
@router.get("/notifications")
def list_notifications(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"notif:{p.workspace_id}", 2, lambda: _list_notifications(p, db))


def _list_notifications(p, db):
    q = select(Notification).where(Notification.workspace_id == p.workspace_id).order_by(Notification.created_at.desc()).limit(50)
    return [to_dict(n) for n in db.scalars(q)]


class NotifyIn(BaseModel):
    title: str
    body: str = ""
    severity: str = "info"
    link: str | None = None
    channel: str = "in_app"
    slack_channel: str | None = None


@router.post("/notifications")
@map_errors
def create_notification(body: NotifyIn, p: Principal = Depends(require("notify")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    with workflows.StepTimer(db, p, wf.workflow, wf.node) as t:
        n = notifications.notify(db, p.workspace_id, body.title, body.body, severity=body.severity, link=body.link, channel=body.channel)
        slack = None
        if body.slack_channel:
            slack = connectors.call(db, p.workspace_id, "slack", "post_message", {"channel": body.slack_channel, "text": f"{body.title}\n{body.body}"},
                                    idempotency_key=f"notify-{p.n8n_execution_id or n.id}-{wf.node or ''}-{body.title[:40]}")
        t.detail = {"notification_id": n.id, "slack": slack}
    db.commit()
    return {"id": n.id, "slack": slack}


@router.post("/notifications/{nid}/read")
def mark_read(nid: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    n = not_found(db.get(Notification, nid), p.workspace_id, "Notification")
    n.read = True
    db.commit()
    invalidate(f"notif:{p.workspace_id}")
    return {"ok": True}


# =========================================================================== workflows
def _run_view(r: WorkflowRun, with_steps: bool = False) -> dict[str, Any]:
    d = to_dict(r)
    dur = ((r.finished_at or utcnow()) - r.started_at).total_seconds() * 1000
    d["duration_ms"] = int(dur)
    d["step_count"] = len(r.steps)
    d["retries"] = sum(1 for s in r.steps if s.attempt > 1)
    if with_steps:
        d["steps"] = [to_dict(s) for s in r.steps]
    return d


@router.get("/workflows")
def list_workflows(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"wf:{p.workspace_id}", 5, lambda: _list_workflows(p=p, db=db))


def _list_workflows(p, db):
    out = []
    for key, meta in workflows.CATALOG.items():
        g = workflows.graph(key)
        q = select(WorkflowRun.status, func.count()).where(WorkflowRun.workspace_id == p.workspace_id, WorkflowRun.workflow_key == key).group_by(WorkflowRun.status)
        stats = dict(db.execute(q).all())
        last = db.scalars(select(WorkflowRun).where(WorkflowRun.workspace_id == p.workspace_id, WorkflowRun.workflow_key == key)
                          .order_by(WorkflowRun.started_at.desc()).limit(1)).first()
        out.append({"key": key, **meta, "n8n_id": g["id"], "nodes": len(g["nodes"]), "stats": stats, "last_run": _run_view(last) if last else None,
                    "triggers": [n["type"] for n in g["nodes"] if n["type"] in {"webhook", "scheduleTrigger", "errorTrigger", "emailReadImap"}]})
    return {"workflows": out, "n8n": workflows.n8n_health()}


@router.get("/workflows/runs")
def list_runs(entity_id: str | None = None, workflow: str | None = None, limit: int = Query(50, le=200),
              p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    q = select(WorkflowRun).where(WorkflowRun.workspace_id == p.workspace_id)
    if entity_id:
        q = q.where(WorkflowRun.entity_id == entity_id)
    if workflow:
        q = q.where(WorkflowRun.workflow_key == workflow)
    return [_run_view(r, with_steps=True) for r in db.scalars(q.order_by(WorkflowRun.started_at.desc()).limit(limit))]


@router.get("/workflows/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    r = not_found(db.get(WorkflowRun, run_id), p.workspace_id, "Run")
    return _run_view(r, with_steps=True)


@router.get("/workflows/{key}")
def get_workflow(key: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    if key not in workflows.CATALOG:
        raise HTTPException(404, "Unknown workflow")
    runs = db.scalars(select(WorkflowRun).where(WorkflowRun.workspace_id == p.workspace_id, WorkflowRun.workflow_key == key)
                      .order_by(WorkflowRun.started_at.desc()).limit(25)).all()
    node_stats: dict[str, dict[str, int]] = {}
    for r in runs:
        for s in r.steps:
            ns = node_stats.setdefault(s.node, {"succeeded": 0, "failed": 0, "waiting": 0, "retries": 0})
            ns[s.status] = ns.get(s.status, 0) + 1
            if s.attempt > 1:
                ns["retries"] += 1
    return {**workflows.graph(key), **workflows.CATALOG[key], "definition": workflows.definition(key), "runs": [_run_view(r, True) for r in runs],
            "node_stats": node_stats}


class TriggerIn(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/workflows/{key}/trigger")
def trigger_workflow(key: str, body: TriggerIn, p: Principal = Depends(require("workflow.trigger")), db: Session = Depends(get_db)):
    if key not in {"B", "D"}:
        raise HTTPException(400, "Only incident (B) and deadline scan (D) can be triggered manually; A and C start from intake")
    cid = body.payload.get("correlation_id") or new_id()
    try:
        res = workflows.trigger(key, {**body.payload, "workspace_id": p.workspace_id, "requested_by": p.actor}, correlation_id=cid)
    except workflows.WorkflowTriggerError as e:
        raise HTTPException(503, str(e)) from e
    audit.record(db, p.workspace_id, p.actor, "workflow.triggered", "workflow", key, {"correlation_id": cid})
    db.commit()
    return {"triggered": key, "correlation_id": cid, "n8n": res}


class StepEventIn(BaseModel):
    workflow: str
    node: str
    status: str = Field(pattern="^(succeeded|failed|waiting|skipped)$")
    correlation_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    finish: bool = False


@router.post("/workflow-events")
def workflow_event(body: StepEventIn, p: Principal = Depends(require("workflow.report")), db: Session = Depends(get_db)):
    """n8n reports steps that do not call a business endpoint (validation, waits, notifications, completion)."""
    run = workflows.get_or_create_run(db, p.workspace_id, workflow_key=body.workflow, n8n_execution_id=p.n8n_execution_id,
                                      correlation_id=body.correlation_id, entity_type=body.entity_type, entity_id=body.entity_id)
    workflows.record_step(db, run, body.node, body.status, detail=body.detail, error=body.error)
    if body.finish:
        workflows.finish(db, run, "failed" if body.status == "failed" else "succeeded", body.error)
    db.commit()
    return {"run_id": run.id, "status": run.status}


class ErrorEventIn(BaseModel):
    workflow_name: str | None = None
    workflow_id: str | None = None
    execution_id: str | None = None
    last_node: str | None = None
    error: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/workflow-events/error")
def workflow_error(body: ErrorEventIn, p: Principal = Depends(require("workflow.report")), db: Session = Depends(get_db)):
    """Called by the n8n error workflow (Z). Creates a dead letter and marks the run failed."""
    key = next((k for k, m in workflows.CATALOG.items() if m["name"] == body.workflow_name or workflows.graph(k)["id"] == body.workflow_id), None)
    payload = body.payload | {"last_node": body.last_node}
    prior = db.scalars(select(WorkflowRun).where(WorkflowRun.n8n_execution_id == body.execution_id)).first() if body.execution_id else None
    if prior and prior.entity_type == "case":
        payload["case_id"] = prior.entity_id
    elif prior and prior.entity_type == "approval":
        payload["approval_id"] = prior.entity_id
    elif prior and prior.entity_type == "rfp":
        payload["rfp_id"] = prior.entity_id
    dl = DeadLetter(workspace_id=p.workspace_id, source=f"n8n:{body.workflow_name}", workflow_key=key, n8n_execution_id=body.execution_id,
                    payload=payload, error=body.error[:4000])
    db.add(dl)
    if body.execution_id:
        run = db.scalars(select(WorkflowRun).where(WorkflowRun.n8n_execution_id == body.execution_id)).first()
        if run:
            if body.last_node and not any(s.node == body.last_node and s.status == "failed" for s in run.steps):
                workflows.record_step(db, run, body.last_node, "failed", error=body.error[:1000])
            workflows.finish(db, run, "failed", body.error[:1000])
    notifications.notify(db, p.workspace_id, f"Workflow failed: {body.workflow_name}", f"{body.last_node}: {body.error[:200]}", severity="critical",
                         link="/app/observability?tab=dead-letters")
    audit.record(db, p.workspace_id, p.actor, "workflow.dead_lettered", "dead_letter", dl.id or "new",
                 {"workflow": body.workflow_name, "node": body.last_node}, n8n_execution_id=body.execution_id)
    db.commit()
    return {"dead_letter_id": dl.id}


@router.get("/dead-letters")
def list_dead_letters(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return [to_dict(d) for d in db.scalars(select(DeadLetter).where(DeadLetter.workspace_id == p.workspace_id).order_by(DeadLetter.created_at.desc()).limit(100))]


@router.post("/dead-letters/{dl_id}/replay")
@map_errors
def replay_dead_letter(dl_id: str, p: Principal = Depends(require("deadletter.manage")), db: Session = Depends(get_db)):
    dl = not_found(db.get(DeadLetter, dl_id), p.workspace_id, "Dead letter")
    if dl.status != "open":
        raise HTTPException(409, f"Dead letter is {dl.status}")
    replayed = None
    if dl.payload.get("approval_id"):
        a = db.get(Approval, dl.payload["approval_id"])
        replayed = _execute_approval(db, a, p.actor)
    elif dl.payload.get("case_id"):
        case = db.get(Case, dl.payload["case_id"])
        action_type = ops.NODE_ACTIONS.get(dl.payload.get("last_node") or "")
        if action_type:
            act, res, _ = ops.run_internal_action(db, case, action_type, p.actor)
            replayed = {"action": action_type, "status": act.status, "external_id": (act.result or {}).get("external_id")}
        else:
            replayed = {**ops.execute_actions(db, case, p.actor), **ops.verify_actions(db, case, p.actor)}
    else:
        raise HTTPException(422, "Dead letter payload has no replayable entity")
    dl.status, dl.resolved_at = "replayed", utcnow()
    audit.record(db, p.workspace_id, p.actor, "dead_letter.replayed", "dead_letter", dl.id, {"result": str(replayed)[:500]})
    db.commit()
    return {"ok": True, "result": replayed}


# =========================================================================== agents
@router.get("/agents/overview")
def agents_overview(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    rows = db.execute(select(AgentRun.agent, AgentRun.status, func.count(), func.avg(AgentRun.latency_ms), func.sum(AgentRun.cost_usd),
                             func.sum(AgentRun.input_tokens + AgentRun.output_tokens))
                      .where(AgentRun.workspace_id == p.workspace_id).group_by(AgentRun.agent, AgentRun.status)).all()
    agents: dict[str, dict[str, Any]] = {}
    for agent, status, n, lat, cost, tok in rows:
        a = agents.setdefault(agent, {"agent": agent, "runs": 0, "by_status": {}, "avg_latency_ms": 0, "cost_usd": 0.0, "tokens": 0})
        a["avg_latency_ms"] = int(((a["avg_latency_ms"] * a["runs"]) + (lat or 0) * n) / (a["runs"] + n))
        a["runs"] += n
        a["by_status"][status] = n
        a["cost_usd"] = round(a["cost_usd"] + float(cost or 0), 5)
        a["tokens"] += int(tok or 0)
    tool_rows = db.execute(select(ToolCall.tool, ToolCall.status, func.count())
                           .join(AgentRun).where(AgentRun.workspace_id == p.workspace_id)
                           .group_by(ToolCall.tool, ToolCall.status)).all()
    return {"agents": sorted(agents.values(), key=lambda a: -a["runs"]), "tools": [{"tool": t, "status": s, "count": c} for t, s, c in tool_rows],
            "registry": [{"name": t.name, "description": t.description, "scope": t.scope, "consequential": t.consequential,
                          "schema": t.input_model.model_json_schema()} for t in TOOLS.values()]}


@router.get("/agents/runs")
def list_agent_runs(agent: str | None = None, status: str | None = None, entity_id: str | None = None, limit: int = Query(60, le=300),
                    p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    q = select(AgentRun).where(AgentRun.workspace_id == p.workspace_id)
    if agent:
        q = q.where(AgentRun.agent == agent)
    if status:
        q = q.where(AgentRun.status == status)
    if entity_id:
        q = q.where(AgentRun.entity_id == entity_id)
    out = []
    for r in db.scalars(q.order_by(AgentRun.started_at.desc()).limit(limit)):
        d = to_dict(r)
        d["tool_calls"] = [to_dict(t) for t in r.tool_calls]
        out.append(d)
    return out


@router.get("/agents/runs/{run_id}")
def get_agent_run(run_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    r = not_found(db.get(AgentRun, run_id), p.workspace_id, "Agent run")
    d = to_dict(r)
    d["tool_calls"] = [to_dict(t) for t in r.tool_calls]
    d["children"] = [to_dict(c) for c in db.scalars(select(AgentRun).where(AgentRun.parent_run_id == r.id))]
    return d


@router.post("/agents/runs/{run_id}/cancel")
def cancel_agent_run(run_id: str, p: Principal = Depends(require("case.write")), db: Session = Depends(get_db)):
    r = not_found(db.get(AgentRun, run_id), p.workspace_id, "Agent run")
    if r.status != "running":
        raise HTTPException(409, f"Run is {r.status}")
    r.status = "cancel_requested"
    audit.record(db, p.workspace_id, p.actor, "agent.cancel_requested", "agent_run", r.id, {})
    db.commit()
    return {"ok": True}


# =========================================================================== integrations
def _ensure_connections(db: Session, workspace_id: str) -> list[IntegrationConnection]:
    have = {c.kind: c for c in db.scalars(select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id))}
    for kind, name in connectors.KINDS.items():
        if kind not in have:
            c = IntegrationConnection(workspace_id=workspace_id, kind=kind, mode="simulator", display_name=name, status="unknown",
                                      secret_ref={"slack": "AXIOMERA_SLACK_WEBHOOK_URL", "jira": "AXIOMERA_JIRA_API_TOKEN", "crm": "AXIOMERA_HUBSPOT_TOKEN"}.get(kind))
            db.add(c)
            have[kind] = c
    db.flush()
    return list(have.values())


@router.get("/integrations")
def list_integrations(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"integ:{p.workspace_id}", 10, lambda: _list_integrations(p=p, db=db))


def _list_integrations(p, db):
    out = []
    for c in _ensure_connections(db, p.workspace_id):
        h = connectors.get_connector(db, p.workspace_id, c.kind).health()
        c.status, c.last_check_at = h["status"], utcnow()
        records = db.scalar(select(func.count()).select_from(SimRecord).where(SimRecord.workspace_id == p.workspace_id, SimRecord.connector == c.kind))
        out.append({**to_dict(c), "health": h, "live_credentials_present": connectors.live_available(c.kind), "simulator_records": records,
                    "effective_mode": h.get("mode")})
    out.append({"kind": "n8n", "display_name": "n8n orchestrator", "mode": "live", "health": workflows.n8n_health(), "effective_mode": "live"})
    db.commit()
    return out


class ModeIn(BaseModel):
    mode: str = Field(pattern="^(live|simulator)$")


@router.patch("/integrations/{kind}")
def set_mode(kind: str, body: ModeIn, p: Principal = Depends(require("integration.manage")), db: Session = Depends(get_db)):
    if body.mode == "live" and not connectors.live_available(kind):
        raise HTTPException(422, f"No live credentials configured for {kind}; set the referenced environment variables first")
    if kind == "payments" and body.mode == "live":
        raise HTTPException(422, "Live payments are intentionally not supported")
    c = next(c for c in _ensure_connections(db, p.workspace_id) if c.kind == kind)
    c.mode = body.mode
    audit.record(db, p.workspace_id, p.actor, "integration.mode_changed", "integration", kind, {"mode": body.mode})
    db.commit()
    return to_dict(c)


class FailIn(BaseModel):
    count: int = Field(ge=0, le=10)


@router.post("/integrations/{kind}/inject-failures")
def inject_failures(kind: str, body: FailIn, p: Principal = Depends(require("integration.manage")), db: Session = Depends(get_db)):
    """Simulator-only chaos control used by case study 3 (retry, recovery, dead-lettering)."""
    ws = db.get(Workspace, p.workspace_id)
    failures = dict((ws.settings or {}).get("sim_failures", {}))
    failures[kind] = body.count
    ws.settings = {**(ws.settings or {}), "sim_failures": failures}
    flag_modified(ws, "settings")
    audit.record(db, p.workspace_id, p.actor, "integration.failures_injected", "integration", kind, {"count": body.count})
    db.commit()
    return {"kind": kind, "pending_failures": body.count}


@router.get("/integrations/{kind}/records")
def sim_records(kind: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(SimRecord).where(SimRecord.workspace_id == p.workspace_id, SimRecord.connector == kind).order_by(SimRecord.created_at.desc()).limit(100))
    return [to_dict(r) for r in rows]


# =========================================================================== policies
@router.get("/policies/approvals")
def get_policies(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return approvals.load_policies(db, p.workspace_id)


@router.put("/policies/approvals")
def put_policies(body: dict[str, Any], p: Principal = Depends(require("admin")), db: Session = Depends(get_db)):
    errors = approvals.validate_policies(body)
    if errors:
        raise HTTPException(422, {"errors": errors})
    ws = db.get(Workspace, p.workspace_id)
    ws.settings = {**(ws.settings or {}), "approval_policies": body}
    flag_modified(ws, "settings")
    audit.record(db, p.workspace_id, p.actor, "policy.approvals_updated", "workspace", ws.id, {"rules": len(body["rules"])})
    db.commit()
    return {"ok": True}


# =========================================================================== analytics
@router.get("/analytics/overview")
def analytics(days: int = Query(14, le=90), p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"analytics:{p.workspace_id}:{days}", 15, lambda: _analytics(days=days, p=p, db=db))


def _analytics(days: int, p, db):
    ws, since = p.workspace_id, utcnow() - timedelta(days=days)
    runs = db.scalars(select(WorkflowRun).where(WorkflowRun.workspace_id == ws, WorkflowRun.started_at >= since)).all()
    finished = [r for r in runs if r.status in {"succeeded", "failed"}]
    cases = db.scalars(select(Case).where(Case.workspace_id == ws, Case.created_at >= since)).all()
    resolved = [c for c in cases if c.resolved_at]
    with_sla = [c for c in cases if c.sla_due_at]
    agent_runs = db.scalars(select(AgentRun).where(AgentRun.workspace_id == ws, AgentRun.started_at >= since)).all()
    appr = db.scalars(select(Approval).where(Approval.workspace_id == ws, Approval.created_at >= since)).all()
    decided = [a for a in appr if a.decided_at]
    tool_fail = db.scalar(select(func.count()).select_from(ToolCall).join(AgentRun).where(AgentRun.workspace_id == ws, ToolCall.status != "ok", ToolCall.created_at >= since)) or 0
    tool_total = db.scalar(select(func.count()).select_from(ToolCall).join(AgentRun).where(AgentRun.workspace_id == ws, ToolCall.created_at >= since)) or 0
    rfps = db.scalars(select(Rfp).where(Rfp.workspace_id == ws)).all()
    reqs = db.scalars(select(Requirement).join(Rfp).where(Rfp.workspace_id == ws, Requirement.deleted.is_(False))).all()
    evidenced = [r for r in reqs if r.compliance and r.compliance.evidence and r.compliance.status in {"compliant", "partially_compliant", "non_compliant"}]

    def per_day(items, attr):
        b: dict[str, int] = {}
        for it in items:
            k = getattr(it, attr).date().isoformat()
            b[k] = b.get(k, 0) + 1
        return [{"day": k, "count": v} for k, v in sorted(b.items())]

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    lat = sorted(((r.finished_at - r.started_at).total_seconds() for r in finished if r.finished_at))
    rfp_durations = []
    for r in rfps:
        ev = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == r.id, AuditEvent.action.in_(["rfp.document_uploaded", "proposal.drafted"]))
                        .order_by(AuditEvent.seq)).all()
        if len(ev) >= 1:
            drafted = db.scalars(select(AuditEvent).where(AuditEvent.action == "proposal.drafted", AuditEvent.correlation_id == r.correlation_id)).first()
            if drafted:
                rfp_durations.append((drafted.created_at - ev[0].created_at).total_seconds())
    eval_latest = db.scalars(select(EvalRun).order_by(EvalRun.started_at.desc())).all()
    latest_by_suite: dict[str, dict] = {}
    for e in eval_latest:
        latest_by_suite.setdefault(e.suite, {"suite": e.suite, "metrics": e.metrics, "at": e.started_at.isoformat(), "uses_fixtures": e.uses_fixtures})
    return {
        "window_days": days,
        "workflow_success_rate": pct(sum(1 for r in finished if r.status == "succeeded"), len(finished)),
        "workflow_runs": len(runs),
        "workflow_latency_p50_s": round(lat[len(lat) // 2], 2) if lat else None,
        "workflow_latency_p95_s": round(lat[int(len(lat) * 0.95) - 1], 2) if lat else None,
        "workflow_runs_by_key": {k: sum(1 for r in runs if r.workflow_key == k) for k in workflows.CATALOG},
        "cases_created": len(cases), "cases_resolved": len(resolved),
        "case_resolution_minutes_avg": round(sum((c.resolved_at - c.created_at).total_seconds() for c in resolved) / 60 / len(resolved), 1) if resolved else None,
        "sla_compliance": pct(sum(1 for c in with_sla if not c.sla_breached), len(with_sla)),
        "cases_by_category": {k: sum(1 for c in cases if c.category == k) for k in sorted({c.category for c in cases if c.category})},
        "cases_by_priority": {k: sum(1 for c in cases if c.priority == k) for k in ["P1", "P2", "P3", "P4"]},
        "cases_per_day": per_day(cases, "created_at"),
        "agent_runs": len(agent_runs),
        "agent_runs_by_agent": {a: sum(1 for r in agent_runs if r.agent == a) for a in sorted({r.agent for r in agent_runs})},
        "agent_failures": sum(1 for r in agent_runs if r.status not in {"succeeded", "running"}),
        "tool_failure_rate": pct(tool_fail, tool_total), "tool_calls": tool_total,
        "model_usage": {prov: {"runs": sum(1 for r in agent_runs if r.provider == prov), "tokens": sum(r.input_tokens + r.output_tokens for r in agent_runs if r.provider == prov),
                               "cost_usd": round(sum(r.cost_usd for r in agent_runs if r.provider == prov), 5)} for prov in sorted({r.provider for r in agent_runs})},
        "estimated_ai_cost_usd": round(sum(r.cost_usd for r in agent_runs), 5),
        "approval_turnaround_minutes_avg": round(sum((a.decided_at - a.created_at).total_seconds() for a in decided) / 60 / len(decided), 1) if decided else None,
        "approvals_by_status": {s: sum(1 for a in appr if a.status == s) for s in sorted({a.status for a in appr})},
        "rfp_processing_seconds_avg": round(sum(rfp_durations) / len(rfp_durations), 1) if rfp_durations else None,
        "evidence_coverage": pct(len(evidenced), len(reqs)),
        "requirements_total": len(reqs),
        "evaluations": list(latest_by_suite.values()),
    }


@router.get("/dashboard/summary")
def dashboard(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"dash:{p.workspace_id}", get_settings().cache_ttl_seconds, lambda: _dashboard(p=p, db=db))


def _dashboard(p, db):
    ws = p.workspace_id
    open_cases = db.scalars(select(Case).where(Case.workspace_id == ws, Case.status.notin_(["resolved", "closed"]))).all()
    pending = db.scalars(select(Approval).where(Approval.workspace_id == ws, Approval.status == "pending").order_by(Approval.created_at.desc())).all()
    recent_runs = db.scalars(select(WorkflowRun).where(WorkflowRun.workspace_id == ws).order_by(WorkflowRun.started_at.desc()).limit(12)).all()
    active_agents = db.scalars(select(AgentRun).where(AgentRun.workspace_id == ws).order_by(AgentRun.started_at.desc()).limit(10)).all()
    rfps = db.scalars(select(Rfp).where(Rfp.workspace_id == ws).order_by(Rfp.created_at.desc())).all()
    incidents = db.scalars(select(Case).where(Case.workspace_id == ws, Case.kind == "incident").order_by(Case.created_at.desc()).limit(6)).all()
    from app.rfp.service import at_risk

    now = utcnow()
    return {
        "open_cases": len(open_cases),
        "cases_by_status": {s: sum(1 for c in open_cases if c.status == s) for s in sorted({c.status for c in open_cases})},
        "sla": {"breached": sum(1 for c in open_cases if c.sla_breached), "at_risk": sum(1 for c in open_cases if c.sla_due_at and not c.sla_breached and c.sla_due_at < now + timedelta(hours=2)),
                "on_track": sum(1 for c in open_cases if c.sla_due_at and c.sla_due_at >= now + timedelta(hours=2))},
        "pending_approvals": [_approval_view(db, a) for a in pending[:8]], "pending_approvals_count": len(pending),
        "recent_runs": [_run_view(r, with_steps=True) for r in recent_runs],
        "agent_activity": [{"id": a.id, "agent": a.agent, "task": a.task, "status": a.status, "provider": a.provider, "latency_ms": a.latency_ms,
                            "started_at": a.started_at.isoformat(), "tool_calls": len(a.tool_calls)} for a in active_agents],
        "proposal_pipeline": {s: sum(1 for r in rfps if r.status == s) for s in ["received", "extracted", "analyzed", "matrix_ready", "drafted", "in_review", "approved", "exported"]},
        "deadlines": at_risk(db, ws, horizon_hours=24 * 30)[:6],
        "incidents": [{"id": c.id, "number": c.number, "title": c.title, "priority": c.priority, "status": c.status, "created_at": c.created_at.isoformat(),
                       "jira": c.external_refs.get("jira")} for c in incidents],
        "proposals_in_review": db.scalar(select(func.count()).select_from(Proposal).join(Rfp).where(Rfp.workspace_id == ws, Proposal.status == "in_review")) or 0,
    }


@router.get("/evals/runs")
def eval_runs(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return [to_dict(e, {"results"}) for e in db.scalars(select(EvalRun).order_by(EvalRun.started_at.desc()).limit(50))]


@router.get("/evals/runs/{run_id}")
def eval_run(run_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    e = db.get(EvalRun, run_id)
    if not e:
        raise HTTPException(404, "Not found")
    return to_dict(e)


_ = (sign_payload, get_principal)
