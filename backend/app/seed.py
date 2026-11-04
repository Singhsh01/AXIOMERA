"""Idempotent demo seed: organisation, users, customers, knowledge base, integration connections.

Run: python -m app.seed
All companies, people and customers are fictional.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.db import session_factory, utcnow
from app.models import Customer, IntegrationConnection, KnowledgeDocument, Organization, User, Workspace, WorkspaceMember
from app.core.security import hash_password
from app.integrations.connectors import KINDS
from app.platform import audit, knowledge

SEED = Path(__file__).resolve().parents[1] / "seed"
DEMO_PASSWORD = "axiomera-demo"

USERS = [
    ("admin@axiomera.dev", "Alex Admin", "admin"),
    ("ops@axiomera.dev", "Olivia Operator", "operator"),
    ("approver@axiomera.dev", "Priya Approver", "approver"),
    ("reviewer@axiomera.dev", "Rafael Reviewer", "reviewer"),
    ("viewer@axiomera.dev", "Vera Viewer", "viewer"),
]


def _orders(*specs: tuple[str, int, float, str, str]) -> list[dict]:
    now = utcnow()
    return [{"id": oid, "date": (now - timedelta(days=days)).isoformat(), "amount": amount, "product": product, "status": status}
            for oid, days, amount, product, status in specs]


def customers() -> list[dict]:
    return [
        {"name": "Anna Weber", "email": "anna.weber@example.com", "company": None, "tier": "premium", "crm_id": "HS-2041",
         "orders": _orders(("ORD-10421", 12, 149.00, "HelixFlow Team plan (annual)", "delivered"), ("ORD-10377", 60, 49.00, "Add-on: e-signature", "delivered"))},
        {"name": "Jonas Keller", "email": "jonas.keller@brightline-logistics.example", "company": "Brightline Logistics", "tier": "enterprise", "crm_id": "HS-1187",
         "orders": _orders(("ORD-10455", 5, 2400.00, "Enterprise seats (20)", "delivered"))},
        {"name": "Mia Schneider", "email": "mia.schneider@example.org", "company": None, "tier": "standard", "crm_id": "HS-3302",
         "orders": _orders(("ORD-10388", 45, 89.00, "Starter plan (annual)", "delivered"))},
        {"name": "Lukas Fischer", "email": "lukas.fischer@example.net", "company": None, "tier": "standard", "crm_id": "HS-3390",
         "orders": _orders(("ORD-10430", 9, 59.00, "Starter plan (annual)", "refunded"))},
        {"name": "Sofia Rossi", "email": "sofia.rossi@nordlicht-energie.example", "company": "Nordlicht Energie", "tier": "enterprise", "crm_id": "HS-0950",
         "orders": _orders(("ORD-10412", 20, 7800.00, "Enterprise platform (annual)", "delivered"))},
        {"name": "Ben Hoffmann", "email": "ben.hoffmann@example.com", "company": "Hoffmann & Partner", "tier": "premium", "crm_id": "HS-2210",
         "orders": _orders(("ORD-10440", 3, 640.00, "Premium plan (annual)", "delivered"))},
    ]


def seed(reset_orders: bool = False) -> dict:
    db = session_factory()()
    try:
        org = db.scalars(select(Organization).where(Organization.slug == "helix-ridge")).first()
        if not org:
            org = Organization(name="Helix Ridge Software GmbH (demo)", slug="helix-ridge")
            db.add(org)
            db.flush()
        ws = db.scalars(select(Workspace).where(Workspace.org_id == org.id, Workspace.slug == "operations")).first()
        if not ws:
            ws = Workspace(org_id=org.id, name="Operations & Bids", slug="operations", settings={})
            db.add(ws)
            db.flush()
        for email, name, role in USERS:
            u = db.scalars(select(User).where(User.email == email)).first()
            if not u:
                u = User(org_id=org.id, email=email, name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
                db.add(u)
                db.flush()
                db.add(WorkspaceMember(workspace_id=ws.id, user_id=u.id))
        for c in customers():
            existing = db.scalars(select(Customer).where(Customer.workspace_id == ws.id, Customer.email == c["email"])).first()
            if existing is None:
                db.add(Customer(workspace_id=ws.id, name=c["name"], email=c["email"], company=c["company"], tier=c["tier"], crm_id=c["crm_id"],
                                attributes={"orders": c["orders"]}))
            elif reset_orders:
                existing.attributes = {"orders": c["orders"]}
        for kind, label in KINDS.items():
            if not db.scalars(select(IntegrationConnection).where(IntegrationConnection.workspace_id == ws.id, IntegrationConnection.kind == kind)).first():
                db.add(IntegrationConnection(workspace_id=ws.id, kind=kind, mode="simulator", display_name=label))
        n_docs = 0
        for f in sorted((SEED / "knowledge").glob("*.md")):
            meta, body = knowledge.parse_front_matter(f.read_text())
            vu = datetime.fromisoformat(meta["valid_until"]).replace(tzinfo=UTC) if meta.get("valid_until") else None
            before = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.workspace_id == ws.id, KnowledgeDocument.title == meta["title"])).first()
            if before is None:
                knowledge.ingest(db, ws.id, title=meta["title"], kind=meta["kind"], body=body, source=f"seed/knowledge/{f.name}", valid_until=vu)
                n_docs += 1
        if n_docs:
            audit.record(db, ws.id, "system:seed", "seed.applied", "workspace", ws.id, {"knowledge_documents": n_docs})
        db.commit()
        return {"organization": org.id, "workspace": ws.id, "knowledge_documents_added": n_docs}
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    print(seed(reset_orders="--reset-orders" in sys.argv))
