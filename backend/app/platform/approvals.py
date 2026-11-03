"""Policy-based approval engine.

* `evaluate` decides whether an action needs approval (unknown actions fail closed).
* `request` creates an approval bound to a canonical *scope hash* of the action parameters.
* `decide` enforces role, expiry and separation of duties.
* `assert_executable` is called by every executor immediately before a consequential action:
  the approval must be `approved`, unexpired, and its scope hash must equal the hash of the
  exact parameters about to be executed. Changing an amount after approval invalidates it.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.observability import APPROVALS
from app.core.security import ROLE_RANK, sha256_hex
from app.db import utcnow
from app.models import Approval, Workspace
from app.platform import audit, notifications

POLICY_FILE = Path(__file__).with_name("approval_policies.json")


class ApprovalError(Exception):
    def __init__(self, message: str, code: int = 409):
        super().__init__(message)
        self.code = code


def default_policies() -> dict[str, Any]:
    return json.loads(POLICY_FILE.read_text())


def load_policies(db: Session, workspace_id: str) -> dict[str, Any]:
    ws = db.get(Workspace, workspace_id)
    custom = (ws.settings or {}).get("approval_policies") if ws else None
    return custom or default_policies()


def validate_policies(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc.get("rules"), list):
        return ["'rules' must be a list"]
    for i, r in enumerate(doc["rules"]):
        for key in ("id", "action", "requires_approval", "risk", "required_role"):
            if key not in r:
                errors.append(f"rules[{i}] missing '{key}'")
        if r.get("risk") not in {"low", "medium", "high", "critical"}:
            errors.append(f"rules[{i}].risk invalid")
        if r.get("required_role") not in ROLE_RANK:
            errors.append(f"rules[{i}].required_role invalid")
        if r.get("action") in {"issue_refund", "apply_account_credit", "send_customer_email", "update_account", "submit_proposal"} and not r.get("requires_approval"):
            errors.append(f"rules[{i}]: '{r.get('action')}' is consequential and must require approval")
    if not doc.get("default", {}).get("requires_approval", False):
        errors.append("default rule must require approval (fail closed)")
    return errors


def _matches(when: dict[str, Any], params: dict[str, Any]) -> bool:
    amount = float(params.get("amount", 0) or 0)
    if "amount_gt" in when and not amount > float(when["amount_gt"]):
        return False
    if "amount_lte" in when and not amount <= float(when["amount_lte"]):
        return False
    return True


def evaluate(db: Session, workspace_id: str, action_type: str, params: dict[str, Any]) -> dict[str, Any]:
    policies = load_policies(db, workspace_id)
    for rule in policies["rules"]:
        if rule["action"] == action_type and _matches(rule.get("when", {}), params):
            return {**rule, "rule": rule["id"]}
    return {**policies["default"], "action": action_type}


def scope_hash(action_type: str, scope: dict[str, Any]) -> str:
    return sha256_hex(action_type + "|" + json.dumps(scope, sort_keys=True, default=str))


def request(
    db: Session, workspace_id: str, *, action_type: str, scope: dict[str, Any], entity_type: str, entity_id: str,
    requested_by: str, summary: str, correlation_id: str | None = None,
) -> Approval:
    decision = evaluate(db, workspace_id, action_type, scope)
    hours = decision.get("expires_hours", 48)
    appr = Approval(
        workspace_id=workspace_id, action_type=action_type, scope=scope, scope_hash=scope_hash(action_type, scope),
        entity_type=entity_type, entity_id=entity_id, risk_level=decision["risk"], policy_rule=decision["rule"],
        required_role=decision["required_role"], requested_by=requested_by, summary=summary,
        expires_at=utcnow() + timedelta(hours=hours), correlation_id=correlation_id,
    )
    db.add(appr)
    db.flush()
    audit.record(db, workspace_id, requested_by, "approval.requested", "approval", appr.id,
                 {"action_type": action_type, "scope": scope, "risk": appr.risk_level, "rule": appr.policy_rule},
                 correlation_id=correlation_id)
    notifications.notify(db, workspace_id, f"Approval needed: {summary}", f"Risk {appr.risk_level} · rule {appr.policy_rule}",
                         severity="warning" if appr.risk_level in {"high", "critical"} else "info", link=f"/app/approvals?focus={appr.id}")
    return appr


def decide(db: Session, appr: Approval, *, user_id: str, user_role: str, approve: bool, note: str | None) -> Approval:
    if appr.status != "pending":
        raise ApprovalError(f"Approval already {appr.status}")
    if appr.expires_at and appr.expires_at < utcnow():
        appr.status = "expired"
        db.flush()
        raise ApprovalError("Approval expired", 410)
    if ROLE_RANK.get(user_role, -1) < ROLE_RANK[appr.required_role]:
        raise ApprovalError(f"Role '{appr.required_role}' or higher required", 403)
    if appr.requested_by == f"user:{user_id}":
        raise ApprovalError("Separation of duties: requester cannot decide their own approval", 403)
    appr.status = "approved" if approve else "rejected"
    appr.decided_by = user_id
    appr.decided_at = utcnow()
    appr.decision_note = note
    APPROVALS.labels(appr.action_type, appr.status).inc()
    audit.record(db, appr.workspace_id, f"user:{user_id}", f"approval.{appr.status}", "approval", appr.id,
                 {"action_type": appr.action_type, "scope_hash": appr.scope_hash, "note": note}, correlation_id=appr.correlation_id)
    db.flush()
    return appr


def assert_executable(appr: Approval | None, action_type: str, scope: dict[str, Any]) -> None:
    if appr is None:
        raise ApprovalError("No approval on record for consequential action", 403)
    if appr.status != "approved":
        raise ApprovalError(f"Approval status is '{appr.status}', not 'approved'", 403)
    if appr.expires_at and appr.expires_at < utcnow():
        raise ApprovalError("Approval expired", 403)
    if appr.action_type != action_type or appr.scope_hash != scope_hash(action_type, scope):
        raise ApprovalError("Action does not match approved scope", 403)
