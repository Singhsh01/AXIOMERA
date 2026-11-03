"""Enterprise operations agents.

Triage, Research, Resolution, Communication and Verification. Policy-relevant decisions
(category, priority, refund eligibility, which actions need approval) are deterministic; models
are used for summarisation, extraction and drafting, and their output is validated.

The Resolution stage is a LangGraph state machine with bounded loops:
    plan ─▶ check_evidence ─(missing & budget)─▶ gather ─▶ plan
                        └─▶ draft_reply ─▶ validate_reply ─(fail & budget)─▶ draft_reply
                                                       └─▶ finalize | escalate
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents import tools as T
from app.agents.providers import DeterministicProvider
from app.agents.runtime import AgentExecution, Budget
from app.core import guard
from app.db import new_id
from app.models import Case, CaseAction, Customer
from app.ops import triage as rules

REFUND_WINDOW_DAYS = 30

TRIAGE_TOOLS = {"crm.lookup_customer", "cases.find_related"}
RESEARCH_TOOLS = {"crm.lookup_customer", "orders.get", "cases.find_related", "knowledge.search"}
RESOLUTION_TOOLS = {"orders.get", "knowledge.search"}
EXECUTOR_TOOLS = {t for t, _ in T.ACTION_TOOLS.values()}
VERIFY_TOOLS = {"connector.fetch"}


# ------------------------------------------------------------------ structured outputs
class TriageOutput(BaseModel):
    summary: str = Field(max_length=400)
    category: str
    priority: Literal["P1", "P2", "P3", "P4"]
    confidence: float = Field(ge=0, le=1)
    entities: dict[str, Any] = Field(default_factory=dict)
    reasoning_summary: str


class ReplyDraft(BaseModel):
    subject: str
    body: str
    reasoning_summary: str


# ------------------------------------------------------------------ triage
def run_triage(db: Session, case: Case, correlation_id: str) -> dict[str, Any]:
    ex = AgentExecution(db, case.workspace_id, "triage-agent", f"Triage case #{case.number}", TRIAGE_TOOLS, "triage@1.3",
                        Budget(max_steps=6, max_tool_calls=4), correlation_id, "case", case.id)
    try:
        text = f"{case.title}\n\n{case.description}"
        flags = guard.scan(text, f"case:{case.number}").flags
        ex.flag(flags)
        email = (case.triage or {}).get("sender") or (case.customer.email if case.customer else None)
        cust = ex.call_tool("crm.lookup_customer", email=email) if email else {"found": False}
        tier = cust.get("tier", "standard") if cust.get("found") else "standard"
        category, conf, scores = rules.classify(text)
        prio, prio_reason = rules.priority(category, text, tier)
        entities = rules.extract_entities(text)
        ex.checkpoint("rules", {"category": category, "priority": prio})

        def fixture() -> TriageOutput:
            first = re.split(r"(?<=[.!?])\s", case.description.strip())[0][:300]
            return TriageOutput(summary=f"{case.title.strip()} — {first}", category=category, priority=prio, confidence=conf,
                                entities=entities, reasoning_summary=f"Rules matched {category} ({scores or 'no keywords'}); {prio_reason}.")

        out: TriageOutput = ex.llm(
            instructions="Summarise the customer request in one sentence and extract order ids, invoice ids and amounts.",
            trusted_context=f"Rule-based classification: category={category}, priority={prio}. Customer tier: {tier}.",
            untrusted=[("customer_message", text)], schema=TriageOutput, fixture=fixture)
        # Deterministic fields always win over model output.
        result = {
            "summary": out.summary, "category": category, "priority": prio, "priority_reason": prio_reason,
            "confidence": conf, "rule_scores": scores, "entities": entities, "customer": cust if cust.get("found") else None,
            "tier": tier, "security_flags": flags, "sender": email,
            "next": "human_review" if flags else ("close_spam" if category == "spam" else "research"),
        }
        if case.customer_id is None and cust.get("found"):
            case.customer_id = cust["id"]
        related = ex.call_tool("cases.find_related", case_id=case.id, customer_id=case.customer_id, category=category)
        result["related_cases"] = related
        ex.finish(result, out.reasoning_summary)
        return result
    except Exception as e:
        ex.fail(e)
        raise


# ------------------------------------------------------------------ research
def run_research(db: Session, case: Case, correlation_id: str) -> dict[str, Any]:
    ex = AgentExecution(db, case.workspace_id, "research-agent", f"Research case #{case.number}", RESEARCH_TOOLS, "research@1.2",
                        Budget(max_steps=8, max_tool_calls=8), correlation_id, "case", case.id)
    try:
        tri = case.triage
        evidence: list[dict[str, Any]] = []
        customer = tri.get("customer")
        orders = []
        if customer:
            for oid in tri.get("entities", {}).get("order_ids", []):
                o = ex.call_tool("orders.get", customer_id=customer["id"], order_id=oid)
                if o.get("found"):
                    orders.append(o)
            if not orders and tri["category"] == "billing_refund" and customer.get("orders"):
                latest = sorted(customer["orders"], key=lambda o: o["date"], reverse=True)[0]
                orders.append({"found": True, **latest, "inferred": True})
        ex.checkpoint("orders", {"orders": [o["id"] for o in orders]})
        policy_query = {
            "billing_refund": "refund policy eligibility window days approval",
            "technical_outage": "incident escalation outage severity SLA response",
            "security": "security incident response escalation",
            "account_access": "account access password reset identity verification",
            "account_change": "account changes plan upgrade downgrade cancellation",
            "billing_invoice": "invoices VAT billing corrections",
        }.get(tri["category"], "customer support policy response times")
        hits = ex.call_tool("knowledge.search", query=policy_query, kinds=["policy"], k=3)
        for h in hits:
            evidence.append({"chunk_id": h["chunk_id"], "document": h["document_title"], "heading": h["heading"],
                             "excerpt": h["text"][:400], "score": h["scores"]["rrf"]})
        result = {"orders": orders, "policy_evidence": evidence, "related_cases": tri.get("related_cases", []),
                  "next": "resolve"}
        ex.finish(result, f"Collected {len(orders)} order record(s) and {len(evidence)} policy passages.")
        return result
    except Exception as e:
        ex.fail(e)
        raise


# ------------------------------------------------------------------ resolution (LangGraph)
class ResolveState(TypedDict, total=False):
    actions: list[dict[str, Any]]
    missing: list[str]
    gather_rounds: int
    reply: dict[str, Any]
    reply_issues: list[str]
    draft_rounds: int
    outcome: str
    rationale: str


def _proposals(case: Case, research: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], str]:
    tri = case.triage
    cat = tri["category"]
    cust = tri.get("customer")
    ent = tri.get("entities", {})
    key = case.id[:8]
    actions: list[dict[str, Any]] = []
    missing: list[str] = []
    rationale = ""
    if cat == "spam":
        return [], [], "Classified as spam; no action."
    if cat == "billing_refund":
        if not cust:
            return [], ["customer_record"], "Sender is not a known customer; identity must be verified before any refund."
        orders = research.get("orders", [])
        if not orders:
            return [], ["order_id"], "No matching order found; customer must provide an order id."
        o = orders[0]
        age = T.days_since(o["date"])
        if o.get("status") == "refunded":
            rationale = f"Order {o['id']} was already refunded; refund declined."
        elif age > REFUND_WINDOW_DAYS:
            rationale = f"Order {o['id']} is {age} days old, outside the {REFUND_WINDOW_DAYS}-day refund window; offering credit instead requires approval."
            actions.append({"action_type": "apply_account_credit", "params": {"customer_id": cust["id"], "amount": round(min(o["amount"], 50.0), 2), "currency": "EUR", "reason": f"Goodwill credit for {o['id']} (outside refund window)"}})
        else:
            requested = [a for a in ent.get("amounts", []) if 0 < a <= o["amount"]]
            amount = round(requested[0] if requested else o["amount"], 2)
            actions.append({"action_type": "issue_refund", "params": {"customer_id": cust["id"], "order_id": o["id"], "amount": amount, "currency": "EUR"}})
            rationale = f"Order {o['id']} ({age} days old, €{o['amount']:.2f}) is within the {REFUND_WINDOW_DAYS}-day window; refund of €{amount:.2f} proposed."
            if o.get("inferred"):
                rationale += " Order inferred as the most recent order; reviewer should confirm."
    elif cat in {"technical_outage", "security"}:
        team = rules.TEAM_FOR_CATEGORY[cat]
        actions.append({"action_type": "create_jira_issue", "params": {"summary": f"[{case.priority}] {case.title}"[:240], "description": tri["summary"], "issue_type": "Incident" if cat == "security" else "Bug"}})
        actions.append({"action_type": "post_slack_message", "params": {"channel": f"#{team}-alerts", "text": f":rotating_light: {case.priority} case #{case.number}: {case.title}"}})
        rationale = f"{cat.replace('_', ' ').title()} routed to {team}; internal ticket and alert created automatically (low-risk internal actions)."
    elif cat == "technical_bug":
        actions.append({"action_type": "create_jira_issue", "params": {"summary": case.title[:240], "description": tri["summary"], "issue_type": "Bug"}})
        rationale = "Bug report forwarded to engineering backlog."
    elif cat == "account_change" and cust:
        m = re.search(r"\b(upgrade|downgrade)\b.*\b(standard|premium|enterprise)\b", case.description, re.I)
        if m:
            actions.append({"action_type": "update_account", "params": {"customer_id": cust["id"], "changes": {"tier": m.group(2).lower()}}})
            rationale = f"Customer requested a plan change to {m.group(2).lower()}; account modification requires approval."
        else:
            rationale = "Account change request without a recognised change; agent will confirm details."
    elif cat in {"billing_invoice", "feature_request"}:
        actions.append({"action_type": "add_crm_note", "params": {"customer_id": cust["id"] if cust else None, "body": f"Case #{case.number}: {tri['summary']}"}})
        rationale = "Logged to CRM for the account team."
    else:
        rationale = "Informational response."
    for a in actions:
        a["params"] = {k: v for k, v in a["params"].items()}
        a["idempotency_key"] = f"case-{key}-{a['action_type']}"
    return actions, missing, rationale


def _reply_fixture(case: Case, actions: list[dict[str, Any]], missing: list[str]) -> ReplyDraft:
    name = (case.triage.get("customer") or {}).get("name", "there").split(" ")[0]
    lines = [f"Hi {name},", "", f"Thank you for contacting us about \"{case.title.strip()}\". Your reference is case #{case.number}."]
    types = {a["action_type"] for a in actions}
    if "issue_refund" in types:
        a = next(a for a in actions if a["action_type"] == "issue_refund")
        lines.append(f"We have reviewed order {a['params']['order_id']} and submitted a refund of €{a['params']['amount']:.2f} for approval. "
                     "You will receive a confirmation as soon as it has been processed.")
    elif "apply_account_credit" in types:
        lines.append("Your order falls outside our refund window, so we have proposed an account credit instead. We will confirm once it is approved.")
    elif "order_id" in missing:
        lines.append("Could you reply with the order number (it starts with ORD-) so we can look into this for you?")
    elif "customer_record" in missing:
        lines.append("We could not match this email address to an account. Please reply from the address registered with us.")
    elif "create_jira_issue" in types:
        lines.append("Our engineering team has been alerted and is investigating. We will keep you updated on progress.")
    elif "update_account" in types:
        lines.append("We have prepared the requested account change and will confirm once it has been applied.")
    else:
        lines.append("A member of our team will follow up shortly.")
    lines += ["", "Kind regards,", "Customer Operations"]
    return ReplyDraft(subject=f"Re: {case.title.strip()} [Case #{case.number}]", body="\n".join(lines),
                      reasoning_summary="Template reply reflecting proposed actions; no outcome promised before approval.")


def validate_reply(body: str, actions: list[dict[str, Any]]) -> list[str]:
    """Deterministic claim checks on customer-facing text."""
    issues = []
    allowed = {f"{a['params'].get('amount'):.2f}" for a in actions if a["params"].get("amount")}
    for m in re.finditer(r"€\s?(\d+(?:[.,]\d{2})?)", body):
        if f"{float(m.group(1).replace(',', '.')):.2f}" not in allowed:
            issues.append(f"amount €{m.group(1)} not backed by a proposed action")
    if re.search(r"\b(has been|have been|was) (refunded|credited|processed|applied)\b", body, re.I):
        issues.append("reply claims an action is complete before approval/execution")
    if re.search(r"\b(guarantee|guaranteed|promise)\b", body, re.I):
        issues.append("reply makes a guarantee")
    return issues


def run_resolution(db: Session, case: Case, correlation_id: str) -> dict[str, Any]:
    ex = AgentExecution(db, case.workspace_id, "resolution-agent", f"Resolve case #{case.number}", RESOLUTION_TOOLS, "resolution@2.0",
                        Budget(max_steps=14, max_tool_calls=6), correlation_id, "case", case.id)
    comms = AgentExecution(db, case.workspace_id, "communication-agent", f"Draft reply for case #{case.number}", set(), "communication@1.4",
                           Budget(max_steps=6, max_tool_calls=0), correlation_id, "case", case.id, parent_run_id=ex.run.id)
    research = case.research or {}

    def plan(state: ResolveState) -> ResolveState:
        actions, missing, rationale = _proposals(case, research)
        ex.checkpoint("plan", {"actions": [a["action_type"] for a in actions], "missing": missing})
        return {"actions": actions, "missing": missing, "rationale": rationale}

    def route_evidence(state: ResolveState) -> str:
        if "order_id" in state["missing"] and state.get("gather_rounds", 0) < 1 and case.triage.get("customer"):
            return "gather"
        return "draft"

    def gather(state: ResolveState) -> ResolveState:
        # One bounded attempt: look for an order id the triage regex missed (e.g. lowercase, spaced).
        m = re.search(r"\bord[\s\-_]?(\d{4,8})\b", case.description, re.I)
        if m:
            o = ex.call_tool("orders.get", customer_id=case.triage["customer"]["id"], order_id=f"ORD-{m.group(1)}")
            if o.get("found"):
                research.setdefault("orders", []).append(o)
        ex.checkpoint("gather", {"found": bool(m)})
        return {"gather_rounds": state.get("gather_rounds", 0) + 1}

    def draft(state: ResolveState) -> ResolveState:
        acts, missing = state["actions"], state["missing"]
        fixture = lambda: _reply_fixture(case, acts, missing)  # noqa: E731
        out: ReplyDraft = comms.llm(
            instructions="Draft a short, polite customer reply. Never state that a refund, credit or change has been completed; "
                         "say it is submitted for approval. Only mention amounts listed in the proposed actions.",
            trusted_context=f"Case #{case.number}. Proposed actions: {acts}. Missing information: {missing}. Rationale: {state['rationale']}",
            untrusted=[("customer_message", case.description)], schema=ReplyDraft, fixture=fixture)
        comms.checkpoint("draft", {"subject": out.subject})
        return {"reply": out.model_dump(), "draft_rounds": state.get("draft_rounds", 0) + 1}

    def validate(state: ResolveState) -> ResolveState:
        issues = validate_reply(state["reply"]["body"], state["actions"])
        ex.checkpoint("validate_reply", {"issues": issues})
        return {"reply_issues": issues}

    def route_validation(state: ResolveState) -> str:
        if not state["reply_issues"]:
            return "finalize"
        return "draft" if state["draft_rounds"] < 2 else "escalate"

    def finalize(state: ResolveState) -> ResolveState:
        return {"outcome": "proposed"}

    def escalate(state: ResolveState) -> ResolveState:
        # Fall back to the validated template rather than sending unvalidated text.
        safe = _reply_fixture(case, state["actions"], state["missing"]).model_dump()
        return {"outcome": "escalated", "reply": safe}

    g = StateGraph(ResolveState)
    for name, fn in [("plan", plan), ("gather", gather), ("draft", draft), ("validate", validate), ("finalize", finalize), ("escalate", escalate)]:
        g.add_node(name, fn)
    g.set_entry_point("plan")
    g.add_conditional_edges("plan", route_evidence, {"gather": "gather", "draft": "draft"})
    g.add_edge("gather", "plan")
    g.add_edge("draft", "validate")
    g.add_conditional_edges("validate", route_validation, {"finalize": "finalize", "draft": "draft", "escalate": "escalate"})
    g.add_edge("finalize", END)
    g.add_edge("escalate", END)

    try:
        final: ResolveState = g.compile().invoke({"gather_rounds": 0, "draft_rounds": 0}, {"recursion_limit": 20})
        comms.finish(final["reply"], final["reply"].get("reasoning_summary", "Reply drafted."))
        result = {"actions": final["actions"], "missing_information": final["missing"], "rationale": final["rationale"],
                  "reply": final["reply"], "reply_issues": final.get("reply_issues", []), "outcome": final["outcome"],
                  "graph": "langgraph:plan→check_evidence→draft→validate"}
        ex.finish(result, final["rationale"])
        return result
    except Exception as e:
        ex.fail(e)
        if comms.run.status == "running":
            comms.fail(e)
        raise


# ------------------------------------------------------------------ execution & verification (deterministic)
def execute_action(db: Session, case: Case, action: CaseAction, correlation_id: str) -> dict[str, Any]:
    tool_name, _ = T.ACTION_TOOLS[action.action_type]
    ex = AgentExecution(db, case.workspace_id, "action-executor", f"Execute {action.action_type} for case #{case.number}",
                        EXECUTOR_TOOLS, "executor@1.0", Budget(max_steps=3, max_tool_calls=2), correlation_id, "case_action",
                        action.id, provider=DeterministicProvider())
    try:
        args = dict(action.params)
        args["idempotency_key"] = f"action-{action.id}"
        if action.approval_id:
            args["approval_id"] = action.approval_id
        res = ex.call_tool(tool_name, **args)
        ex.finish(res, f"Executed {action.action_type} via {res.get('mode')} connector ({res.get('external_id')}).")
        return res
    except Exception as e:
        ex.fail(e)
        raise


def verify_action(db: Session, case: Case, action: CaseAction, correlation_id: str) -> dict[str, Any]:
    _, connector = T.ACTION_TOOLS[action.action_type]
    ex = AgentExecution(db, case.workspace_id, "verification-agent", f"Verify {action.action_type} for case #{case.number}",
                        VERIFY_TOOLS, "verify@1.1", Budget(max_steps=3, max_tool_calls=2), correlation_id, "case_action",
                        action.id, provider=DeterministicProvider())
    try:
        ext = (action.result or {}).get("external_id")
        checks = []
        record = ex.call_tool("connector.fetch", connector=connector, external_id=ext) if ext else None
        checks.append({"check": "record_exists", "passed": record is not None})
        if record and "payload" in record:
            for k, v in action.params.items():
                if k in record["payload"]:
                    checks.append({"check": f"field:{k}", "passed": record["payload"][k] == v, "expected": v, "actual": record["payload"][k]})
        if action.action_type == "apply_account_credit":
            c = db.get(Customer, action.params["customer_id"])
            checks.append({"check": "balance_updated", "passed": c.account_balance >= action.params["amount"]})
        verified = all(c["passed"] for c in checks)
        out = {"verified": verified, "checks": checks, "mode": (record or {}).get("mode")}
        ex.finish(out, "All checks passed." if verified else "Verification failed; escalating.")
        return out
    except Exception as e:
        ex.fail(e)
        raise


def correlation() -> str:
    return new_id()
