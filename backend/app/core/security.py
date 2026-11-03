"""Passwords, JWTs, role checks and HMAC webhook signatures."""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

ROLE_RANK = {"viewer": 0, "reviewer": 1, "operator": 2, "approver": 3, "admin": 4}

# Explicit permission matrix. Roles are not strictly hierarchical: reviewers may review
# proposals but cannot operate cases; approvers can decide approvals.
PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "reviewer": {"read", "rfp.review", "rfp.edit"},
    "operator": {"read", "case.write", "rfp.write", "rfp.edit", "knowledge.write", "workflow.trigger"},
    "approver": {"read", "case.write", "approval.decide", "rfp.review", "rfp.edit", "rfp.write"},
    "admin": {
        "read", "case.write", "rfp.write", "rfp.edit", "rfp.review", "approval.decide", "knowledge.write",
        "workflow.trigger", "integration.manage", "admin", "eval.run", "deadletter.manage",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, org_id: str, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": user_id, "org": org_id, "role": role, "iat": now, "exp": now + timedelta(minutes=s.jwt_ttl_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


# ------------------------------------------------------------------ webhook signatures
def sign_payload(body: bytes, timestamp: int | None = None, secret: str | None = None) -> tuple[str, str]:
    """Return (timestamp, signature). Signature = hex(HMAC_SHA256(secret, f"{ts}.{body}"))."""
    ts = str(timestamp or int(time.time()))
    key = (secret or get_settings().webhook_secret).encode()
    sig = hmac.new(key, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return ts, sig


def verify_signature(body: bytes, timestamp: str | None, signature: str | None, secret: str | None = None) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > get_settings().webhook_max_skew_seconds:
        return False
    _, expected = sign_payload(body, ts, secret)
    return hmac.compare_digest(expected, signature)


def constant_time_equals(a: str | None, b: str) -> bool:
    return a is not None and hmac.compare_digest(a.encode(), b.encode())


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()
