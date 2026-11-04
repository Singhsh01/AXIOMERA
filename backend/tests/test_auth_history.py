"""Login history, account lockout, and rate limiting keyed per user."""
from __future__ import annotations

import uuid

from app.core.security import hash_password
from app.models import Organization, User, Workspace, WorkspaceMember


def _make_user(db, role="operator"):
    org = db.query(Organization).first()
    ws = db.query(Workspace).first()
    email = f"qa-{uuid.uuid4().hex[:8]}@axiomera.dev"
    u = User(org_id=org.id, email=email, name="QA User", role=role, password_hash=hash_password("Correct-horse-1"))
    db.add(u)
    db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=u.id))
    db.commit()
    return email


def test_successful_and_failed_logins_are_recorded(client, db):
    email = _make_user(db)
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"}, headers={"User-Agent": "qa-agent/1"}).status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": email, "password": "Correct-horse-1"}, headers={"User-Agent": "qa-agent/1"})
    assert ok.status_code == 200
    h = {"Authorization": f"Bearer {ok.json()['token']}"}
    hist = client.get("/api/v1/auth/login-history", headers=h).json()
    assert [e["success"] for e in hist[:2]] == [True, False]
    assert hist[1]["reason"] == "bad_password" and hist[0]["user_agent"] == "qa-agent/1"
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["last_login_at"] and me["email"] == email


def test_unknown_user_attempt_is_recorded_without_user(client, admin_h):
    ghost = f"ghost-{uuid.uuid4().hex[:6]}@example.com"
    assert client.post("/api/v1/auth/login", json={"email": ghost, "password": "x"}).status_code == 401
    events = client.get(f"/api/v1/auth/login-history/all?email={ghost}", headers=admin_h).json()["events"]
    assert events[0]["reason"] == "unknown_user" and events[0]["user_id"] is None


def test_lockout_after_repeated_failures(client, db, admin_h):
    email = _make_user(db)
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "nope"}).status_code == 401
    # even the correct password is refused while locked
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Correct-horse-1"})
    assert r.status_code == 423 and "locked" in r.json()["detail"]
    data = client.get("/api/v1/auth/login-history/all", headers=admin_h).json()
    assert any(a["email"] == email for a in data["locked_accounts"])
    reasons = [e["reason"] for e in data["events"] if e["email"] == email]
    assert "bad_password_locked" in reasons and "locked" in reasons


def test_org_history_is_admin_only(client, ops_h):
    assert client.get("/api/v1/auth/login-history/all", headers=ops_h).status_code == 403


def test_rate_limit_is_per_user_not_per_proxy(client, ops_h, approver_h):
    """All browser traffic shares the web proxy's address; one busy user must not throttle others."""
    from app.config import get_settings

    s = get_settings()
    old = s.rate_limit_per_minute
    s.rate_limit_per_minute = 5
    try:
        codes = [client.get("/api/v1/notifications", headers=ops_h).status_code for _ in range(7)]
        assert codes[-1] == 429
        assert client.get("/api/v1/notifications", headers=approver_h).status_code == 200
    finally:
        s.rate_limit_per_minute = old


def test_admin_can_unlock(client, db, admin_h):
    email = _make_user(db)
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    locked = client.get("/api/v1/auth/login-history/all", headers=admin_h).json()["locked_accounts"]
    uid = next(a["id"] for a in locked if a["email"] == email)
    assert client.post(f"/api/v1/auth/users/{uid}/unlock", headers=admin_h).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "Correct-horse-1"}).status_code == 200


def test_unlock_requires_admin(client, ops_h):
    assert client.post("/api/v1/auth/users/x/unlock", headers=ops_h).status_code == 403
