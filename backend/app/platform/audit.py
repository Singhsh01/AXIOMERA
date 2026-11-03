"""Hash-chained audit log.

Each event stores sha256(prev_hash + canonical(event)). `verify_chain` recomputes the chain so
any edit or deletion of a historical record is detectable.
"""
from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.observability import correlation_id_var
from app.core.redaction import redact
from app.core.security import sha256_hex
from app.db import utcnow
from app.models import AuditEvent

GENESIS = "0" * 64


def _canonical(e: AuditEvent) -> str:
    return json.dumps(
        {
            "seq": e.seq, "workspace_id": e.workspace_id, "actor_type": e.actor_type, "actor_id": e.actor_id,
            "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id, "data": e.data,
            "correlation_id": e.correlation_id, "n8n_execution_id": e.n8n_execution_id,
            "created_at": e.created_at.astimezone(UTC).isoformat(),
        },
        sort_keys=True, default=str,
    )


def record(
    db: Session,
    workspace_id: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    n8n_execution_id: str | None = None,
) -> AuditEvent:
    actor_type, _, actor_id = actor.partition(":")
    # Serialise chain appends per workspace (transaction-scoped advisory lock).
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"audit:{workspace_id}"})
    last = db.execute(
        select(AuditEvent.seq, AuditEvent.hash).where(AuditEvent.workspace_id == workspace_id).order_by(AuditEvent.seq.desc()).limit(1)
    ).first()
    seq = (last[0] + 1) if last else 1
    prev = last[1] if last else GENESIS
    ev = AuditEvent(
        seq=seq, workspace_id=workspace_id, actor_type=actor_type or "system", actor_id=actor_id or actor,
        action=action, entity_type=entity_type, entity_id=str(entity_id), data=redact(data or {}),
        correlation_id=correlation_id or correlation_id_var.get(), n8n_execution_id=n8n_execution_id,
        prev_hash=prev, created_at=utcnow(),
    )
    ev.hash = sha256_hex(prev + _canonical(ev))
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session, workspace_id: str) -> dict[str, Any]:
    events = db.scalars(select(AuditEvent).where(AuditEvent.workspace_id == workspace_id).order_by(AuditEvent.seq)).all()
    prev = GENESIS
    for e in events:
        if e.prev_hash != prev or sha256_hex(prev + _canonical(e)) != e.hash:
            return {"valid": False, "events": len(events), "broken_at_seq": e.seq}
        prev = e.hash
    return {"valid": True, "events": len(events), "head": prev}


def count(db: Session, workspace_id: str) -> int:
    return db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.workspace_id == workspace_id)) or 0
