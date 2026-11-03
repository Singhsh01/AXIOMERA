"""Tool registry. Each tool declares an input schema, a permission scope, and whether it is
consequential (requires an approval whose scope matches the call exactly)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agents.runtime import AgentExecution, tool
from app.integrations import connectors
from app.models import Approval, Case, Customer
from app.platform import approvals, knowledge


# ------------------------------------------------------------------ read tools
class LookupCustomer(BaseModel):
    email: str


@tool("crm.lookup_customer", "Look up a customer record by email", LookupCustomer, scope="crm.read")
def lookup_customer(ex: AgentExecution, a: LookupCustomer) -> dict[str, Any]:
    c = ex.db.scalars(select(Customer).where(Customer.workspace_id == ex.workspace_id, Customer.email == a.email.lower())).first()
    if not c:
        return {"found": False}
    ex.add_context({"type": "customer", "id": c.id, "label": c.name})
    return {"found": True, "id": c.id, "name": c.name, "company": c.company, "tier": c.tier, "crm_id": c.crm_id,
            "orders": c.attributes.get("orders", []), "account_balance": c.account_balance}


class GetOrder(BaseModel):
    customer_id: str
    order_id: str


@tool("orders.get", "Fetch one order for a customer", GetOrder, scope="crm.read")
def get_order(ex: AgentExecution, a: GetOrder) -> dict[str, Any]:
    c = ex.db.get(Customer, a.customer_id)
    if not c or c.workspace_id != ex.workspace_id:
        return {"found": False}
    for o in c.attributes.get("orders", []):
        if o["id"].upper() == a.order_id.upper():
            ex.add_context({"type": "order", "id": o["id"]})
            return {"found": True, **o}
    return {"found": False}


class FindSimilar(BaseModel):
    case_id: str
    customer_id: str | None = None
    category: str | None = None


@tool("cases.find_related", "Find other open cases for the same customer/category", FindSimilar, scope="cases.read")
def find_related(ex: AgentExecution, a: FindSimilar) -> list[dict[str, Any]]:
    q = select(Case).where(Case.workspace_id == ex.workspace_id, Case.id != a.case_id, Case.status.notin_(["closed"]))
    if a.customer_id:
        q = q.where(Case.customer_id == a.customer_id)
    elif a.category:
        q = q.where(Case.category == a.category)
    else:
        return []
    rows = ex.db.scalars(q.order_by(Case.created_at.desc()).limit(5)).all()
    return [{"id": r.id, "number": r.number, "title": r.title, "status": r.status, "category": r.category} for r in rows]


class SearchKnowledge(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    kinds: list[str] | None = None
    k: int = Field(default=4, ge=1, le=10)


@tool("knowledge.search", "Hybrid search over approved company knowledge", SearchKnowledge, scope="knowledge.read")
def search_knowledge(ex: AgentExecution, a: SearchKnowledge) -> list[dict[str, Any]]:
    hits = knowledge.search(ex.db, ex.workspace_id, a.query, k=a.k, kinds=a.kinds)
    for h in hits:
        ex.add_context({"type": "knowledge_chunk", "id": h["chunk_id"], "label": h["document_title"]})
    return hits


class FetchRecord(BaseModel):
    connector: str
    external_id: str


@tool("connector.fetch", "Read back a record from an integration (verification)", FetchRecord, scope="integration.read")
def fetch_record(ex: AgentExecution, a: FetchRecord) -> dict[str, Any] | None:
    return connectors.get_connector(ex.db, ex.workspace_id, a.connector).fetch("get", a.external_id)


# ------------------------------------------------------------------ write tools
class _Consequential(BaseModel):
    approval_id: str
    idempotency_key: str

    def scope(self) -> dict[str, Any]:
        return self.model_dump(exclude={"approval_id", "idempotency_key"})


def _gate(ex: AgentExecution, a: _Consequential, action_type: str) -> None:
    appr = ex.db.get(Approval, a.approval_id)
    if appr and appr.workspace_id != ex.workspace_id:
        appr = None
    approvals.assert_executable(appr, action_type, a.scope())


class Refund(_Consequential):
    customer_id: str
    order_id: str
    amount: float = Field(gt=0, le=100_000)
    currency: str = "EUR"


@tool("payments.refund", "Issue a refund (simulated payments ledger only)", Refund, scope="payments.write", consequential=True)
def refund(ex: AgentExecution, a: Refund) -> dict[str, Any]:
    _gate(ex, a, "issue_refund")
    # Payments are never live in this project – always the simulated ledger.
    return connectors.call(ex.db, ex.workspace_id, "payments", "refund", a.scope(), a.idempotency_key)


class Credit(_Consequential):
    customer_id: str
    amount: float = Field(gt=0, le=100_000)
    currency: str = "EUR"
    reason: str


@tool("crm.apply_credit", "Apply an account credit (simulated ledger)", Credit, scope="payments.write", consequential=True)
def apply_credit(ex: AgentExecution, a: Credit) -> dict[str, Any]:
    _gate(ex, a, "apply_account_credit")
    res = connectors.call(ex.db, ex.workspace_id, "payments", "credit", a.scope(), a.idempotency_key)
    if not res.get("idempotent_replay"):
        c = ex.db.get(Customer, a.customer_id)
        c.account_balance = round(c.account_balance + a.amount, 2)
    return res


class SendEmail(_Consequential):
    to: str
    subject: str
    body: str


@tool("email.send", "Send a customer-facing email", SendEmail, scope="email.send", consequential=True)
def send_email(ex: AgentExecution, a: SendEmail) -> dict[str, Any]:
    _gate(ex, a, "send_customer_email")
    return connectors.call(ex.db, ex.workspace_id, "email", "send", a.scope(), a.idempotency_key)


class UpdateAccount(_Consequential):
    customer_id: str
    changes: dict[str, str]


@tool("crm.update_account", "Modify a customer account", UpdateAccount, scope="crm.write", consequential=True)
def update_account(ex: AgentExecution, a: UpdateAccount) -> dict[str, Any]:
    _gate(ex, a, "update_account")
    res = connectors.call(ex.db, ex.workspace_id, "crm", "update_account", a.scope(), a.idempotency_key)
    c = ex.db.get(Customer, a.customer_id)
    if "tier" in a.changes and a.changes["tier"] in {"standard", "premium", "enterprise"}:
        c.tier = a.changes["tier"]
    return res


class JiraIssue(BaseModel):
    summary: str = Field(max_length=250)
    description: str
    issue_type: str = "Task"
    idempotency_key: str


@tool("jira.create_issue", "Create an internal Jira issue", JiraIssue, scope="jira.write")
def jira_issue(ex: AgentExecution, a: JiraIssue) -> dict[str, Any]:
    return connectors.call(ex.db, ex.workspace_id, "jira", "create_issue", a.model_dump(exclude={"idempotency_key"}), a.idempotency_key)


class SlackPost(BaseModel):
    channel: str
    text: str = Field(max_length=3000)
    idempotency_key: str


@tool("slack.post", "Post an internal Slack message", SlackPost, scope="slack.write")
def slack_post(ex: AgentExecution, a: SlackPost) -> dict[str, Any]:
    return connectors.call(ex.db, ex.workspace_id, "slack", "post_message", a.model_dump(exclude={"idempotency_key"}), a.idempotency_key)


class CrmNote(BaseModel):
    customer_id: str | None = None
    body: str
    idempotency_key: str


@tool("crm.add_note", "Add an internal CRM note", CrmNote, scope="crm.write")
def crm_note(ex: AgentExecution, a: CrmNote) -> dict[str, Any]:
    return connectors.call(ex.db, ex.workspace_id, "crm", "add_note", a.model_dump(exclude={"idempotency_key"}), a.idempotency_key)


# action_type -> (tool name, connector kind)
ACTION_TOOLS: dict[str, tuple[str, str]] = {
    "issue_refund": ("payments.refund", "payments"),
    "apply_account_credit": ("crm.apply_credit", "payments"),
    "send_customer_email": ("email.send", "email"),
    "update_account": ("crm.update_account", "crm"),
    "create_jira_issue": ("jira.create_issue", "jira"),
    "post_slack_message": ("slack.post", "slack"),
    "add_crm_note": ("crm.add_note", "crm"),
}


def days_since(iso: str) -> int:
    d = datetime.fromisoformat(iso)
    from app.db import utcnow

    if d.tzinfo is None:
        from datetime import UTC

        d = d.replace(tzinfo=UTC)
    return (utcnow() - d).days
