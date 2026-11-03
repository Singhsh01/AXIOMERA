"""n8n orchestration layer.

* The Orkestr API is the source of truth for business state; n8n coordinates *when* and *in
  which order* work happens, with retries, waits, schedules and error workflows.
* API → n8n: signed webhook calls (HMAC over timestamp + body).
* n8n → API: HTTP Request nodes authenticated with a service token; each call carries the n8n
  execution id, workflow key and node name, which the API records as workflow steps. That gives
  a business-record ↔ n8n-execution correlation without polling n8n.
"""
from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.observability import WORKFLOW_STEPS
from app.core.security import sign_payload
from app.db import new_id, utcnow
from app.models import WorkflowRun, WorkflowStep

log = logging.getLogger(__name__)

CATALOG: dict[str, dict[str, Any]] = {
    "A": {"file": "A-customer-request-intake.json", "path": "orkestr/intake", "name": "Customer Request Intake", "domain": "operations"},
    "B": {"file": "B-incident-escalation.json", "path": "orkestr/incident", "name": "Enterprise Incident Escalation", "domain": "operations"},
    "C": {"file": "C-rfp-processing.json", "path": "orkestr/rfp-arrived", "name": "RFP Processing", "domain": "proposals"},
    "D": {"file": "D-proposal-deadline-monitoring.json", "path": "orkestr/deadline-scan", "name": "Proposal Deadline Monitoring", "domain": "proposals"},
    "E": {"file": "E-approval-and-audit.json", "path": "orkestr/approval-requested", "name": "Approval & Audit", "domain": "platform"},
    "Z": {"file": "Z-error-handler.json", "path": None, "name": "Error Handler (dead-letter)", "domain": "platform"},
}


class WorkflowTriggerError(Exception):
    pass


@lru_cache(maxsize=16)
def _load(file: str) -> dict[str, Any]:
    return json.loads((get_settings().n8n_workflows_dir / file).read_text())


def definition(key: str) -> dict[str, Any]:
    return _load(CATALOG[key]["file"])


def graph(key: str) -> dict[str, Any]:
    """Convert an n8n workflow definition to nodes/edges for visualisation."""
    wf = definition(key)
    nodes = [
        {
            "id": n["name"], "type": n["type"].split(".")[-1], "position": {"x": n["position"][0], "y": n["position"][1]},
            "retry": {"enabled": n.get("retryOnFail", False), "maxTries": n.get("maxTries"), "waitMs": n.get("waitBetweenTries")},
            "notes": n.get("notes"),
            "disabled": n.get("disabled", False),
        }
        for n in wf["nodes"]
        if n["type"] != "n8n-nodes-base.stickyNote"
    ]
    edges = []
    for src, outs in wf.get("connections", {}).items():
        for branch_idx, branch in enumerate(outs.get("main", [])):
            for conn in branch or []:
                edges.append({"id": f"{src}->{conn['node']}#{branch_idx}", "source": src, "target": conn["node"], "branch": branch_idx})
    return {"key": key, "id": wf.get("id"), "name": wf["name"], "nodes": nodes, "edges": edges, "settings": wf.get("settings", {})}


def trigger(key: str, payload: dict[str, Any], *, correlation_id: str) -> dict[str, Any]:
    s = get_settings()
    path = CATALOG[key]["path"]
    if not path:
        raise WorkflowTriggerError(f"Workflow {key} has no webhook trigger")
    if not s.n8n_enabled:
        raise WorkflowTriggerError("n8n disabled by configuration")
    body = json.dumps({**payload, "correlation_id": correlation_id}, default=str).encode()
    ts, sig = sign_payload(body)
    try:
        r = httpx.post(
            f"{s.n8n_base_url}/webhook/{path}", content=body, timeout=15,
            headers={"Content-Type": "application/json", "X-Orkestr-Timestamp": ts, "X-Orkestr-Signature": sig,
                     "X-Correlation-Id": correlation_id},
        )
    except httpx.HTTPError as exc:
        raise WorkflowTriggerError(f"n8n unreachable: {exc}") from exc
    if r.status_code >= 400:
        raise WorkflowTriggerError(f"n8n returned {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text[:500]}


def get_or_create_run(
    db: Session, workspace_id: str, *, workflow_key: str, n8n_execution_id: str | None, correlation_id: str | None,
    entity_type: str | None = None, entity_id: str | None = None, trigger_kind: str = "n8n",
) -> WorkflowRun:
    run = None
    if n8n_execution_id:
        run = db.scalars(select(WorkflowRun).where(WorkflowRun.n8n_execution_id == n8n_execution_id, WorkflowRun.workspace_id == workspace_id)).first()
    elif correlation_id:
        run = db.scalars(select(WorkflowRun).where(WorkflowRun.workspace_id == workspace_id, WorkflowRun.correlation_id == correlation_id,
                                                   WorkflowRun.workflow_key == workflow_key, WorkflowRun.n8n_execution_id.is_(None),
                                                   WorkflowRun.trigger == trigger_kind, WorkflowRun.status.in_(["running", "waiting"]))
                         .order_by(WorkflowRun.started_at.desc())).first()
    if run is None:
        run = WorkflowRun(
            workspace_id=workspace_id, workflow_key=workflow_key, n8n_execution_id=n8n_execution_id,
            correlation_id=correlation_id or new_id(), entity_type=entity_type, entity_id=entity_id, trigger=trigger_kind,
        )
        db.add(run)
        db.flush()
    if entity_id and not run.entity_id:
        run.entity_type, run.entity_id = entity_type, entity_id
    return run


def record_step(
    db: Session, run: WorkflowRun, node: str, status: str, *, detail: dict[str, Any] | None = None,
    error: str | None = None, attempt: int = 1, duration_ms: int | None = None,
) -> WorkflowStep:
    prior = [s for s in run.steps if s.node == node]
    if prior:
        attempt = max(attempt, max(s.attempt for s in prior) + 1)
    step = WorkflowStep(run_id=run.id, node=node, status=status, detail=detail or {}, error=error, attempt=attempt, duration_ms=duration_ms)
    db.add(step)
    run.steps.append(step)
    WORKFLOW_STEPS.labels(run.workflow_key, status).inc()
    if status == "failed":
        run.status, run.error = "failed", error
    elif status == "waiting":
        run.status = "waiting"
    elif run.status in {"waiting", "failed"} and status == "succeeded":
        run.status, run.error = "running", None  # recovered (e.g. after retry)
    db.flush()
    return step


def finish(db: Session, run: WorkflowRun, status: str = "succeeded", error: str | None = None) -> None:
    run.status, run.error, run.finished_at = status, error, utcnow()
    db.flush()


class StepTimer:
    """Context helper used by API handlers that n8n calls; records one step per call."""

    def __init__(self, db: Session, principal, workflow_key: str | None, node: str | None, *, entity_type: str | None = None,
                 entity_id: str | None = None, correlation_id: str | None = None):
        self.db, self.p, self.key, self.node = db, principal, workflow_key, node
        self.entity_type, self.entity_id, self.correlation_id = entity_type, entity_id, correlation_id
        self.detail: dict[str, Any] = {}
        self.run: WorkflowRun | None = None

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.key or not self.node:
            return False
        ms = int((time.perf_counter() - self.t0) * 1000)
        # Failures must be visible even though the request transaction will be rolled back,
        # so they are written through an independent session.
        from app.db import session_factory

        target_db = self.db if exc is None else session_factory()()
        try:
            run = get_or_create_run(target_db, self.p.workspace_id, workflow_key=self.key, n8n_execution_id=self.p.n8n_execution_id,
                                    correlation_id=self.correlation_id, entity_type=self.entity_type, entity_id=self.entity_id)
            record_step(target_db, run, self.node, "failed" if exc else "succeeded", detail=self.detail,
                        error=str(exc)[:1000] if exc else None, duration_ms=ms)
            self.run = run
            if exc is not None:
                target_db.commit()
        finally:
            if exc is not None:
                target_db.close()
        return False


def n8n_health() -> dict[str, Any]:
    s = get_settings()
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{s.n8n_base_url}/healthz", timeout=3)
        ok = r.status_code == 200
        return {"status": "healthy" if ok else "degraded", "latency_ms": int((time.perf_counter() - t0) * 1000), "url": s.n8n_base_url}
    except httpx.HTTPError as exc:
        return {"status": "down", "error": str(exc)[:200], "url": s.n8n_base_url}


def n8n_executions(limit: int = 20) -> list[dict[str, Any]] | None:
    """Fetch executions from the n8n public API if an API key is configured."""
    s = get_settings()
    if not s.n8n_api_key:
        return None
    try:
        r = httpx.get(f"{s.n8n_base_url}/api/v1/executions", params={"limit": limit},
                      headers={"X-N8N-API-KEY": s.n8n_api_key}, timeout=5)
        r.raise_for_status()
        return r.json().get("data", [])
    except httpx.HTTPError as exc:
        log.warning("n8n executions fetch failed: %s", exc)
        return None
