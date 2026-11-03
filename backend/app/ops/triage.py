"""Deterministic triage rules.

Classification, priority and SLA assignment are rule-based by design: they are auditable,
reproducible and evaluated against a labelled dataset (evals/datasets/cases.jsonl). An LLM is
used only to *summarise* and *extract*, never to override the policy-relevant decisions.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

CATEGORY_RULES: dict[str, list[tuple[str, float]]] = {
    "security": [(r"\b(breach|phishing|compromised|hacked|unauthori[sz]ed access|leak(ed)?|vulnerab|malware|suspicious login)\b", 3.0)],
    "technical_outage": [(r"\b(outage|down|unavailable|not loading|5\d\d error|cannot access the (app|platform|service)|service (is )?degraded|timeouts?)\b", 2.5),
                         (r"\b(production|all users|entire team|nobody can)\b", 1.0)],
    "billing_refund": [(r"\b(refund|money back|reimburse|charged twice|double[- ]charged|duplicate charge|overcharged)\b", 3.0)],
    "billing_invoice": [(r"\b(invoice|receipt|vat|billing address|payment method|tax id)\b", 2.0)],
    "account_access": [(r"\b(password|reset|locked out|log ?in|2fa|mfa|sign ?in|cannot access my account)\b", 2.0)],
    "account_change": [(r"\b(change (my|our) (plan|email|address|owner)|upgrade|downgrade|cancel (my|our) (subscription|account)|close (my|our) account|add seats?)\b", 2.2)],
    "technical_bug": [(r"\b(bug|error|crash(es|ed)?|broken|exception|does not work|doesn't work|incorrect|wrong result)\b", 1.6)],
    "feature_request": [(r"\b(feature request|would be (great|nice)|could you add|suggestion|roadmap|wish)\b", 2.0)],
    "spam": [(r"\b(viagra|crypto giveaway|seo services|buy followers|lottery|winner)\b", 3.0)],
}

PRIORITY_SLA_HOURS = {"P1": 1, "P2": 4, "P3": 24, "P4": 72}
TIER_FACTOR = {"enterprise": 0.5, "premium": 0.75, "standard": 1.0}

TEAM_FOR_CATEGORY = {
    "security": "security", "technical_outage": "sre", "technical_bug": "engineering", "billing_refund": "billing",
    "billing_invoice": "billing", "account_access": "support", "account_change": "support",
    "feature_request": "product", "general": "support", "spam": "support",
}

AMOUNT = re.compile(r"(?:€|eur|usd|\$)\s?(\d{1,6}(?:[.,]\d{2})?)|(\d{1,6}(?:[.,]\d{2})?)\s?(?:€|eur|euros?|usd|dollars?)", re.I)
ORDER = re.compile(r"\b(ORD-\d{4,8})\b", re.I)
INVOICE = re.compile(r"\b(INV-\d{4,8})\b", re.I)


def classify(text: str) -> tuple[str, float, dict[str, float]]:
    scores: dict[str, float] = {}
    for cat, rules in CATEGORY_RULES.items():
        s = sum(w * len(re.findall(p, text, re.I)) for p, w in rules)
        if s:
            scores[cat] = s
    if not scores:
        return "general", 0.5, {}
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    total = sum(scores.values())
    confidence = round(min(0.98, 0.55 + 0.45 * scores[best] / total * min(1.0, scores[best] / 3)), 2)
    return best, confidence, scores


def priority(category: str, text: str, tier: str) -> tuple[str, str]:
    t = text.lower()
    if category == "security":
        return "P1", "security issues are always P1"
    if category == "technical_outage":
        if tier == "enterprise" or re.search(r"\b(production|all users|entire|nobody)\b", t):
            return "P1", "outage affecting production or an enterprise customer"
        return "P2", "service outage"
    if category in {"billing_refund", "account_access"}:
        return ("P2", f"{category} for enterprise customer") if tier == "enterprise" else ("P3", "standard handling")
    if re.search(r"\b(urgent|asap|immediately|critical)\b", t) and tier in {"enterprise", "premium"}:
        return "P2", "urgent request from premium/enterprise customer"
    if category in {"feature_request", "spam"}:
        return "P4", "non-urgent"
    return "P3", "standard handling"


def sla_due(priority_: str, tier: str, start: datetime) -> datetime:
    hours = PRIORITY_SLA_HOURS[priority_] * TIER_FACTOR.get(tier, 1.0)
    return start + timedelta(hours=hours)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def extract_entities(text: str) -> dict:
    amounts = []
    for m in AMOUNT.finditer(text):
        raw = m.group(1) or m.group(2)
        try:
            amounts.append(_num(raw))
        except ValueError:
            pass
    return {
        "amounts": amounts,
        "order_ids": sorted({m.upper() for m in ORDER.findall(text)}),
        "invoice_ids": sorted({m.upper() for m in INVOICE.findall(text)}),
    }
