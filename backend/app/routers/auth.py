from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import PERMISSIONS, create_token, verify_password
from app.db import get_db
from app.deps import Principal, get_principal
from app.models import User, Workspace, WorkspaceMember
from app.platform import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user.id, user.org_id, user.role)
    response.set_cookie("orkestr_token", token, httponly=True, samesite="lax", max_age=12 * 3600)
    ws = db.scalars(select(Workspace).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                    .where(WorkspaceMember.user_id == user.id)).first()
    audit.record(db, ws.id, f"user:{user.id}", "auth.login", "user", user.id, {})
    db.commit()
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}, "workspace": {"id": ws.id, "name": ws.name}}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("orkestr_token")
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    ws = db.get(Workspace, p.workspace_id)
    return {"id": p.id, "name": p.name, "role": p.role, "kind": p.kind, "workspace": {"id": ws.id, "name": ws.name},
            "permissions": sorted(PERMISSIONS.get(p.role, []))}
