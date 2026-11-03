"""Case lifecycle as an explicit finite-state machine."""
from __future__ import annotations

from app.db import utcnow
from app.models import Case, CaseEvent

TRANSITIONS: dict[str, set[str]] = {
    "new": {"triaged", "escalated", "closed", "needs_review"},
    "needs_review": {"triaged", "investigating", "closed", "escalated"},
    "triaged": {"investigating", "escalated", "closed", "needs_review"},
    "investigating": {"awaiting_approval", "action_in_progress", "resolved", "escalated", "waiting_customer", "needs_review"},
    "awaiting_approval": {"action_in_progress", "investigating", "escalated"},
    "action_in_progress": {"resolved", "investigating", "escalated", "awaiting_approval"},
    "waiting_customer": {"investigating", "closed"},
    "escalated": {"investigating", "awaiting_approval", "action_in_progress", "resolved"},
    "resolved": {"closed", "investigating"},
    "closed": set(),
}
TERMINAL = {"closed"}
OPEN_STATES = set(TRANSITIONS) - {"resolved", "closed"}


class InvalidTransition(Exception):
    pass


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def transition(case: Case, dst: str, actor: str, reason: str = "", data: dict | None = None) -> CaseEvent:
    src = case.status
    if src == dst:
        ev = CaseEvent(case_id=case.id, type="noop_transition", from_status=src, to_status=dst, actor=actor, data={"reason": reason})
        case.events.append(ev)
        return ev
    if not can_transition(src, dst):
        raise InvalidTransition(f"Case #{case.number}: {src} → {dst} is not allowed")
    case.status = dst
    now = utcnow()
    if dst == "resolved":
        case.resolved_at = now
    if dst == "closed":
        case.closed_at = now
    ev = CaseEvent(case_id=case.id, type="status_changed", from_status=src, to_status=dst, actor=actor,
                   data={"reason": reason, **(data or {})})
    case.events.append(ev)
    return ev
