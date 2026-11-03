"""SQLAlchemy models.

Grouped by module: platform (identity, audit, workflow, approvals, agents, integrations),
operations (customers, cases), proposal intelligence (RFPs, requirements, knowledge, proposals).
Business modules reference platform tables but never each other.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, new_id, utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")
EMBED_DIM = 384


def pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_id)


def ws_fk() -> Mapped[str]:
    return mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)


# --------------------------------------------------------------------------- platform
class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[str] = pk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = pk()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "slug"),)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = pk()
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    # admin | operator | approver | reviewer | viewer
    role: Mapped[str] = mapped_column(String(20), default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginEvent(Base):
    """Every sign-in attempt, successful or not. Kept for security review and user-visible history."""

    __tablename__ = "login_events"
    id: Mapped[str] = pk()
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    org_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(40))  # ok | bad_password | unknown_user | locked | inactive
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class AuditEvent(Base):
    """Append-only, hash-chained audit trail (tamper-evident per workspace)."""

    __tablename__ = "audit_events"
    __table_args__ = (UniqueConstraint("workspace_id", "seq", name="uq_audit_ws_seq"),)
    id: Mapped[str] = pk()
    seq: Mapped[int] = mapped_column(Integer, index=True)
    workspace_id: Mapped[str] = ws_fk()
    actor_type: Mapped[str] = mapped_column(String(20))  # user | agent | workflow | system
    actor_id: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    n8n_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class InboundEvent(TimestampMixin, Base):
    """Idempotency ledger for every externally triggered event."""

    __tablename__ = "inbound_events"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    source: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing | done | failed
    result_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (Index("ix_workflow_runs_ws_started", "workspace_id", "started_at"),)
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    workflow_key: Mapped[str] = mapped_column(String(60), index=True)
    n8n_execution_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|waiting|succeeded|failed
    trigger: Mapped[str] = mapped_column(String(40), default="webhook")
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="run", order_by="WorkflowStep.started_at", cascade="all, delete-orphan"
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id: Mapped[str] = pk()
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    node: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20))  # succeeded | failed | waiting | skipped
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    run: Mapped[WorkflowRun] = relationship(back_populates="steps")


class DeadLetter(TimestampMixin, Base):
    __tablename__ = "dead_letters"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    source: Mapped[str] = mapped_column(String(80))
    workflow_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    n8n_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | replayed | discarded
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_ws_status", "workspace_id", "status"),)
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    action_type: Mapped[str] = mapped_column(String(60))
    scope: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    scope_hash: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    risk_level: Mapped[str] = mapped_column(String(10))  # low | medium | high | critical
    policy_rule: Mapped[str] = mapped_column(String(120))
    required_role: Mapped[str] = mapped_column(String(20), default="approver")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending | approved | rejected | expired | executed | failed
    requested_by: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Set by n8n Workflow E while it waits for the decision (Wait node resume URL).
    resume_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    n8n_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_ws_created", "workspace_id", "created_at"),)
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10), default="info")
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_ws_started", "workspace_id", "started_at"),)
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    agent: Mapped[str] = mapped_column(String(60), index=True)
    task: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    # running | succeeded | failed | escalated | cancelled | cancel_requested | budget_exceeded
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    context_refs: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    security_flags: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    budget: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tool_calls: Mapped[list[ToolCall]] = relationship(
        back_populates="run", order_by="ToolCall.created_at", cascade="all, delete-orphan"
    )


class ToolCall(TimestampMixin, Base):
    __tablename__ = "tool_calls"
    id: Mapped[str] = pk()
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # redacted
    result_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20))  # ok | error | denied
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    run: Mapped[AgentRun] = relationship(back_populates="tool_calls")


class IntegrationConnection(TimestampMixin, Base):
    __tablename__ = "integration_connections"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    kind: Mapped[str] = mapped_column(String(20))  # email | slack | jira | crm | rest
    mode: Mapped[str] = mapped_column(String(20))  # live | simulator
    display_name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # non-secret config only
    secret_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)  # env var name
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # healthy | degraded | down | unknown
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("workspace_id", "kind"),)


class SimRecord(TimestampMixin, Base):
    """Records written by the local integration simulators (never presented as live)."""

    __tablename__ = "sim_records"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    connector: Mapped[str] = mapped_column(String(20), index=True)
    operation: Mapped[str] = mapped_column(String(60))
    external_id: Mapped[str] = mapped_column(String(60), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    response: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[str] = pk()
    suite: Mapped[str] = mapped_column(String(60), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    uses_fixtures: Mapped[bool] = mapped_column(Boolean, default=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    results: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- operations
class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), index=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), default="standard")  # standard | premium | enterprise
    crm_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    account_balance: Mapped[float] = mapped_column(Float, default=0.0)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)


class Case(TimestampMixin, Base):
    __tablename__ = "cases"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20), default="request")  # request | incident
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30))  # email | webhook | manual | monitoring
    source_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[str] = mapped_column(String(4), default="P3")
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    dedup_key: Mapped[str] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    triage: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    research: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    resolution: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    draft_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    security_flags: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    external_refs: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer: Mapped[Customer | None] = relationship()
    events: Mapped[list[CaseEvent]] = relationship(order_by="CaseEvent.created_at", cascade="all, delete-orphan")
    actions: Mapped[list[CaseAction]] = relationship(order_by="CaseAction.created_at", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("workspace_id", "number"), Index("ix_cases_ws_status", "workspace_id", "status"),
                      Index("ix_cases_ws_created", "workspace_id", "created_at"))


class CaseEvent(TimestampMixin, Base):
    __tablename__ = "case_events"
    id: Mapped[str] = pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor: Mapped[str] = mapped_column(String(120))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class CaseAction(TimestampMixin, Base):
    __tablename__ = "case_actions"
    id: Mapped[str] = pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(60))
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    # proposed | pending_approval | approved | executing | executed | verified | failed | rejected
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approvals.id"), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    verification: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- proposal intelligence
class Rfp(TimestampMixin, Base):
    __tablename__ = "rfps"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    title: Mapped[str] = mapped_column(String(300))
    issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="received", index=True)
    submission_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default=new_id)
    deadlines: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    security_flags: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    last_deadline_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documents: Mapped[list[RfpDocument]] = relationship(order_by="RfpDocument.created_at", cascade="all, delete-orphan")


class RfpDocument(TimestampMixin, Base):
    __tablename__ = "rfp_documents"
    id: Mapped[str] = pk()
    rfp_id: Mapped[str] = mapped_column(ForeignKey("rfps.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extraction_warnings: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    pages: Mapped[list[RfpPage]] = relationship(order_by="RfpPage.page_no", cascade="all, delete-orphan")


class RfpPage(Base):
    __tablename__ = "rfp_pages"
    id: Mapped[str] = pk()
    document_id: Mapped[str] = mapped_column(ForeignKey("rfp_documents.id", ondelete="CASCADE"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class RfpSection(Base):
    __tablename__ = "rfp_sections"
    id: Mapped[str] = pk()
    document_id: Mapped[str] = mapped_column(ForeignKey("rfp_documents.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    page_start: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)


class Requirement(TimestampMixin, Base):
    __tablename__ = "requirements"
    id: Mapped[str] = pk()
    rfp_id: Mapped[str] = mapped_column(ForeignKey("rfps.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("rfp_documents.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    obligation: Mapped[str] = mapped_column(String(20))  # mandatory | optional | informational
    category: Mapped[str] = mapped_column(String(20))
    # technical | commercial | submission | evaluation | deadline | attachment | contractual | general
    page: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(300), nullable=True)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    extraction_method: Mapped[str] = mapped_column(String(30))  # rules | llm | rules+llm | human
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance: Mapped[ComplianceItem | None] = relationship(back_populates="requirement", uselist=False, cascade="all, delete-orphan")


class ComplianceItem(Base):
    __tablename__ = "compliance_items"
    id: Mapped[str] = pk()
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="unverified")
    # compliant | partially_compliant | non_compliant | unverified
    evidence: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    missing_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | changed
    assessed_by: Mapped[str] = mapped_column(String(40), default="engine")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    requirement: Mapped[Requirement] = relationship(back_populates="compliance")


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = ws_fk()
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(40))
    # capability | certification | reference_project | product | standard_response | policy | previous_proposal
    source: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunks: Mapped[list[KnowledgeChunk]] = relationship(order_by="KnowledgeChunk.ordinal", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("workspace_id", "sha256"),)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = pk()
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
    __table_args__ = (
        Index(
            "ix_knowledge_chunks_fts",
            # expression index for lexical retrieval
            sa_text("to_tsvector('english', text)"),
            postgresql_using="gin",
        ),
    )


class Proposal(TimestampMixin, Base):
    __tablename__ = "proposals"
    id: Mapped[str] = pk()
    rfp_id: Mapped[str] = mapped_column(ForeignKey("rfps.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft | in_review | changes_requested | approved | exported
    sections: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    generator: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_by: Mapped[str] = mapped_column(String(64))
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[list[ProposalComment]] = relationship(order_by="ProposalComment.created_at", cascade="all, delete-orphan")


class ProposalComment(TimestampMixin, Base):
    __tablename__ = "proposal_comments"
    id: Mapped[str] = pk()
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id", ondelete="CASCADE"), index=True)
    section_key: Mapped[str] = mapped_column(String(60))
    author_id: Mapped[str] = mapped_column(String(36))
    author_name: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class ExportArtifact(TimestampMixin, Base):
    __tablename__ = "export_artifacts"
    id: Mapped[str] = pk()
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    final: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
