"""Requirement and deadline extraction.

Rules find candidate obligations at sentence level and keep exact character offsets into the
page text, so every requirement can be highlighted in the source. When a live model is
configured it proposes additional requirements as verbatim quotes; a quote is only accepted if
it can be located in the page text (hallucinated requirements are dropped).
Sentences that try to instruct automated reviewers are excluded and raised as security flags.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.core import guard

MANDATORY = re.compile(r"\b(shall|must|is required to|are required to|is mandatory|are mandatory|mandatory|required)\b", re.I)
OPTIONAL = re.compile(r"\b(should|may|is desirable|are desirable|preferred|optional|nice to have|is encouraged)\b", re.I)
EVALUATION = re.compile(r"\b(will be evaluated|evaluation criteri|weighted|weighting|scored|award criteri)", re.I)

CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("deadline", re.compile(r"\b(deadline|no later than|not later than|by \d{1,2}[ .]\w+|closing date|due date)\b", re.I)),
    ("attachment", re.compile(r"\b(attach\w*|annex|appendix|enclose\w*|copy of|copies of|cv|curricul\w*|certificate copies)\b", re.I)),
    ("submission", re.compile(r"\b(submit|submission|submitted|tender portal|page limit|pages?|font|format|copies|signed by|electronic(ally)?)\b", re.I)),
    ("evaluation", EVALUATION),
    ("contractual", re.compile(r"\b(contract|liability|insurance|indemn\w*|terminat\w*|governing law|warrant\w*|penalt\w*|data processing agreement|dpa|gdpr|subcontract\w*|confidential\w*)\b", re.I)),
    ("commercial", re.compile(r"\b(price|prices|pricing|cost|costs|fee|fees|payment|invoice|currency|eur|euro|discount|budget|rate card|tco)\b", re.I)),
]

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_PATTERNS = [
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTHS})\s+(\d{{4}})(?:[, ]+(?:at\s+)?(\d{{1,2}}):(\d{{2}}))?", re.I), "dmy"),
    (re.compile(rf"\b({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})(?:[, ]+(?:at\s+)?(\d{{1,2}}):(\d{{2}}))?", re.I), "mdy"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?"), "iso"),
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})(?:,?\s+(\d{1,2}):(\d{2}))?"), "dot"),
]
DEADLINE_KIND = [
    ("questions", re.compile(r"\b(question|clarification|enquir|inquir)", re.I)),
    ("submission", re.compile(r"\b(submi|proposal|tender|bid|offer)s?", re.I)),
    ("award", re.compile(r"\b(award|notification|decision)", re.I)),
    ("contract_start", re.compile(r"\b(start|commence|go-live|kick-?off)", re.I)),
]
_CH = r"(?:[^.!?\n]|\.(?=\d))"
SENTENCE = re.compile(rf"{_CH}*(?:\n(?!\s*\n)(?!\s*(?:\d+(?:\.\d+)*\.?\s|[-•*]\s|[A-Z]{{2,5}}-\d)){_CH}*)*[.!?]?", re.M)
HEADING_LINE = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2})*\.?\s+[A-Z][^.\n]{2,80}\n")


@dataclass
class Candidate:
    page: int
    start: int
    end: int
    text: str
    obligation: str
    category: str
    confidence: float
    section: str | None
    method: str = "rules"


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("-\n", "")).strip()


def categorise(sentence: str) -> str:
    for cat, pat in CATEGORY_RULES:
        if pat.search(sentence):
            return cat
    return "technical"


def _section_for(sections: list[dict], page: int, offset_line: str | None) -> str | None:
    current = None
    for s in sections:
        if s["page"] <= page:
            current = f"{s['number']} {s['title']}"
    return current


def rule_extract(pages: list[str], sections: list[dict]) -> tuple[list[Candidate], list[dict]]:
    out: list[Candidate] = []
    flags: list[dict] = []
    for pno, page in enumerate(pages, start=1):
        for m in SENTENCE.finditer(page):
            raw = m.group(0)
            offset = m.start()
            hm = HEADING_LINE.match(raw)
            if hm and raw[hm.end():].strip():
                raw, offset = raw[hm.end():], offset + hm.end()
            sent = _clean(raw)
            if len(sent) < 25 or len(sent) > 700:
                continue
            lead = len(raw) - len(raw.lstrip())
            start, end = offset + lead, m.end()
            # strip list markers / ids from the front but keep offsets valid
            g = guard.scan(sent, f"page:{pno}")
            if g.suspicious:
                flags += [{**f, "page": pno, "sentence": sent[:200]} for f in g.flags]
                continue
            if EVALUATION.search(sent):
                obligation, conf = "informational", 0.75
            elif MANDATORY.search(sent):
                obligation, conf = "mandatory", 0.8
            elif OPTIONAL.search(sent):
                obligation, conf = "optional", 0.65
            else:
                continue
            if re.match(r"^\s*([A-Z]{2,5}-\d+|\d+(\.\d+)+|[-•*])", raw.lstrip()):
                conf += 0.1
            if re.search(r"\b(the (bidder|supplier|vendor|contractor|provider|tenderer)|proposals?|solution|offer)\b", sent, re.I):
                conf += 0.05
            out.append(Candidate(pno, start, end, sent, obligation, categorise(sent), round(min(conf, 0.97), 2),
                                 _section_for(sections, pno, None)))
    return out, flags


class LLMRequirement(BaseModel):
    quote: str = Field(description="Exact verbatim requirement sentence from the page")
    obligation: str
    category: str


class LLMRequirements(BaseModel):
    requirements: list[LLMRequirement]
    reasoning_summary: str


def locate(page: str, quote: str) -> tuple[int, int] | None:
    """Find a quote in page text tolerant to whitespace differences."""
    q = _clean(quote)
    if len(q) < 20:
        return None
    pattern = r"\s+".join(re.escape(w) for w in q.split(" "))
    m = re.search(pattern, page)
    return (m.start(), m.end()) if m else None


def merge_llm(pages: list[str], rules: list[Candidate], llm_by_page: dict[int, list[LLMRequirement]], sections: list[dict]) -> tuple[list[Candidate], int]:
    """Accept LLM requirements only if verbatim-locatable; mark overlaps as rules+llm."""
    rejected = 0
    merged = list(rules)
    for pno, items in llm_by_page.items():
        for it in items:
            loc = locate(pages[pno - 1], it.quote)
            if not loc:
                rejected += 1
                continue
            s, e = loc
            overlap = next((c for c in merged if c.page == pno and not (e <= c.start or s >= c.end)), None)
            if overlap:
                overlap.method = "rules+llm"
                overlap.confidence = round(min(0.98, overlap.confidence + 0.08), 2)
            else:
                obligation = it.obligation if it.obligation in {"mandatory", "optional", "informational"} else "mandatory"
                merged.append(Candidate(pno, s, e, _clean(pages[pno - 1][s:e]), obligation, it.category if it.category else categorise(it.quote),
                                        0.7, _section_for(sections, pno, None), "llm"))
    merged.sort(key=lambda c: (c.page, c.start))
    return merged, rejected


def _to_dt(m: re.Match, kind: str) -> datetime | None:
    months = {n: i + 1 for i, n in enumerate(MONTHS.split("|"))}
    g = m.groups()
    try:
        if kind == "dmy":
            d, mo, y, hh, mm = int(g[0]), months[g[1].lower()], int(g[2]), g[3], g[4]
        elif kind == "mdy":
            mo, d, y, hh, mm = months[g[0].lower()], int(g[1]), int(g[2]), g[3], g[4]
        elif kind == "iso":
            y, mo, d, hh, mm = int(g[0]), int(g[1]), int(g[2]), g[3], g[4]
        else:
            d, mo, y, hh, mm = int(g[0]), int(g[1]), int(g[2]), g[3], g[4]
        return datetime(y, mo, d, int(hh or 17), int(mm or 0), tzinfo=UTC)
    except (ValueError, KeyError):
        return None


def extract_deadlines(pages: list[str]) -> list[dict]:
    found: dict[tuple[str, str], dict] = {}
    for pno, page in enumerate(pages, start=1):
        for pat, kind in DATE_PATTERNS:
            for m in pat.finditer(page):
                dt = _to_dt(m, kind)
                if not dt:
                    continue
                ctx_start = max(0, page.rfind("\n", 0, max(0, m.start() - 1)) - 160)
                context = _clean(page[ctx_start:m.end() + 40])
                local = _clean(page[max(0, m.start() - 160):m.start()])
                dkind = next((k for k, p in DEADLINE_KIND if p.search(local)), "other")
                key = (dkind, dt.isoformat())
                if key not in found:
                    found[key] = {"kind": dkind, "at": dt.isoformat(), "page": pno, "context": context[-240:]}
    return sorted(found.values(), key=lambda d: d["at"])
