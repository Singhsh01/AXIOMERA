"""Connector abstraction.

Every connector exposes `execute(operation, payload, idempotency_key)`, `fetch(operation, external_id)`
and `health()`. Two implementations exist per kind:

* Simulator – persists records in `sim_records`, honours idempotency keys and supports
  failure injection (`workspace.settings.sim_failures[kind] = n`) so retry/recovery paths can
  be demonstrated reproducibly. Every response carries `"mode": "simulator"`.
* Live – real HTTP adapters (Slack incoming webhook, Jira Cloud REST v3, HubSpot CRM v3).
  Used only when the corresponding credentials are configured. Payments are *never* live:
  refunds and credits always go to the simulated ledger in this project.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.observability import INTEGRATION_CALLS
from app.db import new_id, utcnow
from app.models import IntegrationConnection, SimRecord, Workspace


class ConnectorError(Exception):
    def __init__(self, message: str, transient: bool = True):
        super().__init__(message)
        self.transient = transient


class Connector:
    kind = "base"
    mode = "simulator"

    def execute(self, operation: str, payload: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def fetch(self, operation: str, external_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def health(self) -> dict[str, Any]:
        raise NotImplementedError


# ------------------------------------------------------------------ simulators
_PREFIX = {"email": "MSG", "slack": "SLK", "jira": "OPS", "crm": "CRM", "rest": "REST", "payments": "PAY"}


class SimulatorConnector(Connector):
    mode = "simulator"

    def __init__(self, db: Session, workspace_id: str, kind: str):
        self.db, self.workspace_id, self.kind = db, workspace_id, kind

    def _maybe_fail(self) -> None:
        # The counter is persisted through an independent session so that the caller's
        # transaction (which will be rolled back) never leaks partial business state.
        from app.db import session_factory

        side = session_factory()()
        try:
            # Atomic decrement; the UPDATE takes a FOR NO KEY UPDATE row lock, which does not
            # conflict with the foreign-key share locks held by the caller's transaction.
            row = side.execute(text("""
                UPDATE workspaces SET settings = jsonb_set(settings, ARRAY['sim_failures', :kind],
                       to_jsonb(((settings->'sim_failures'->>:kind)::int) - 1))
                WHERE id = :ws AND COALESCE((settings->'sim_failures'->>:kind)::int, 0) > 0
                RETURNING (settings->'sim_failures'->>:kind)::int"""), {"kind": self.kind, "ws": self.workspace_id}).first()
            side.commit()
        finally:
            side.close()
        if row is None:
            return
        remaining = row[0] + 1
        raise ConnectorError(f"[simulator] injected transient failure for '{self.kind}' ({remaining - 1} remaining)")

    def execute(self, operation: str, payload: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        if idempotency_key:
            existing = self.db.scalars(select(SimRecord).where(
                SimRecord.workspace_id == self.workspace_id, SimRecord.connector == self.kind,
                SimRecord.idempotency_key == idempotency_key)).first()
            if existing:
                return {**existing.response, "idempotent_replay": True}
        self._maybe_fail()
        count = self.db.scalar(select(func.count()).select_from(SimRecord).where(
            SimRecord.workspace_id == self.workspace_id, SimRecord.connector == self.kind)) or 0
        external_id = f"{_PREFIX.get(self.kind, 'SIM')}-{1001 + count}"
        response = {"mode": "simulator", "connector": self.kind, "operation": operation, "external_id": external_id,
                    "status": "ok", "at": utcnow().isoformat()}
        rec = SimRecord(workspace_id=self.workspace_id, connector=self.kind, operation=operation, external_id=external_id,
                        idempotency_key=idempotency_key, payload=payload, response=response)
        self.db.add(rec)
        self.db.flush()
        return response

    def fetch(self, operation: str, external_id: str) -> dict[str, Any] | None:
        rec = self.db.scalars(select(SimRecord).where(SimRecord.workspace_id == self.workspace_id,
                                                      SimRecord.connector == self.kind, SimRecord.external_id == external_id)).first()
        if not rec:
            return None
        return {"external_id": rec.external_id, "operation": rec.operation, "payload": rec.payload, "mode": "simulator"}

    def health(self) -> dict[str, Any]:
        ws = self.db.get(Workspace, self.workspace_id)
        self.db.refresh(ws, ["settings"])
        pending = int(((ws.settings or {}).get("sim_failures", {})).get(self.kind, 0))
        return {"status": "degraded" if pending else "healthy", "mode": "simulator", "injected_failures_pending": pending}


# ------------------------------------------------------------------ live adapters
class SlackLive(Connector):
    kind, mode = "slack", "live"

    def __init__(self, webhook_url: str):
        self.url = webhook_url

    def execute(self, operation, payload, idempotency_key=None):
        r = httpx.post(self.url, json={"text": payload.get("text", "")}, timeout=10)
        if r.status_code >= 500:
            raise ConnectorError(f"Slack {r.status_code}")
        if r.status_code >= 400:
            raise ConnectorError(f"Slack rejected message: {r.text[:200]}", transient=False)
        # Incoming webhooks return no message id; a synthetic reference is recorded instead.
        return {"mode": "live", "connector": "slack", "external_id": f"slack-webhook-{new_id()[:8]}", "status": "ok"}

    def fetch(self, operation, external_id):
        return {"external_id": external_id, "mode": "live", "note": "Slack incoming webhooks are write-only; delivery confirmed by HTTP 200"}

    def health(self):
        return {"status": "healthy" if self.url.startswith("https://hooks.slack.com/") else "degraded", "mode": "live"}


class JiraLive(Connector):
    kind, mode = "jira", "live"

    def __init__(self, base_url: str, email: str, token: str, project: str):
        self.base, self.auth, self.project = base_url.rstrip("/"), (email, token), project

    def execute(self, operation, payload, idempotency_key=None):
        body = {"fields": {"project": {"key": self.project}, "summary": payload["summary"][:250], "issuetype": {"name": payload.get("issue_type", "Task")},
                           "labels": ["axiomera"] + ([f"axiomera-{idempotency_key[:20]}"] if idempotency_key else []),
                           "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": payload.get("description", "")[:3000]}]}]}}}
        r = httpx.post(f"{self.base}/rest/api/3/issue", json=body, auth=self.auth, timeout=15)
        if r.status_code >= 500 or r.status_code == 429:
            raise ConnectorError(f"Jira {r.status_code}")
        if r.status_code >= 400:
            raise ConnectorError(f"Jira rejected issue: {r.text[:300]}", transient=False)
        return {"mode": "live", "connector": "jira", "external_id": r.json()["key"], "status": "ok"}

    def fetch(self, operation, external_id):
        r = httpx.get(f"{self.base}/rest/api/3/issue/{external_id}", auth=self.auth, timeout=10)
        return {"external_id": external_id, "mode": "live", "payload": {"summary": r.json()["fields"]["summary"]}} if r.status_code == 200 else None

    def health(self):
        try:
            r = httpx.get(f"{self.base}/rest/api/3/myself", auth=self.auth, timeout=5)
            return {"status": "healthy" if r.status_code == 200 else "down", "mode": "live", "http": r.status_code}
        except httpx.HTTPError as e:
            return {"status": "down", "mode": "live", "error": str(e)[:200]}


class HubSpotLive(Connector):
    kind, mode = "crm", "live"

    def __init__(self, token: str):
        self.h = {"Authorization": f"Bearer {token}"}

    def execute(self, operation, payload, idempotency_key=None):
        if operation != "add_note":
            raise ConnectorError(f"Live CRM operation '{operation}' is not enabled", transient=False)
        r = httpx.post("https://api.hubapi.com/crm/v3/objects/notes", headers=self.h, timeout=10,
                       json={"properties": {"hs_note_body": payload.get("body", "")[:5000], "hs_timestamp": utcnow().isoformat()}})
        if r.status_code >= 500 or r.status_code == 429:
            raise ConnectorError(f"HubSpot {r.status_code}")
        if r.status_code >= 400:
            raise ConnectorError(f"HubSpot rejected: {r.text[:200]}", transient=False)
        return {"mode": "live", "connector": "crm", "external_id": r.json()["id"], "status": "ok"}

    def fetch(self, operation, external_id):
        r = httpx.get(f"https://api.hubapi.com/crm/v3/objects/notes/{external_id}", headers=self.h, timeout=10)
        return {"external_id": external_id, "mode": "live"} if r.status_code == 200 else None

    def health(self):
        try:
            r = httpx.get("https://api.hubapi.com/crm/v3/objects/contacts?limit=1", headers=self.h, timeout=5)
            return {"status": "healthy" if r.status_code == 200 else "down", "mode": "live", "http": r.status_code}
        except httpx.HTTPError as e:
            return {"status": "down", "mode": "live", "error": str(e)[:200]}


# ------------------------------------------------------------------ registry
KINDS = {
    "email": "Email (Gmail-compatible)",
    "slack": "Slack",
    "jira": "Jira",
    "crm": "CRM (HubSpot-compatible)",
    "payments": "Payments ledger",
    "rest": "Generic REST",
}


def live_available(kind: str) -> bool:
    s = get_settings()
    return {
        "slack": bool(s.slack_webhook_url),
        "jira": bool(s.jira_base_url and s.jira_email and s.jira_api_token and s.jira_project_key),
        "crm": bool(s.hubspot_token),
    }.get(kind, False)


def get_connector(db: Session, workspace_id: str, kind: str) -> Connector:
    s = get_settings()
    conn = db.scalars(select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id,
                                                          IntegrationConnection.kind == kind)).first()
    wants_live = conn is not None and conn.mode == "live"
    if wants_live and live_available(kind):
        if kind == "slack":
            return SlackLive(s.slack_webhook_url)  # type: ignore[arg-type]
        if kind == "jira":
            return JiraLive(s.jira_base_url, s.jira_email, s.jira_api_token, s.jira_project_key)  # type: ignore[arg-type]
        if kind == "crm":
            return HubSpotLive(s.hubspot_token)  # type: ignore[arg-type]
    return SimulatorConnector(db, workspace_id, kind)


def call(db: Session, workspace_id: str, kind: str, operation: str, payload: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
    c = get_connector(db, workspace_id, kind)
    t0 = time.perf_counter()
    try:
        res = c.execute(operation, payload, idempotency_key)
        INTEGRATION_CALLS.labels(kind, c.mode, "ok").inc()
        res["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        _mark(db, workspace_id, kind, "healthy", None)
        return res
    except ConnectorError as e:
        INTEGRATION_CALLS.labels(kind, c.mode, "error").inc()
        raise e


def _mark(db: Session, workspace_id: str, kind: str, status: str, error: str | None) -> None:
    conn = db.scalars(select(IntegrationConnection).where(IntegrationConnection.workspace_id == workspace_id,
                                                          IntegrationConnection.kind == kind)).first()
    if conn:
        conn.status, conn.last_error, conn.last_check_at = status, error, utcnow()
