"""Sensitive-data redaction applied before anything is written to audit logs, tool-call records or LLM prompts."""
from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("API_KEY", re.compile(r"\b(?:sk|pk|xox[abp]|ghp|AKIA)[-_A-Za-z0-9]{12,}\b")),
    ("BEARER", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}")),
    ("PASSWORD", re.compile(r"(?i)(password|passwort|pwd)\s*[:=]\s*\S+")),
]

SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization", "card_number", "iban", "cvv"}


def redact_text(text: str) -> str:
    out = text
    for label, pattern in _PATTERNS:
        out = pattern.sub(f"[REDACTED:{label}]", out)
    return out


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else redact(v)) for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
