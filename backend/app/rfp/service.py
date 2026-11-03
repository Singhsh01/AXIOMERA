"""Proposal intelligence service (authoritative state for RFPs, requirements, matrix, proposals)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.runtime import AgentExecution, Budget
from app.config import get_settings
from app.core import guard
from app.core.security import sha256_hex
from app.db import utcnow
from app.models import (
    ComplianceItem,
    ExportArtifact,
    KnowledgeChunk,
    Proposal,
    Requirement,
    Rfp,
    RfpDocument,
    RfpPage,
    RfpSection,
)
from app.platform import audit, notifications
from app.rfp import compliance, export, extraction
from app.rfp import proposal as proposal_gen
from app.rfp import requirements as req

PROCEDURAL = {"submission", "deadline", "evaluation", "attachment"}
COMPANY = "Helix Ridge Software GmbH"  # fictional demo company used by the seed knowledge base


class RfpError(Exception):
    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


def storage_path(workspace_id: str, sha: str, ext: str) -> Path:
    d = get_settings().storage_dir / workspace_id / "rfp"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sha}.{ext}"


def add_document(db: Session, rfp: Rfp, filename: str, data: bytes, actor: str) -> RfpDocument:
    s = get_settings()
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise RfpError(f"File exceeds {s.max_upload_mb} MB", 413)
    kind = extraction.sniff(data, filename)
    if kind is None:
        raise RfpError("Only PDF and DOCX files are accepted (content sniffing failed)", 415)
    sha = sha256_hex(data)
    path = storage_path(rfp.workspace_id, sha, kind)
    if not path.exists():
        path.write_bytes(data)
    version = (db.scalar(select(func.max(RfpDocument.version)).where(RfpDocument.rfp_id == rfp.id)) or 0) + 1
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name)[:200]
    mime = next(m for m, k in extraction.ALLOWED_MIME.items() if k == kind)
    doc = RfpDocument(rfp_id=rfp.id, filename=safe_name, mime=mime, sha256=sha, size_bytes=len(data), storage_path=str(path), version=version)
    db.add(doc)
    rfp.documents.append(doc)
    db.flush()
    audit.record(db, rfp.workspace_id, actor, "rfp.document_uploaded", "rfp", rfp.id, {"document_id": doc.id, "sha256": sha, "version": version, "filename": safe_name},
                 correlation_id=rfp.correlation_id)
    return doc


def latest_document(rfp: Rfp) -> RfpDocument:
    if not rfp.documents:
        raise RfpError("RFP has no documents", 409)
    return sorted(rfp.documents, key=lambda d: d.version)[-1]


def intake(db: Session, rfp: Rfp, actor: str) -> dict[str, Any]:
    doc = latest_document(rfp)
    data = Path(doc.storage_path).read_bytes()
    checks = {"sha256_matches": sha256_hex(data) == doc.sha256, "type": extraction.sniff(data, doc.filename),
              "size_ok": doc.size_bytes <= get_settings().max_upload_mb * 1024 * 1024}
    if b"/JavaScript" in data[:2_000_000] or b"/Launch" in data[:2_000_000]:
        checks["active_content"] = True
        rfp.security_flags = [*rfp.security_flags, {"type": "active_content", "detail": "PDF contains JavaScript/Launch actions; content is never executed"}]
    ok = checks["sha256_matches"] and checks["type"] is not None and checks["size_ok"]
    audit.record(db, rfp.workspace_id, actor, "rfp.intake_validated", "rfp", rfp.id, checks, correlation_id=rfp.correlation_id)
    if not ok:
        raise RfpError(f"Intake validation failed: {checks}", 422)
    return {"rfp_id": rfp.id, "document_id": doc.id, "checks": checks, "stored": doc.storage_path.split("/")[-1]}


def extract(db: Session, rfp: Rfp, actor: str) -> dict[str, Any]:
    doc = latest_document(rfp)
    data = Path(doc.storage_path).read_bytes()
    rfp.status = "extracting"
    ex = extraction.extract(data, "pdf" if doc.mime == "application/pdf" else "docx")
    for p in list(doc.pages):
        db.delete(p)
    db.query(RfpSection).filter(RfpSection.document_id == doc.id).delete()
    db.flush()
    db.refresh(doc, ["pages"])
    for i, t in enumerate(ex.pages, start=1):
        doc.pages.append(RfpPage(document_id=doc.id, page_no=i, text=t))
    for i, s in enumerate(ex.sections):
        db.add(RfpSection(document_id=doc.id, number=str(s["number"]), title=s["title"][:300], page_start=s["page"], ordinal=i))
    doc.page_count, doc.extraction_method, doc.extraction_warnings, doc.doc_metadata = len(ex.pages), ex.method, ex.warnings, ex.metadata
    flags = [f | {"page": i + 1} for i, t in enumerate(ex.pages) for f in guard.scan(t, f"rfp-page:{i + 1}").flags]
    rfp.security_flags = [f for f in rfp.security_flags if f.get("type") == "active_content"] + flags
    deadlines = req.extract_deadlines(ex.pages)
    rfp.deadlines = deadlines
    sub = next((d for d in deadlines if d["kind"] == "submission"), None)
    if sub:
        rfp.submission_due_at = datetime.fromisoformat(sub["at"])
    if not rfp.issuer and ex.metadata.get("author"):
        rfp.issuer = ex.metadata["author"][:200]
    rfp.status = "extracted"
    db.flush()
    audit.record(db, rfp.workspace_id, actor, "rfp.extracted", "rfp", rfp.id,
                 {"pages": len(ex.pages), "method": ex.method, "sections": len(ex.sections), "deadlines": len(deadlines), "security_flags": len(flags)},
                 correlation_id=rfp.correlation_id)
    if flags:
        notifications.notify(db, rfp.workspace_id, f"RFP '{rfp.title[:60]}' contains suspicious instructions",
                             f"{len(flags)} passage(s) attempt to instruct automated reviewers; they were excluded from requirements.",
                             severity="warning", link=f"/app/rfps/{rfp.id}")
    return {"rfp_id": rfp.id, "pages": len(ex.pages), "method": ex.method, "warnings": ex.warnings, "sections": len(ex.sections),
            "deadlines": deadlines, "security_flags": len(flags)}


def extract_requirements(db: Session, rfp: Rfp, actor: str) -> dict[str, Any]:
    doc = latest_document(rfp)
    pages = [p.text for p in doc.pages]
    if not pages:
        raise RfpError("Extract text first", 409)
    sections = [{"number": s.number, "title": s.title, "page": s.page_start} for s in
                db.scalars(select(RfpSection).where(RfpSection.document_id == doc.id).order_by(RfpSection.ordinal))]
    ex = AgentExecution(db, rfp.workspace_id, "requirements-agent", f"Extract requirements: {rfp.title[:80]}", set(), "requirements@1.6",
                        Budget(max_steps=60, max_tool_calls=0, max_tokens=120_000, max_cost_usd=1.0, max_seconds=300), rfp.correlation_id, "rfp", rfp.id)
    try:
        candidates, flags = req.rule_extract(pages, sections)
        ex.flag(flags)
        rejected = 0
        if ex.provider.name != "fixture":
            by_page = {}
            for i, page in enumerate(pages, start=1):
                out: req.LLMRequirements = ex.llm(
                    instructions="List every requirement sentence on this RFP page as an exact verbatim quote with obligation "
                                 "(mandatory/optional/informational) and category (technical, commercial, submission, evaluation, deadline, attachment, contractual).",
                    trusted_context=f"Page {i} of {len(pages)}.", untrusted=[(f"rfp_page_{i}", page)], schema=req.LLMRequirements,
                    fixture=lambda: req.LLMRequirements(requirements=[], reasoning_summary="fixture"), max_tokens=2000)
                by_page[i] = out.requirements
                ex.checkpoint(f"page-{i}", {"found": len(out.requirements)})
            candidates, rejected = req.merge_llm(pages, candidates, by_page, sections)
        # Preserve human corrections across re-extraction: only replace machine-made rows.
        existing = db.scalars(select(Requirement).where(Requirement.rfp_id == rfp.id)).all()
        for r in existing:
            if not r.human_verified:
                db.delete(r)
        db.flush()
        kept_human = [r for r in existing if r.human_verified]
        n = len(kept_human)
        for c in candidates:
            if any(h.page == c.page and not (c.end <= h.char_start or c.start >= h.char_end) for h in kept_human):
                continue
            n += 1
            db.add(Requirement(rfp_id=rfp.id, document_id=doc.id, code=f"REQ-{n:03d}", text=c.text, obligation=c.obligation, category=c.category,
                               page=c.page, section=c.section, char_start=c.start, char_end=c.end, confidence=c.confidence, extraction_method=c.method))
        rfp.status = "analyzed"
        db.flush()
        by_cat: dict[str, int] = {}
        for c in candidates:
            by_cat[c.category] = by_cat.get(c.category, 0) + 1
        ex.finish({"requirements": n, "by_category": by_cat, "excluded_injections": len(flags), "llm_quotes_rejected": rejected},
                  f"Extracted {n} requirements; excluded {len(flags)} manipulative passage(s); rejected {rejected} unlocatable model quote(s).")
        audit.record(db, rfp.workspace_id, actor, "rfp.requirements_extracted", "rfp", rfp.id, {"count": n, "by_category": by_cat},
                     correlation_id=rfp.correlation_id)
        return {"rfp_id": rfp.id, "requirements": n, "by_category": by_cat, "excluded_injections": len(flags)}
    except Exception as e:
        ex.fail(e)
        raise


def build_matrix(db: Session, rfp: Rfp, actor: str) -> dict[str, Any]:
    reqs = db.scalars(select(Requirement).where(Requirement.rfp_id == rfp.id, Requirement.deleted.is_(False))).all()
    created = 0
    for r in reqs:
        if r.compliance is None:
            r.compliance = ComplianceItem(requirement_id=r.id, status="unverified", rationale="Not yet assessed.")
            created += 1
    rfp.status = "matrix_ready"
    db.flush()
    audit.record(db, rfp.workspace_id, actor, "rfp.matrix_built", "rfp", rfp.id, {"items": len(reqs), "created": created}, correlation_id=rfp.correlation_id)
    return {"rfp_id": rfp.id, "items": len(reqs), "created": created}


def assess_evidence(db: Session, rfp: Rfp, actor: str) -> dict[str, Any]:
    reqs = db.scalars(select(Requirement).where(Requirement.rfp_id == rfp.id, Requirement.deleted.is_(False)).order_by(Requirement.code)).all()
    ex = AgentExecution(db, rfp.workspace_id, "compliance-agent", f"Assess compliance: {rfp.title[:80]}", {"knowledge.search"}, "compliance@1.4",
                        Budget(max_steps=len(reqs) + 2, max_tool_calls=0, max_seconds=300), rfp.correlation_id, "rfp", rfp.id)
    try:
        counts: dict[str, int] = {}
        for r in reqs:
            if r.compliance is None:
                r.compliance = ComplianceItem(requirement_id=r.id)
            item = r.compliance
            if item.review_status == "changed":
                counts[item.status] = counts.get(item.status, 0) + 1
                continue  # never overwrite a human decision
            if r.category in PROCEDURAL:
                item.status, item.evidence, item.assessed_by = "unverified", [], "engine"
                item.rationale = "Procedural bid requirement — verified by the bid manager in the submission checklist, not by product evidence."
                item.missing_info = "Confirm in the submission checklist."
                counts["unverified"] = counts.get("unverified", 0) + 1
                ex.checkpoint(r.code, {"status": "procedural"})
                continue
            a = compliance.assess(db, rfp.workspace_id, r.text)
            item.status, item.rationale, item.evidence, item.missing_info, item.assessed_by = a["status"], a["rationale"], a["evidence"], a["missing_info"], "engine"
            for e in a["evidence"][:2]:
                ex.add_context({"type": "knowledge_chunk", "id": e["chunk_id"], "label": e["document"], "requirement": r.code})
            counts[a["status"]] = counts.get(a["status"], 0) + 1
            ex.checkpoint(r.code, {"status": a["status"]})
        ex.finish({"counts": counts}, f"Assessed {len(reqs)} requirements: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        audit.record(db, rfp.workspace_id, actor, "rfp.compliance_assessed", "rfp", rfp.id, {"counts": counts}, correlation_id=rfp.correlation_id)
        return {"rfp_id": rfp.id, "counts": counts}
    except Exception as e:
        ex.fail(e)
        raise


def draft_proposal(db: Session, rfp: Rfp, actor: str, provider=None) -> Proposal:
    reqs = db.scalars(select(Requirement).where(Requirement.rfp_id == rfp.id, Requirement.deleted.is_(False)).order_by(Requirement.code)).all()
    result = proposal_gen.generate(db, rfp, list(reqs), COMPANY, rfp.correlation_id, provider=provider)
    version = (db.scalar(select(func.max(Proposal.version)).where(Proposal.rfp_id == rfp.id)) or 0) + 1
    p = Proposal(rfp_id=rfp.id, version=version, sections=result["sections"], generator=result["generator"], created_by=actor)
    db.add(p)
    rfp.status = "drafted"
    db.flush()
    audit.record(db, rfp.workspace_id, actor, "proposal.drafted", "proposal", p.id,
                 {"version": version, "unsupported_removed": result["generator"]["unsupported_claims_removed"]}, correlation_id=rfp.correlation_id)
    return p


def request_review(db: Session, rfp: Rfp, p: Proposal, actor: str) -> dict[str, Any]:
    if p.status not in {"draft", "changes_requested"}:
        raise RfpError(f"Proposal is {p.status}", 409)
    p.status = "in_review"
    rfp.status = "in_review"
    notifications.notify(db, rfp.workspace_id, f"Proposal v{p.version} ready for review", rfp.title, severity="info", link=f"/app/rfps/{rfp.id}?tab=proposal")
    audit.record(db, rfp.workspace_id, actor, "proposal.review_requested", "proposal", p.id, {"version": p.version}, correlation_id=rfp.correlation_id)
    return {"proposal_id": p.id, "status": p.status, "version": p.version}


def review(db: Session, rfp: Rfp, p: Proposal, *, user_id: str, approve: bool, note: str | None) -> Proposal:
    if p.status != "in_review":
        raise RfpError("Proposal is not in review", 409)
    if p.created_by == f"user:{user_id}":
        raise RfpError("Separation of duties: the author cannot approve their own proposal", 403)
    blocking = [s["key"] for s in p.sections if s.get("unsupported_claims")]
    p.status = "approved" if approve else "changes_requested"
    p.reviewed_by, p.reviewed_at, p.review_note = user_id, utcnow(), note
    rfp.status = "approved" if approve else "drafted"
    audit.record(db, rfp.workspace_id, f"user:{user_id}", f"proposal.{p.status}", "proposal", p.id,
                 {"version": p.version, "note": note, "sections_with_removed_claims": blocking}, correlation_id=rfp.correlation_id)
    return p


def matrix_rows(db: Session, rfp: Rfp) -> list[dict[str, Any]]:
    reqs = db.scalars(select(Requirement).where(Requirement.rfp_id == rfp.id, Requirement.deleted.is_(False)).order_by(Requirement.code)).all()
    return [{"code": r.code, "text": r.text, "page": r.page, "category": r.category, "obligation": r.obligation,
             "status": r.compliance.status if r.compliance else "unverified", "evidence": r.compliance.evidence if r.compliance else []} for r in reqs]


def export_proposal(db: Session, rfp: Rfp, p: Proposal, fmt: str, actor: str, final: bool) -> ExportArtifact:
    if final and p.status not in {"approved", "exported"}:
        raise RfpError("Final export requires an approved review", 403)
    chunk_ids = {c["chunk_id"] for s in p.sections for c in s.get("citations", [])}
    texts = {c.id: c.text for c in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))} if chunk_ids else {}
    pdict = {"id": p.id, "version": p.version, "status": p.status, "sections": p.sections, "generator": p.generator}
    man = export.manifest(pdict, texts)
    man_sha = sha256_hex(export.manifest_bytes(man))
    ctx = {"proposal": pdict, "rfp": {"title": rfp.title, "issuer": rfp.issuer, "reference": rfp.reference,
                                      "due": rfp.submission_due_at.strftime("%d %B %Y, %H:%M UTC") if rfp.submission_due_at else None},
           "company": COMPANY, "final": final, "matrix": matrix_rows(db, rfp), "manifest_sha": man_sha}
    data = export.to_docx(ctx) if fmt == "docx" else export.to_pdf(ctx)
    sha = sha256_hex(data)
    d = get_settings().storage_dir / rfp.workspace_id / "exports"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"proposal-{p.id[:8]}-v{p.version}-{'final' if final else 'draft'}.{fmt}"
    path.write_bytes(data)
    (d / f"{path.stem}.manifest.json").write_bytes(export.manifest_bytes(man))
    art = ExportArtifact(proposal_id=p.id, format=fmt, path=str(path), sha256=sha, final=final, evidence_manifest={**man, "sha256": man_sha})
    db.add(art)
    if final:
        p.status, rfp.status = "exported", "exported"
    db.flush()
    audit.record(db, rfp.workspace_id, actor, "proposal.exported", "proposal", p.id, {"format": fmt, "final": final, "sha256": sha, "manifest_sha256": man_sha},
                 correlation_id=rfp.correlation_id)
    return art


def at_risk(db: Session, workspace_id: str, horizon_hours: int = 72) -> list[dict[str, Any]]:
    now = utcnow()
    rows = db.scalars(select(Rfp).where(Rfp.workspace_id == workspace_id, Rfp.status.notin_(["exported", "archived"]),
                                        Rfp.submission_due_at.is_not(None), Rfp.submission_due_at <= now + timedelta(hours=horizon_hours))).all()
    out = []
    for r in rows:
        hours = (r.submission_due_at - now).total_seconds() / 3600
        reqs = db.scalars(select(Requirement).where(Requirement.rfp_id == r.id, Requirement.deleted.is_(False))).all()
        open_mand = sum(1 for q in reqs if q.obligation == "mandatory" and (q.compliance is None or q.compliance.status in {"unverified", "non_compliant"}))
        severity = "critical" if hours < 24 else "warning"
        out.append({"rfp_id": r.id, "title": r.title, "status": r.status, "due": r.submission_due_at.isoformat(), "hours_left": round(hours, 1),
                    "open_mandatory": open_mand, "severity": severity, "owner_id": r.owner_id, "escalate": hours < 24 and r.status not in {"approved"}})
    return sorted(out, key=lambda x: x["hours_left"])
