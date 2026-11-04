from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import hit_rate_limit
from app.core.naming import LEGACY_SESSION_COOKIE, SESSION_COOKIE
from app.core.security import PERMISSIONS, create_token, verify_password
from app.db import get_db, utcnow
from app.deps import Principal, get_principal, require
from app.models import LoginEvent, User, Workspace, WorkspaceMember
from app.platform import audit
from app.routers.serialize import to_dict

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def _record(db: Session, *, email: str, user: User | None, success: bool, reason: str, request: Request) -> None:
    db.add(LoginEvent(user_id=user.id if user else None, org_id=user.org_id if user else None, email=email, success=success,
                      reason=reason, ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:300]))


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    ip = client_ip(request) or "unknown"
    # Throttle credential stuffing independently of the account lockout.
    if hit_rate_limit(f"login-ip:{ip}", 30) or hit_rate_limit(f"login-email:{email}", 10):
        raise HTTPException(429, "Too many sign-in attempts. Wait a minute and try again.", headers={"Retry-After": "60"})
    user = db.scalars(select(User).where(User.email == email)).first()
    if user and user.locked_until and user.locked_until > utcnow():
        _record(db, email=email, user=user, success=False, reason="locked", request=request)
        db.commit()
        minutes = max(1, int((user.locked_until - utcnow()).total_seconds() // 60) + 1)
        raise HTTPException(423, f"Account temporarily locked after repeated failed sign-ins. Try again in {minutes} min.")
    if not user or not verify_password(body.password, user.password_hash):
        reason = "unknown_user" if not user else "bad_password"
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_FAILURES:
                user.locked_until, user.failed_logins = utcnow() + LOCKOUT, 0
                reason = "bad_password_locked"
        _record(db, email=email, user=user, success=False, reason=reason, request=request)
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        _record(db, email=email, user=user, success=False, reason="inactive", request=request)
        db.commit()
        raise HTTPException(401, "Invalid email or password")

    user.failed_logins, user.locked_until, user.last_login_at = 0, None, utcnow()
    _record(db, email=email, user=user, success=True, reason="ok", request=request)
    token = create_token(user.id, user.org_id, user.role)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=12 * 3600)
    ws = db.scalars(select(Workspace).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                    .where(WorkspaceMember.user_id == user.id)).first()
    audit.record(db, ws.id, f"user:{user.id}", "auth.login", "user", user.id, {"ip": client_ip(request)})
    db.commit()
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}, "workspace": {"id": ws.id, "name": ws.name}}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(LEGACY_SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ws = db.get(Workspace, p.workspace_id)
    u = db.get(User, p.id) if p.kind == "user" else None
    return {"id": p.id, "name": p.name, "role": p.role, "kind": p.kind, "workspace": {"id": ws.id, "name": ws.name},
            "permissions": sorted(PERMISSIONS.get(p.role, [])), "email": u.email if u else None,
            "last_login_at": u.last_login_at.isoformat() if u and u.last_login_at else None}


@router.get("/login-history")
def my_history(limit: int = Query(50, le=200), p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """The signed-in user's own sign-in attempts, including failures against their address."""
    if p.kind != "user":
        raise HTTPException(403, "Users only")
    u = db.get(User, p.id)
    rows = db.scalars(select(LoginEvent).where(LoginEvent.email == u.email).order_by(LoginEvent.created_at.desc()).limit(limit))
    return [to_dict(r) for r in rows]


@router.get("/login-history/all")
def org_history(email: str | None = None, success: bool | None = None, limit: int = Query(100, le=500),
                p: Principal = Depends(require("admin")), db: Session = Depends(get_db)):
    """All sign-in attempts for the admin's organisation (plus attempts for unknown addresses)."""
    q = select(LoginEvent).where((LoginEvent.org_id == p.org_id) | (LoginEvent.org_id.is_(None)))
    if email:
        q = q.where(LoginEvent.email == email.lower())
    if success is not None:
        q = q.where(LoginEvent.success.is_(success))
    rows = db.scalars(q.order_by(LoginEvent.created_at.desc()).limit(limit)).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.org_id == p.org_id))}
    out = []
    for r in rows:
        d = to_dict(r)
        u = users.get(r.user_id) if r.user_id else None
        d["user_name"], d["user_role"] = (u.name, u.role) if u else (None, None)
        out.append(d)
    locked = [{"id": u.id, "email": u.email, "name": u.name, "locked_until": u.locked_until.isoformat()} for u in users.values() if u.locked_until and u.locked_until > utcnow()]
    return {"events": out, "locked_accounts": locked}


@router.post("/users/{user_id}/unlock")
def unlock(user_id: str, p: Principal = Depends(require("admin")), db: Session = Depends(get_db)):
    """Clear a lockout before it expires. Recorded in the audit chain."""
    u = db.get(User, user_id)
    if not u or u.org_id != p.org_id:
        raise HTTPException(404, "User not found")
    u.failed_logins, u.locked_until = 0, None
    audit.record(db, p.workspace_id, f"user:{p.id}", "auth.unlock", "user", u.id, {"email": u.email})
    db.commit()
    return {"ok": True}
