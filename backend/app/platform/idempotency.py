from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.observability import DUPLICATES
from app.core.security import sha256_hex
from app.models import InboundEvent


def payload_hash(payload: Any) -> str:
    return sha256_hex(json.dumps(payload, sort_keys=True, default=str))


def claim(db: Session, workspace_id: str, source: str, key: str, payload: Any) -> tuple[InboundEvent, bool]:
    """Insert an idempotency record. Returns (event, is_duplicate).

    Uses the unique constraint (workspace_id, idempotency_key) as the arbiter, so concurrent
    deliveries of the same event (n8n retries, provider redeliveries) resolve to one winner.
    """
    existing = db.scalars(
        select(InboundEvent).where(InboundEvent.workspace_id == workspace_id, InboundEvent.idempotency_key == key)
    ).first()
    if existing:
        existing.duplicate_count += 1
        DUPLICATES.labels(source).inc()
        db.flush()
        return existing, True
    ev = InboundEvent(workspace_id=workspace_id, source=source, idempotency_key=key, payload_hash=payload_hash(payload))
    try:
        with db.begin_nested():
            db.add(ev)
            db.flush()
    except IntegrityError:
        existing = db.scalars(
            select(InboundEvent).where(InboundEvent.workspace_id == workspace_id, InboundEvent.idempotency_key == key)
        ).one()
        existing.duplicate_count += 1
        DUPLICATES.labels(source).inc()
        return existing, True
    return ev, False
