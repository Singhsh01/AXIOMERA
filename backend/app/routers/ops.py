"""Enterprise operations endpoints. Stage endpoints are called by n8n Workflows A and B."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.core.cache import cached
from app.db import get_db, new_id, session_factory
from app.deps import Principal, require
from app.integrations import connectors
from app.models import AgentRun, Approval, Case, Customer, WorkflowRun
from app.ops import service as ops
from app.ops.state_machine import TRANSITIONS, transition
from app.platform import audit, idempotency, workflows
from app.routers.common import WfCtx, map_errors, not_found, wf_ctx
from app.routers.serialize import to_dict

router = APIRouter(tags=["operations"])


# ------------------------------------------------------------------ intake
class EmailIn(BaseModel):
    message_id: str = Field(min_length=3, max_length=200)
    sender: EmailStr = Field(alias="from")
    subject: str = Field(max_length=500)
    body: str = Field(max_length=50_000)
    correlation_id: str | None = None
    model_config = {"populate_by_name": True}


@router.post("/ingest/email")
@map_errors
def ingest_email(body: EmailIn, p: Principal = Depends(require("case.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    """Idempotent: the email Message-ID is the idempotency key; content-level dedup catches resends."""
    ev, dup = idempotency.claim(db, p.workspace_id, "email", f"email:{body.message_id}", body.model_dump(by_alias=True))
    if dup and ev.result_ref:
        case = db.get(Case, ev.result_ref)
        with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="case", entity_id=case.id, correlation_id=case.correlation_id) as t:
            t.detail = {"duplicate": "idempotency_key"}
        db.commit()
        return {"case_id": case.id, "number": case.number, "duplicate": True, "reason": "idempotency_key", "status": case.status,
                "correlation_id": case.correlation_id}
    with workflows.StepTimer(db, p, wf.workflow, wf.node, correlation_id=body.correlation_id) as t:
        case, content_dup = ops.create_case(db, p.workspace_id, title=body.subject, description=body.body, source="email", sender=body.sender,
                                            source_ref=body.message_id, kind="request", actor=p.actor, correlation_id=body.correlation_id)
        ev.status, ev.result_ref = "done", case.id
        t.entity_type, t.entity_id = "case", case.id
        t.correlation_id = case.correlation_id
        t.detail = {"case_number": case.number, "duplicate": content_dup}
    db.commit()
    return {"case_id": case.id, "number": case.number, "duplicate": content_dup, "reason": "content" if content_dup else None,
            "status": case.status, "correlation_id": case.correlation_id}


class IntakeIn(BaseModel):
    sender: EmailStr
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=5, max_length=20_000)


def _inline_pipeline(case_id: str, actor: str) -> None:
    """Fallback when n8n is unreachable: run Workflow A's stages in-process and record the run as such."""
    db = session_factory()()
    try:
        case = db.get(Case, case_id)
        run = workflows.get_or_create_run(db, case.workspace_id, workflow_key="A", n8n_execution_id=None, correlation_id=case.correlation_id,
                                          entity_type="case", entity_id=case.id, trigger_kind="api-fallback")
        for node, fn in [("Classify", ops.classify), ("Retrieve Evidence", ops.research), ("Propose Resolution", ops.resolve)]:
            res = fn(db, case, actor)
            workflows.record_step(db, run, node, "succeeded", detail={k: v for k, v in res.items() if k in {"status", "category", "priority", "next", "approvals"}})
            db.commit()
            if case.status in {"needs_review", "closed", "awaiting_approval", "waiting_customer", "resolved"}:
                break
        if case.status == "action_in_progress":
            ops.execute_actions(db, case, actor)
            ops.verify_actions(db, case, actor)
            workflows.record_step(db, run, "Execute", "succeeded")
        workflows.finish(db, run, "succeeded")
        db.commit()
    finally:
        db.close()


@router.post("/cases/intake")
def submit_intake(body: IntakeIn, bg: BackgroundTasks, p: Principal = Depends(require("case.write")), db: Session = Depends(get_db)):
    """UI entry point: submits a request through n8n Workflow A exactly like an inbound email."""
    message_id = f"ui-{new_id()}"
    cid = new_id()
    payload = {"message_id": message_id, "from": body.sender, "subject": body.subject, "body": body.body, "channel": "portal"}
    try:
        res = workflows.trigger("A", payload, correlation_id=cid)
        audit.record(db, p.workspace_id, p.actor, "intake.submitted", "intake", message_id, {"via": "n8n", "correlation_id": cid})
        db.commit()
        return {"via": "n8n", "correlation_id": cid, "n8n": res}
    except workflows.WorkflowTriggerError as e:
        case, dup = ops.create_case(db, p.workspace_id, title=body.subject, description=body.body, source="portal", sender=body.sender,
                                    source_ref=message_id, kind="request", actor=p.actor, correlation_id=cid)
        audit.record(db, p.workspace_id, p.actor, "intake.submitted", "intake", message_id, {"via": "api-fallback", "reason": str(e)[:200]})
        db.commit()
        if not dup:
            bg.add_task(_inline_pipeline, case.id, p.actor)
        return {"via": "api-fallback", "reason": str(e), "case_id": case.id, "number": case.number, "correlation_id": cid}


# ------------------------------------------------------------------ case views
def _case_summary(c: Case) -> dict[str, Any]:
    return {"id": c.id, "number": c.number, "kind": c.kind, "title": c.title, "status": c.status, "category": c.category, "priority": c.priority,
            "source": c.source, "customer": {"id": c.customer.id, "name": c.customer.name, "tier": c.customer.tier, "company": c.customer.company} if c.customer else None,
            "sla_due_at": c.sla_due_at.isoformat() if c.sla_due_at else None, "sla_breached": c.sla_breached, "escalation_level": c.escalation_level,
            "owner_team": c.owner_team, "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
            "security_flags": len(c.security_flags or []), "pending_actions": sum(1 for a in c.actions if a.status == "pending_approval"),
            "correlation_id": c.correlation_id}


@router.get("/cases")
def list_cases(status: str | None = None, kind: str | None = None, q: str | None = None, limit: int = Query(100, le=500),
               p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return cached(f"cases:{p.workspace_id}:{status}:{kind}:{q}:{limit}", 2, lambda: _list_cases(status, kind, q, limit, p, db))


def _list_cases(status, kind, q, limit, p, db):
    stmt = select(Case).options(selectinload(Case.customer), selectinload(Case.actions)).where(Case.workspace_id == p.workspace_id)
    if status == "open":
        stmt = stmt.where(Case.status.notin_(["resolved", "closed"]))
    elif status:
        stmt = stmt.where(Case.status == status)
    if kind:
        stmt = stmt.where(Case.kind == kind)
    if q:
        stmt = stmt.where(Case.title.ilike(f"%{q}%"))
    return [_case_summary(c) for c in db.scalars(stmt.order_by(Case.created_at.desc()).limit(limit))]


@router.get("/cases/{case_id}")
def get_case(case_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    c = not_found(db.get(Case, case_id), p.workspace_id, "Case")
    d = {**_case_summary(c), "description": c.description, "triage": c.triage, "research": c.research, "resolution": c.resolution,
         "draft_reply": c.draft_reply, "security_flags": c.security_flags, "external_refs": c.external_refs, "source_ref": c.source_ref,
         "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
         "allowed_transitions": sorted(TRANSITIONS.get(c.status, set()))}
    d["events"] = [to_dict(e) for e in c.events]
    d["actions"] = []
    for a in c.actions:
        ad = to_dict(a)
        if a.approval_id:
            ad["approval"] = to_dict(db.get(Approval, a.approval_id), {"resume_url"})
        d["actions"].append(ad)
    action_ids = [a.id for a in c.actions]
    runs = db.scalars(select(AgentRun).where(AgentRun.entity_id.in_([c.id, *action_ids])).order_by(AgentRun.started_at)).all()
    d["agent_runs"] = [{**to_dict(r), "tool_calls": [to_dict(t) for t in r.tool_calls]} for r in runs]
    wruns = db.scalars(select(WorkflowRun).where(WorkflowRun.correlation_id == c.correlation_id).order_by(WorkflowRun.started_at)).all()
    appr_ids = [a.approval_id for a in c.actions if a.approval_id]
    if appr_ids:
        wruns += db.scalars(select(WorkflowRun).where(WorkflowRun.entity_id.in_(appr_ids), WorkflowRun.correlation_id != c.correlation_id)).all()
    d["workflow_runs"] = [{**to_dict(r), "steps": [to_dict(s) for s in r.steps]} for r in wruns]
    return d


# ------------------------------------------------------------------ stage endpoints (n8n)
def _stage(fn_name: str):
    def handler(case_id: str, p: Principal = Depends(require("case.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
        c = not_found(db.get(Case, case_id), p.workspace_id, "Case")
        with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="case", entity_id=c.id, correlation_id=c.correlation_id) as t:
            res = getattr(ops, fn_name)(db, c, p.actor)
            t.detail = {k: v for k, v in res.items() if k in {"status", "category", "priority", "next", "approvals", "executed", "all_verified", "team", "assignee"}}
        db.commit()
        return {**res, "correlation_id": c.correlation_id, "number": c.number}

    return map_errors(handler)


for _path, _fn in [("classify", "classify"), ("research", "research"), ("resolve", "resolve"), ("execute", "execute_actions"),
                   ("verify", "verify_actions"), ("assign", "assign_owner")]:
    router.add_api_route(f"/cases/{{case_id}}/{_path}", _stage(_fn), methods=["POST"], name=f"case_{_path}")


@router.post("/cases/{case_id}/actions/{action_type}")
@map_errors
def run_internal_action(case_id: str, action_type: str, p: Principal = Depends(require("case.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    """Execute one policy-approved internal action (Jira task, Slack alert) — used by Workflow B."""
    c = not_found(db.get(Case, case_id), p.workspace_id, "Case")
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="case", entity_id=c.id, correlation_id=c.correlation_id) as t:
        act, res, ver = ops.run_internal_action(db, c, action_type, p.actor)
        t.detail = {"action": action_type, "external_id": (act.result or {}).get("external_id"), "mode": (act.result or {}).get("mode")}
    db.commit()
    return {"case_id": c.id, "action_id": act.id, "status": act.status, "result": act.result, "verification": act.verification, "executed": res.get("executed"),
            "case_status": ver["status"], "jira": c.external_refs.get("jira")}


class TransitionIn(BaseModel):
    to: str
    reason: str = Field(min_length=3, max_length=500)


@router.post("/cases/{case_id}/transition")
@map_errors
def manual_transition(case_id: str, body: TransitionIn, p: Principal = Depends(require("case.write")), db: Session = Depends(get_db)):
    c = not_found(db.get(Case, case_id), p.workspace_id, "Case")
    src = c.status
    transition(c, body.to, p.actor, body.reason)
    audit.record(db, c.workspace_id, p.actor, "case.transitioned", "case", c.id, {"from": src, "to": body.to, "reason": body.reason}, correlation_id=c.correlation_id)
    db.commit()
    return _case_summary(c)


@router.post("/cases/{case_id}/release-review")
@map_errors
def release_review(case_id: str, bg: BackgroundTasks, p: Principal = Depends(require("case.write")), db: Session = Depends(get_db)):
    """A human confirms a case held for manipulation is safe to continue; re-runs the pipeline."""
    c = not_found(db.get(Case, case_id), p.workspace_id, "Case")
    if c.status != "needs_review":
        raise HTTPException(409, "Case is not held for review")
    transition(c, "investigating", p.actor, "released by human reviewer")
    audit.record(db, c.workspace_id, p.actor, "case.review_released", "case", c.id, {}, correlation_id=c.correlation_id)
    db.commit()
    return _case_summary(c)


# ------------------------------------------------------------------ incidents & SLA (Workflow B)
class IncidentIn(BaseModel):
    source: str = Field(default="monitoring", max_length=60)
    event_id: str = Field(min_length=3, max_length=200)
    title: str = Field(max_length=300)
    description: str = Field(max_length=20_000)
    service: str | None = None
    severity: str | None = None
    reporter: EmailStr | None = None
    correlation_id: str | None = None


@router.post("/incidents")
@map_errors
def create_incident(body: IncidentIn, p: Principal = Depends(require("case.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    ev, dup = idempotency.claim(db, p.workspace_id, body.source, f"incident:{body.source}:{body.event_id}", body.model_dump())
    if dup and ev.result_ref:
        c = db.get(Case, ev.result_ref)
        with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="case", entity_id=c.id, correlation_id=c.correlation_id) as t:
            t.detail = {"duplicate": "idempotency_key"}
        db.commit()
        return {"case_id": c.id, "number": c.number, "duplicate": True, "category": c.category, "priority": c.priority, "status": c.status,
                "correlation_id": c.correlation_id}
    with workflows.StepTimer(db, p, wf.workflow, wf.node, correlation_id=body.correlation_id) as t:
        desc = body.description + (f"\nService: {body.service}" if body.service else "") + (f"\nReported severity: {body.severity}" if body.severity else "")
        c, content_dup = ops.create_case(db, p.workspace_id, title=body.title, description=desc, source=body.source, sender=body.reporter,
                                         source_ref=body.event_id, kind="incident", actor=p.actor, correlation_id=body.correlation_id)
        ev.status, ev.result_ref = "done", c.id
        res = ops.classify(db, c, p.actor) if not content_dup else {}
        t.entity_type, t.entity_id, t.detail = "case", c.id, {"number": c.number, "priority": c.priority, "category": c.category}
    db.commit()
    return {"case_id": c.id, "number": c.number, "duplicate": content_dup, "category": c.category, "priority": c.priority, "status": c.status,
            "next": res.get("next"), "correlation_id": c.correlation_id}


@router.post("/ops/sla/scan")
def sla_scan(p: Principal = Depends(require("case.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    with workflows.StepTimer(db, p, wf.workflow, wf.node) as t:
        res = ops.sla_scan(db, p.workspace_id, p.actor)
        t.detail = {"scanned": res["scanned"], "breached": len(res["newly_breached"])}
    db.commit()
    return res


@router.post("/ops/auto-close")
def auto_close(p: Principal = Depends(require("case.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    with workflows.StepTimer(db, p, wf.workflow, wf.node) as t:
        res = ops.auto_close(db, p.workspace_id, p.actor)
        t.detail = res
    db.commit()
    return res


@router.get("/customers")
def customers(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.scalars(select(Customer).where(Customer.workspace_id == p.workspace_id).order_by(Customer.name))]


_ = connectors
