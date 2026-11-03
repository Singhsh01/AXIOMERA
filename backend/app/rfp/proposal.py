"""Proposal drafting grounded in approved company knowledge.

Each section is produced from retrieved evidence. With the fixture provider, content is
extractive (evidence sentences ranked against the section intent, each with a citation). With a
live model, the model writes prose using only numbered evidence passages and must cite them as
[S#]. In both cases a claim checker runs afterwards: sentences asserting certifications, numbers,
percentages or customer facts that are not present in their cited evidence are removed and
recorded as `unsupported_claims` for the reviewer.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.runtime import AgentExecution, Budget
from app.models import Requirement, Rfp
from app.platform import knowledge
from app.rfp.compliance import CERT, PERCENT

SECTIONS = [
    ("executive_summary", "Executive Summary", "company overview mission capabilities experience value", ["capability", "reference_project"]),
    ("technical_approach", "Technical Approach", "technical approach platform features integration security architecture", ["product", "capability"]),
    ("solution_architecture", "Solution Architecture", "architecture hosting data residency availability scalability encryption", ["product"]),
    ("implementation_methodology", "Implementation Methodology", "implementation methodology agile phases onboarding migration training", ["capability", "standard_response"]),
    ("delivery_plan", "Delivery Plan", "delivery plan timeline milestones project team governance weeks", ["capability", "standard_response"]),
    ("relevant_capabilities", "Relevant Capabilities and References", "reference project customer delivered results", ["reference_project"]),
    ("risks_assumptions", "Risks and Assumptions", "", []),
    ("compliance_response", "Compliance Response", "", []),
    ("supporting_references", "Supporting References", "", []),
]

NUMBERISH = re.compile(r"\b\d[\d.,]*\s?(%|percent|years?|customers?|employees?|engineers?|countries|million|m|k|users|projects)\b", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


class SectionDraft(BaseModel):
    content: str = Field(description="Section prose. Cite evidence as [S1], [S2] …")
    reasoning_summary: str


def claims_in(sentence: str) -> list[str]:
    out = [c.strip() for c in CERT.findall(sentence)]
    out += [m.group(0).strip() for m in NUMBERISH.finditer(sentence)]
    out += [m.group(0) for m in PERCENT.finditer(sentence)]
    return list(dict.fromkeys(out))


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower())


def check_claims(content: str, cited: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    """Remove sentences with claims not found in the evidence they cite (or in any section evidence if uncited)."""
    kept, unsupported = [], []
    all_ev = _norm(" ".join(cited.values()))
    for para in content.split("\n"):
        out_sents = []
        for s in SENT_SPLIT.split(para):
            refs = re.findall(r"\[S(\d+)\]", s)
            scope = _norm(" ".join(cited.get(f"S{r}", "") for r in refs)) if refs else all_ev
            bad = [c for c in claims_in(s) if _norm(c) not in scope]
            if bad:
                unsupported.append({"sentence": s.strip(), "claims": bad})
            else:
                out_sents.append(s)
        kept.append(" ".join(out_sents))
    return "\n".join(kept).strip(), unsupported


def _extractive(query: str, evidence: list[dict[str, Any]], max_sentences: int = 5, used: set[str] | None = None) -> str:
    q = set(knowledge.tokens(query))
    scored = []
    for i, ev in enumerate(evidence, start=1):
        for s in SENT_SPLIT.split(re.sub(r"\s+", " ", ev["text"])):
            s = s.strip().lstrip("-•* ").strip()
            if len(s) < 40 or s.endswith(":"):
                continue
            overlap = len(q & set(knowledge.tokens(s)))
            scored.append((overlap + ev["scores"]["rrf"] * 10, i, s))
    scored.sort(key=lambda t: t[0], reverse=True)
    seen = used if used is not None else set()
    out = []
    for _, i, s in scored:
        if s in seen:
            continue
        seen.add(s)
        out.append(f"{s.rstrip('.')}. [S{i}]")
        if len(out) >= max_sentences:
            break
    return " ".join(out)


def generate(db: Session, rfp: Rfp, requirements: list[Requirement], company: str, correlation_id: str, provider=None) -> dict[str, Any]:
    ex = AgentExecution(db, rfp.workspace_id, "proposal-agent", f"Draft proposal for {rfp.title[:80]}", {"knowledge.search"}, "proposal@1.5",
                        Budget(max_steps=20, max_tool_calls=12, max_tokens=60_000, max_cost_usd=0.75, max_seconds=240),
                        correlation_id, "rfp", rfp.id, provider=provider)
    try:
        reqs = [r for r in requirements if not r.deleted]
        tech_terms = " ".join(r.text for r in reqs if r.category == "technical")[:600]
        sections = []
        used_sentences: set[str] = set()
        for key, title, intent, kinds in SECTIONS:
            if key in {"risks_assumptions", "compliance_response", "supporting_references"}:
                continue
            query = f"{intent} {tech_terms if key in {'technical_approach', 'solution_architecture'} else ''} {rfp.title}".strip()
            hits = ex.call_tool("knowledge.search", query=query[:500], kinds=kinds, k=5)
            cited = {f"S{i}": h["text"] for i, h in enumerate(hits, start=1)}

            def fixture(q=query, h=hits) -> SectionDraft:
                return SectionDraft(content=_extractive(q, h, used=used_sentences), reasoning_summary="Extractive draft from top-ranked approved evidence.")

            numbered = "\n".join(f"[S{i}] ({h['document_title']}) {h['text']}" for i, h in enumerate(hits, start=1))
            draft: SectionDraft = ex.llm(
                instructions=f"Write the '{title}' section of a proposal for {company}. Use ONLY facts in the numbered evidence and cite them as [S#]. "
                             "Do not invent certifications, figures, customers or capabilities. 120-220 words.",
                trusted_context=f"RFP: {rfp.title} (issuer: {rfp.issuer}).\nEvidence:\n{numbered}",
                untrusted=[("rfp_requirements", "\n".join(r.text for r in reqs[:25]))], schema=SectionDraft, fixture=fixture, max_tokens=900)
            content, unsupported = check_claims(draft.content, cited)
            ex.checkpoint(key, {"evidence": len(hits), "unsupported": len(unsupported)})
            sections.append({
                "key": key, "title": title, "content": content, "unsupported_claims": unsupported,
                "citations": [{"ref": f"S{i}", "chunk_id": h["chunk_id"], "document": h["document_title"], "heading": h["heading"],
                               "excerpt": h["text"][:300]} for i, h in enumerate(hits, start=1) if f"[S{i}]" in content],
            })
        sections += _derived_sections(reqs, rfp)
        sections.sort(key=lambda s: [k for k, *_ in SECTIONS].index(s["key"]))
        # Supporting references aggregate all citations.
        refs = {}
        for s in sections:
            for c in s.get("citations", []):
                refs.setdefault(c["chunk_id"], c)
        for s in sections:
            if s["key"] == "supporting_references":
                s["content"] = "\n".join(f"- {c['document']}" + (f" — {c['heading']}" if c["heading"] else "") for c in refs.values())
                s["citations"] = list(refs.values())
        total_unsupported = sum(len(s["unsupported_claims"]) for s in sections)
        ex.finish({"sections": [s["key"] for s in sections], "unsupported_claims_removed": total_unsupported},
                  f"Drafted {len(sections)} sections from {len(refs)} evidence passages; removed {total_unsupported} unsupported claim(s).")
        return {"sections": sections, "generator": {"agent_run_id": ex.run.id, "provider": ex.run.provider, "model": ex.run.model,
                                                    "prompt_version": "proposal@1.5", "unsupported_claims_removed": total_unsupported}}
    except Exception as e:
        ex.fail(e)
        raise


def _derived_sections(reqs: list[Requirement], rfp: Rfp) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    risks = []
    for r in reqs:
        st = r.compliance.status if r.compliance else "unverified"
        counts[st] = counts.get(st, 0) + 1
        if st in {"non_compliant", "unverified"} and r.obligation == "mandatory":
            risks.append(f"- {r.code}: {r.text[:180]} — status {st.replace('_', ' ')}"
                         + (f". {r.compliance.missing_info}" if r.compliance and r.compliance.missing_info else ""))
    risk_text = ("The following mandatory requirements are not yet evidenced and must be resolved before submission:\n" + "\n".join(risks)) if risks \
        else "All mandatory requirements are supported by approved evidence."
    risk_text += "\n\nAssumptions: pricing, staffing and dates are subject to confirmation by the bid owner; this draft contains no commercial commitments."
    comp = "Summary of the compliance matrix: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(counts.items())) + \
           ". The full matrix with evidence references is attached as an annex."
    return [
        {"key": "risks_assumptions", "title": "Risks and Assumptions", "content": risk_text, "unsupported_claims": [], "citations": []},
        {"key": "compliance_response", "title": "Compliance Response", "content": comp, "unsupported_claims": [], "citations": []},
        {"key": "supporting_references", "title": "Supporting References", "content": "", "unsupported_claims": [], "citations": []},
    ]
