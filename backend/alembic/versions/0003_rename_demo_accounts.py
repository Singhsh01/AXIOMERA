"""Move the demo accounts from @orkestr.dev to @axiomera.dev after the product rename.

The demo users are renamed in place, so their ids, history, approvals and audit records stay attached.
Their password becomes ``axiomera-demo`` only if it is still the old default ``orkestr-demo``; a
password someone changed is left alone. Sign-in history keeps the address that was actually used at
the time. If an @axiomera.dev account already exists (a fresh seed ran first), the old one is kept.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DEMO = ["admin", "ops", "approver", "reviewer", "viewer"]


def _swap(old_domain: str, new_domain: str, old_pw: str, new_pw: str) -> None:
    from app.core.security import hash_password, verify_password

    conn = op.get_bind()
    for local in DEMO:
        old, new = f"{local}@{old_domain}", f"{local}@{new_domain}"
        row = conn.execute(sa.text("SELECT id, password_hash FROM users WHERE email = :e"), {"e": old}).first()
        if not row or conn.execute(sa.text("SELECT 1 FROM users WHERE email = :e"), {"e": new}).first():
            continue
        params = {"id": row.id, "e": new, "h": row.password_hash}
        try:
            if verify_password(old_pw, row.password_hash):
                params["h"] = hash_password(new_pw)
        except Exception:  # noqa: BLE001  (an unusable hash is left exactly as it was)
            pass
        conn.execute(sa.text("UPDATE users SET email = :e, password_hash = :h WHERE id = :id"), params)


def upgrade() -> None:
    _swap("orkestr.dev", "axiomera.dev", "orkestr-demo", "axiomera-demo")


def downgrade() -> None:
    _swap("axiomera.dev", "orkestr.dev", "axiomera-demo", "orkestr-demo")
