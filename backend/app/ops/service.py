"""Enterprise operations service – the authoritative business logic that n8n and the UI call."""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.security import sha256_hex
from app.db import new_id, utcnow
from app.integrations.connectors import ConnectorError
from app.models import Approval, Case, CaseAction, CaseEvent, Customer, User, Workspace
from app.ops import agents, triage
from app.ops.state_machine import OPEN_STATES, TRANSITIONS, transition
from app.platform import approvals, audit, notifications


def normalise_subject(s: str) -> str:
    return re.sub(r"^\s*((re|fw|fwd|aw|wg)\s*:\s*)+", "", s.strip(), flags=re.I).lower()


def dedup_key(sender: str | None, title: str, description: str) -> str:
    body = re.sub(r"\s+", " ", description.strip().lower())[:280]
    return sha256_hex(f"{(sender or '').lower()}|{normalise_subject(title)}|{body}")


def _next_number(db: Session, workspace_id: str) -> int:
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"case-number:{workspace_id}"})
    return (db.scalar(select(func.max(Case.number)).where(Case.workspace_id == workspace_id)) or 1000) + 1


def create_case(db: Session, workspace_id: str, *, title: str, description: str, source: str, sender: str | None,
                source_ref: str | None, kind: str, actor: str, correlation_id: str | None = None) -> tuple[Case, bool]:
    key = dedup_key(sender, title, description)
    dup = db.scalars(select(Case).where(Case.workspace_id == workspace_id, Case.dedup_key == key,
                                        Case.status.in_(OPEN_STATES), Case.created_at > utcnow() - timedelta(hours=72))).first()
    if dup:
        dup.events.append(CaseEvent(case_id=dup.id, type="duplicate_suppressed", actor=actor, data={"source_ref": source_ref}))
        audit.record(db, workspace_id, actor, "case.duplicate_suppressed", "case", dup.id, {"source_ref": source_ref})
        return dup, True
    cust = db.scalars(select(Customer).where(Customer.workspace_id == workspace_id, Customer.email == (sender or "").lower())).first() if sender else None
    case = Case(workspace_id=workspace_id, number=_next_number(db, workspace_id), kind=kind, title=title[:300], description=description,
                source=source, source_ref=source_ref, customer_id=cust.id if cust else None, dedup_key=key,
                correlation_id=correlation_id or new_id(), triage={"sender": sender.lower() if sender else None})
    db.add(case)
    db.flush()
    case.events.append(CaseEvent(case_id=case.id, type="created", to_status="new", actor=actor, data={"source": source, "source_ref": source_ref}))
    audit.record(db, workspace_id, actor, "case.created", "case", case.id, {"number": case.number, "source": source, "kind": kind},
                 correlation_id=case.correlation_id)
    return case, False


def classify(db: Session, case: Case, actor: str) -> dict[str, Any]:
    result = agents.run_triage(db, case, case.correlation_id)
    case.triage = {**case.triage, **result}
    case.category, case.priority = result["category"], result["priority"]
    case.owner_team = triage.TEAM_FOR_CATEGORY.get(result["category"], "support")
    case.sla_due_at = triage.sla_due(case.priority, result["tier"], case.created_at)
    case.security_flags = result["security_flags"]
    if result["next"] == "human_review":
        transition(case, "needs_review", actor, "possible prompt injection or manipulation detected", {"flags": result["security_flags"]})
        notifications.notify(db, case.workspace_id, f"Case #{case.number} held for human review",
                             "Untrusted content matched manipulation patterns; automation paused.", severity="warning", link=f"/app/cases/{case.id}")
    elif result["next"] == "close_spam":
        transition(case, "triaged", actor, "classified")
        transition(case, "closed", actor, "spam")
    else:
        transition(case, "triaged", actor, f"{case.category}/{case.priority}")
    audit.record(db, case.workspace_id, actor, "case.classified", "case", case.id,
                 {"category": case.category, "priority": case.priority, "confidence": result["confidence"], "flags": len(result["security_flags"])},
                 correlation_id=case.correlation_id)
    return {"case_id": case.id, "number": case.number, "status": case.status, "category": case.category, "priority": case.priority,
            "sla_due_at": case.sla_due_at, "next": result["next"], "security_flags": result["security_flags"]}


def research(db: Session, case: Case, actor: str) -> dict[str, Any]:
    if case.status not in {"triaged", "escalated", "investigating"}:
        return {"case_id": case.id, "status": case.status, "next": "skip", "reason": f"status {case.status}"}
    result = agents.run_research(db, case, case.correlation_id)
    case.research = result
    transition(case, "investigating", actor, "evidence gathered")
    audit.record(db, case.workspace_id, actor, "case.researched", "case", case.id,
                 {"orders": len(result["orders"]), "evidence": len(result["policy_evidence"])}, correlation_id=case.correlation_id)
    return {"case_id": case.id, "status": case.status, "evidence": len(result["policy_evidence"]), "next": "resolve"}


def resolve(db: Session, case: Case, actor: str) -> dict[str, Any]:
    """Run the resolution graph, persist proposed actions and open approvals where policy requires."""
    if case.status != "investigating":
        return {"case_id": case.id, "status": case.status, "next": "skip", "approvals": []}
    result = agents.run_resolution(db, case, case.correlation_id)
    case.resolution = result
    case.draft_reply = result["reply"]["body"]
    proposed = list(result["actions"])
    sender = case.triage.get("sender")
    if sender and case.category != "spam":
        proposed.append({"action_type": "send_customer_email",
                         "params": {"to": sender, "subject": result["reply"]["subject"], "body": result["reply"]["body"]}})
    opened: list[str] = []
    auto: list[str] = []
    for p in proposed:
        act = CaseAction(case_id=case.id, action_type=p["action_type"], params=p["params"], rationale=result["rationale"])
        db.add(act)
        case.actions.append(act)
        db.flush()
        decision = approvals.evaluate(db, case.workspace_id, p["action_type"], p["params"])
        if decision["requires_approval"]:
            appr = approvals.request(db, case.workspace_id, action_type=p["action_type"], scope=p["params"], entity_type="case_action",
                                     entity_id=act.id, requested_by="agent:resolution-agent", correlation_id=case.correlation_id,
                                     summary=f"Case #{case.number}: {p['action_type'].replace('_', ' ')}" +
                                             (f" €{p['params']['amount']:.2f}" if p["params"].get("amount") else ""))
            act.approval_id, act.status = appr.id, "pending_approval"
            opened.append(appr.id)
        else:
            act.status = "approved"
            auto.append(act.id)
    if opened:
        transition(case, "awaiting_approval", actor, f"{len(opened)} approval(s) required")
    elif auto:
        transition(case, "action_in_progress", actor, "auto-approved internal actions")
    elif result["missing_information"]:
        transition(case, "waiting_customer", actor, "missing information")
    else:
        transition(case, "resolved", actor, "no action required")
    audit.record(db, case.workspace_id, actor, "case.resolution_proposed", "case", case.id,
                 {"actions": [p["action_type"] for p in proposed], "approvals": opened, "outcome": result["outcome"]},
                 correlation_id=case.correlation_id)
    return {"case_id": case.id, "status": case.status, "approvals": opened, "auto_actions": auto,
            "needs_approval": bool(opened), "has_auto_actions": bool(auto), "rationale": result["rationale"]}


def execute_actions(db: Session, case: Case, actor: str, *, action_ids: list[str] | None = None) -> dict[str, Any]:
    """Execute actions that are approved (by a human, or by policy for low-risk internal actions).
    Raises ConnectorError on transient failures so n8n's retry policy applies."""
    executed, failed = [], []
    for act in case.actions:
        if act.status != "approved" or (action_ids and act.id not in action_ids):
            continue
        act.status, act.attempts = "executing", act.attempts + 1
        db.flush()
        try:
            res = agents.execute_action(db, case, act, case.correlation_id)
        except ConnectorError:
            act.status = "approved"  # remains eligible for retry
            raise
        except approvals.ApprovalError as e:
            act.status, act.result = "failed", {"error": str(e)}
            failed.append(act.id)
            continue
        act.status, act.result = "executed", res
        if act.action_type == "create_jira_issue":
            case.external_refs = {**case.external_refs, "jira": res["external_id"]}
        executed.append({"id": act.id, "action_type": act.action_type, "external_id": res.get("external_id"), "mode": res.get("mode")})
        audit.record(db, case.workspace_id, actor, "action.executed", "case_action", act.id,
                     {"case": case.number, "action_type": act.action_type, "external_id": res.get("external_id"), "mode": res.get("mode"),
                      "approval_id": act.approval_id}, correlation_id=case.correlation_id)
        if act.approval_id:
            appr = db.get(Approval, act.approval_id)
            appr.status, appr.executed_at, appr.execution_result = "executed", utcnow(), res
    if executed and case.status in {"awaiting_approval", "escalated", "investigating"}:
        transition(case, "action_in_progress", actor, "executing approved actions")
    return {"case_id": case.id, "executed": executed, "failed": failed}


def verify_actions(db: Session, case: Case, actor: str) -> dict[str, Any]:
    results = []
    for act in case.actions:
        if act.status != "executed":
            continue
        v = agents.verify_action(db, case, act, case.correlation_id)
        act.verification = v
        act.status = "verified" if v["verified"] else "failed"
        results.append({"id": act.id, "action_type": act.action_type, **v})
        audit.record(db, case.workspace_id, actor, "action.verified" if v["verified"] else "action.verification_failed",
                     "case_action", act.id, {"checks": v["checks"]}, correlation_id=case.correlation_id)
    _settle(db, case, actor)
    all_ok = all(r["verified"] for r in results) if results else True
    return {"case_id": case.id, "number": case.number, "status": case.status, "verified": results, "all_verified": all_ok,
            "pending": [a.id for a in case.actions if a.status in {"pending_approval", "approved", "executing"}]}


def _settle(db: Session, case: Case, actor: str) -> None:
    states = {a.status for a in case.actions}
    if not states or states & {"pending_approval", "approved", "executing"}:
        if "pending_approval" in states and case.status == "action_in_progress":
            transition(case, "awaiting_approval", actor, "remaining approvals pending")
        return
    if "failed" in states:
        if case.status != "escalated":
            transition(case, "escalated", actor, "action failed verification")
            case.escalation_level += 1
        return
    if case.kind == "incident" and states <= {"verified", "rejected"}:
        # Incidents are not resolved by creating tickets; engineering resolves them.
        if case.status == "action_in_progress":
            transition(case, "investigating", actor, "ticket and alert created; awaiting engineering resolution")
        return
    if states <= {"verified", "rejected"} and case.status in {"action_in_progress", "awaiting_approval"}:
        transition(case, "resolved", actor, "all actions verified or rejected")
        audit.record(db, case.workspace_id, actor, "case.resolved", "case", case.id, {}, correlation_id=case.correlation_id)


def on_approval_decided(db: Session, appr: Approval, actor: str) -> Case | None:
    if appr.entity_type != "case_action":
        return None
    act = db.get(CaseAction, appr.entity_id)
    case = db.get(Case, act.case_id)
    act.status = "approved" if appr.status == "approved" else "rejected"
    case.events.append(CaseEvent(case_id=case.id, type=f"approval_{appr.status}", actor=actor,
                                 data={"approval_id": appr.id, "action_type": appr.action_type}))
    if appr.status == "rejected":
        _settle(db, case, actor)
    return case


def assign_owner(db: Session, case: Case, actor: str) -> dict[str, Any]:
    team = case.owner_team or triage.TEAM_FOR_CATEGORY.get(case.category or "general", "support")
    # On-call: the operator with the fewest open cases (deterministic, auditable).
    users = db.scalars(select(User).where(User.org_id == db.get(Workspace, case.workspace_id).org_id,
                                          User.role.in_(["operator", "admin"]), User.is_active)).all()
    load = {u.id: db.scalar(select(func.count()).select_from(Case).where(Case.assignee_id == u.id, Case.status.in_(OPEN_STATES))) or 0 for u in users}
    owner = min(users, key=lambda u: (load[u.id], u.email)) if users else None
    case.assignee_id = owner.id if owner else None
    case.owner_team = team
    case.events.append(CaseEvent(case_id=case.id, type="assigned", actor=actor, data={"team": team, "assignee": owner.email if owner else None}))
    audit.record(db, case.workspace_id, actor, "case.assigned", "case", case.id, {"team": team, "assignee": owner.id if owner else None},
                 correlation_id=case.correlation_id)
    return {"case_id": case.id, "team": team, "assignee": owner.email if owner else None, "assignee_name": owner.name if owner else None}


def sla_scan(db: Session, workspace_id: str, actor: str, at_risk_minutes: int = 30) -> dict[str, Any]:
    now = utcnow()
    open_cases = db.scalars(select(Case).where(Case.workspace_id == workspace_id, Case.status.in_(OPEN_STATES), Case.sla_due_at.is_not(None))).all()
    breached, at_risk = [], []
    for c in open_cases:
        if c.sla_due_at <= now:
            if not c.sla_breached:
                c.sla_breached = True
                c.escalation_level += 1
                if c.status != "escalated" and "escalated" in TRANSITIONS[c.status]:
                    transition(c, "escalated", actor, "SLA breached")
                audit.record(db, workspace_id, actor, "case.sla_breached", "case", c.id, {"priority": c.priority, "level": c.escalation_level},
                             correlation_id=c.correlation_id)
                notifications.notify(db, workspace_id, f"SLA breached: case #{c.number}", f"{c.priority} · {c.title}", severity="critical", link=f"/app/cases/{c.id}")
                breached.append({"case_id": c.id, "number": c.number, "priority": c.priority, "title": c.title, "level": c.escalation_level, "team": c.owner_team})
        elif c.sla_due_at <= now + timedelta(minutes=at_risk_minutes):
            at_risk.append({"case_id": c.id, "number": c.number, "priority": c.priority, "title": c.title, "due": c.sla_due_at.isoformat()})
    return {"scanned": len(open_cases), "newly_breached": breached, "at_risk": at_risk, "count": len(breached)}


def auto_close(db: Session, workspace_id: str, actor: str, after_hours: int = 24) -> dict[str, Any]:
    cutoff = utcnow() - timedelta(hours=after_hours)
    rows = db.scalars(select(Case).where(Case.workspace_id == workspace_id, Case.status == "resolved", Case.resolved_at < cutoff)).all()
    for c in rows:
        transition(c, "closed", actor, f"auto-closed {after_hours}h after resolution")
        audit.record(db, workspace_id, actor, "case.closed", "case", c.id, {"auto": True}, correlation_id=c.correlation_id)
    return {"closed": [c.number for c in rows]}


INTERNAL_ACTIONS = {"create_jira_issue", "post_slack_message"}
NODE_ACTIONS = {"Create Jira Task": "create_jira_issue", "Notify Slack": "post_slack_message"}


def run_internal_action(db: Session, case: Case, action_type: str, actor: str) -> tuple[CaseAction, dict[str, Any], dict[str, Any]]:
    """Execute one policy-approved internal action (Jira task, Slack alert). Idempotent per case."""
    act = next((a for a in case.actions if a.action_type == action_type and a.status in {"approved", "executed", "verified"}), None)
    if act is None:
        if action_type not in INTERNAL_ACTIONS:
            raise approvals.ApprovalError("Only internal actions can be run directly", 400)
        params = {"create_jira_issue": {"summary": f"[{case.priority}] {case.title}"[:240], "description": (case.triage or {}).get("summary", case.description[:500]),
                                        "issue_type": "Incident"},
                  "post_slack_message": {"channel": f"#{case.owner_team or 'ops'}-alerts",
                                         "text": f":rotating_light: {case.priority} incident #{case.number}: {case.title}" + (f" · {case.external_refs.get('jira')}" if case.external_refs.get("jira") else "")}}[action_type]
        if approvals.evaluate(db, case.workspace_id, action_type, params)["requires_approval"]:
            raise approvals.ApprovalError("Policy requires approval for this action", 403)
        act = CaseAction(case_id=case.id, action_type=action_type, params=params, status="approved", rationale="Incident workflow (policy: internal, low risk)")
        db.add(act)
        case.actions.append(act)
        db.flush()
    res = execute_actions(db, case, actor, action_ids=[act.id]) if act.status == "approved" else {"executed": [], "idempotent": True}
    ver = verify_actions(db, case, actor)
    return act, res, ver
