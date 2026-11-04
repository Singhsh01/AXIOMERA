"""Request principals and authorization dependencies.

Two kinds of callers exist:
  * users            – JWT bearer token, role-based permissions, scoped to one workspace;
  * the n8n service  – X-Axiomera-Service-Token header (legacy X-Orkestr-Service-Token accepted), a fixed least-privilege permission set.
The service principal can move work forward but can never *decide* an approval.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.naming import LEGACY_SESSION_COOKIE, SESSION_COOKIE
from app.core.observability import correlation_id_var
from app.core.security import PERMISSIONS, constant_time_equals, decode_token
from app.db import get_db
from app.models import User, Workspace, WorkspaceMember

SERVICE_PERMISSIONS = {
    "read", "case.write", "rfp.write", "workflow.report", "approval.execute", "notify", "workflow.trigger",
}


@dataclass
class Principal:
    kind: str  # user | service
    id: str
    name: str
    role: str
    org_id: str
    workspace_id: str
    n8n_execution_id: str | None = None

    @property
    def actor(self) -> str:
        return f"{self.kind}:{self.id}"

    def can(self, permission: str) -> bool:
        if self.kind == "service":
            return permission in SERVICE_PERMISSIONS
        return permission in PERMISSIONS.get(self.role, set())


def _resolve_workspace(db: Session, org_id: str, requested: str | None, user_id: str | None) -> Workspace:
    q = select(Workspace).where(Workspace.org_id == org_id)
    if requested:
        q = q.where(Workspace.id == requested)
    if user_id:
        q = q.join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(WorkspaceMember.user_id == user_id)
    ws = db.scalars(q.order_by(Workspace.created_at)).first()
    if not ws:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to workspace")
    return ws


def get_principal(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_axiomera_service_token: str | None = Header(default=None),
    x_orkestr_service_token: str | None = Header(default=None, include_in_schema=False),  # legacy name, accepted but not advertised
    x_workspace_id: str | None = Header(default=None),
    x_n8n_execution_id: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None),
) -> Principal:
    x_workspace_id = x_workspace_id or None
    x_n8n_execution_id = x_n8n_execution_id or None
    if x_correlation_id:
        correlation_id_var.set(x_correlation_id[:64])
    settings = get_settings()
    service_token = x_axiomera_service_token if x_axiomera_service_token is not None else x_orkestr_service_token
    if service_token is not None:
        if not constant_time_equals(service_token, settings.service_token):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service token")
        if x_workspace_id:
            ws = db.get(Workspace, x_workspace_id)
        else:
            ws = db.scalars(select(Workspace).order_by(Workspace.created_at)).first()
        if not ws:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown workspace")
        return Principal("service", "n8n", "n8n orchestrator", "service", ws.org_id, ws.id, x_n8n_execution_id)

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    elif request.cookies.get(SESSION_COOKIE) or request.cookies.get(LEGACY_SESSION_COOKIE):
        token = request.cookies.get(SESSION_COOKIE) or request.cookies[LEGACY_SESSION_COOKIE]
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive user")
    ws = _resolve_workspace(db, user.org_id, x_workspace_id, user.id)
    return Principal("user", user.id, user.name, user.role, user.org_id, ws.id)


def require(permission: str):
    def checker(p: Principal = Depends(get_principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return p

    return checker


def require_user(p: Principal = Depends(get_principal)) -> Principal:
    if p.kind != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Human user required")
    return p
