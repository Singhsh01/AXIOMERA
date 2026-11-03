"""Proposal intelligence endpoints. Stage endpoints are called by n8n Workflows C and D."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

import pymupdf
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, session_factory, utcnow
from app.deps import Principal, require
from app.integrations import connectors
from app.models import AgentRun, ComplianceItem, ExportArtifact, Proposal, ProposalComment, Requirement, Rfp, RfpDocument, RfpSection, WorkflowRun
from app.platform import audit, notifications, workflows
from app.rfp import service as svc
from app.rfp.proposal import check_claims
from app.routers.common import WfCtx, map_errors, not_found, wf_ctx
from app.routers.serialize import to_dict

router = APIRouter(tags=["proposals"])


def _rfp(db: Session, rfp_id: str, p: Principal) -> Rfp:
    return not_found(db.get(Rfp, rfp_id), p.workspace_id, "RFP")


def _proposal(db: Session, pid: str, p: Principal) -> tuple[Proposal, Rfp]:
    prop = db.get(Proposal, pid)
    if not prop:
        raise HTTPException(404, "Proposal not found")
    return prop, _rfp(db, prop.rfp_id, p)


def _trigger_c(rfp_id: str, document_id: str, correlation_id: str) -> None:
    try:
        workflows.trigger("C", {"rfp_id": rfp_id, "document_id": document_id}, correlation_id=correlation_id)
    except workflows.WorkflowTriggerError:
        _inline_pipeline(rfp_id, "system:api-fallback")


def _inline_pipeline(rfp_id: str, actor: str) -> None:
    db = session_factory()()
    try:
        rfp = db.get(Rfp, rfp_id)
        run = workflows.get_or_create_run(db, rfp.workspace_id, workflow_key="C", n8n_execution_id=None, correlation_id=rfp.correlation_id,
                                          entity_type="rfp", entity_id=rfp.id, trigger_kind="api-fallback")
        steps = [("Validate & Store", svc.intake), ("Extract Text", svc.extract), ("Analyze Requirements", svc.extract_requirements),
                 ("Build Compliance Matrix", svc.build_matrix), ("Retrieve Evidence", svc.assess_evidence)]
        for node, fn in steps:
            fn(db, rfp, actor)
            workflows.record_step(db, run, node, "succeeded")
            db.commit()
        prop = svc.draft_proposal(db, rfp, actor)
        workflows.record_step(db, run, "Generate Draft", "succeeded", detail={"proposal_id": prop.id})
        svc.request_review(db, rfp, prop, actor)
        workflows.record_step(db, run, "Request Review", "succeeded")
        art = svc.export_proposal(db, rfp, prop, "docx", actor, final=False)
        workflows.record_step(db, run, "Export Draft", "succeeded", detail={"artifact": art.id})
        workflows.finish(db, run, "succeeded")
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        run = workflows.get_or_create_run(db, rfp.workspace_id, workflow_key="C", n8n_execution_id=None, correlation_id=rfp.correlation_id,
                                          entity_type="rfp", entity_id=rfp.id, trigger_kind="api-fallback")
        workflows.record_step(db, run, "pipeline", "failed", error=str(e))
        workflows.finish(db, run, "failed", str(e))
        db.commit()
    finally:
        db.close()


# ------------------------------------------------------------------ RFP CRUD
@router.post("/rfps")
@map_errors
def create_rfp(bg: BackgroundTasks, title: str = Form(..., min_length=3, max_length=300), issuer: str | None = Form(None), reference: str | None = Form(None),
               file: UploadFile = File(...), auto_process: bool = Form(True), p: Principal = Depends(require("rfp.write")), db: Session = Depends(get_db)):
    data = file.file.read()
    rfp = Rfp(workspace_id=p.workspace_id, title=title, issuer=issuer, reference=reference, owner_id=p.id if p.kind == "user" else None)
    db.add(rfp)
    db.flush()
    doc = svc.add_document(db, rfp, file.filename or "upload.pdf", data, p.actor)
    audit.record(db, p.workspace_id, p.actor, "rfp.created", "rfp", rfp.id, {"title": title}, correlation_id=rfp.correlation_id)
    db.commit()
    if auto_process:
        bg.add_task(_trigger_c, rfp.id, doc.id, rfp.correlation_id)
    return {"id": rfp.id, "document_id": doc.id, "correlation_id": rfp.correlation_id, "processing": "n8n" if auto_process else "manual"}


@router.post("/rfps/{rfp_id}/documents")
@map_errors
def upload_version(rfp_id: str, bg: BackgroundTasks, file: UploadFile = File(...), p: Principal = Depends(require("rfp.write")), db: Session = Depends(get_db)):
    rfp = _rfp(db, rfp_id, p)
    doc = svc.add_document(db, rfp, file.filename or "upload.pdf", file.file.read(), p.actor)
    rfp.status = "received"
    db.commit()
    bg.add_task(_trigger_c, rfp.id, doc.id, rfp.correlation_id)
    return {"document_id": doc.id, "version": doc.version}


@router.post("/rfps/{rfp_id}/process")
def process_inline(rfp_id: str, bg: BackgroundTasks, via: str = Query("n8n", pattern="^(n8n|inline)$"), p: Principal = Depends(require("rfp.write")), db: Session = Depends(get_db)):
    rfp = _rfp(db, rfp_id, p)
    doc = svc.latest_document(rfp)
    bg.add_task(_trigger_c if via == "n8n" else (lambda *a: _inline_pipeline(rfp.id, p.actor)), rfp.id, doc.id, rfp.correlation_id)
    return {"queued": True, "via": via}


def _rfp_summary(db: Session, r: Rfp) -> dict[str, Any]:
    reqs = db.scalars(select(Requirement).where(Requirement.rfp_id == r.id, Requirement.deleted.is_(False))).all()
    counts: dict[str, int] = {}
    for q in reqs:
        s = q.compliance.status if q.compliance else "unassessed"
        counts[s] = counts.get(s, 0) + 1
    latest = db.scalars(select(Proposal).where(Proposal.rfp_id == r.id).order_by(Proposal.version.desc())).first()
    return {**to_dict(r), "requirements": len(reqs), "compliance": counts, "documents": len(r.documents),
            "latest_proposal": {"id": latest.id, "version": latest.version, "status": latest.status} if latest else None,
            "hours_left": round((r.submission_due_at - utcnow()).total_seconds() / 3600, 1) if r.submission_due_at else None}


@router.get("/rfps")
def list_rfps(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return [_rfp_summary(db, r) for r in db.scalars(select(Rfp).where(Rfp.workspace_id == p.workspace_id).order_by(Rfp.created_at.desc()))]


@router.get("/rfps/deadlines/at-risk")
def deadlines(horizon_hours: int = Query(72, le=24 * 60), p: Principal = Depends(require("read")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    with workflows.StepTimer(db, p, wf.workflow, wf.node) as t:
        items = svc.at_risk(db, p.workspace_id, horizon_hours)
        swept = workflows.sweep_stale_runs(db, p.workspace_id)  # Workflow D runs hourly: a good place for housekeeping
        t.detail = {"at_risk": len(items), "abandoned_runs_closed": swept}
    db.commit()
    return {"items": items, "count": len(items), "checked_at": utcnow().isoformat()}


@router.get("/rfps/{rfp_id}")
def get_rfp(rfp_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    r = _rfp(db, rfp_id, p)
    d = _rfp_summary(db, r)
    d["documents"] = [{**to_dict(doc, {"storage_path"}), "sections": [to_dict(s) for s in db.scalars(select(RfpSection).where(RfpSection.document_id == doc.id).order_by(RfpSection.ordinal))]}
                      for doc in r.documents]
    d["proposals"] = [{"id": x.id, "version": x.version, "status": x.status, "created_at": x.created_at.isoformat()}
                      for x in db.scalars(select(Proposal).where(Proposal.rfp_id == r.id).order_by(Proposal.version.desc()))]
    d["workflow_runs"] = [{**to_dict(w), "steps": [to_dict(s) for s in w.steps]} for w in
                          db.scalars(select(WorkflowRun).where(WorkflowRun.correlation_id == r.correlation_id).order_by(WorkflowRun.started_at.desc()))]
    d["agent_runs"] = [to_dict(a) for a in db.scalars(select(AgentRun).where(AgentRun.entity_id == r.id).order_by(AgentRun.started_at))]
    return d


@router.get("/rfps/{rfp_id}/documents/{doc_id}/pages")
def pages(rfp_id: str, doc_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    r = _rfp(db, rfp_id, p)
    doc = next((d for d in r.documents if d.id == doc_id), None)
    if not doc:
        raise HTTPException(404, "Document not found")
    return [{"page": pg.page_no, "text": pg.text} for pg in doc.pages]


@router.get("/rfps/{rfp_id}/documents/{doc_id}/pages/{page_no}.png")
def page_image(rfp_id: str, doc_id: str, page_no: int, scale: float = Query(1.6, ge=0.5, le=3), p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    r = _rfp(db, rfp_id, p)
    doc = next((d for d in r.documents if d.id == doc_id), None)
    if not doc or doc.mime != "application/pdf":
        raise HTTPException(404, "Rendering is available for PDF documents")
    pdf = pymupdf.open(doc.storage_path)
    if not 1 <= page_no <= len(pdf):
        raise HTTPException(404, "Page out of range")
    pix = pdf[page_no - 1].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    return Response(pix.tobytes("png"), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/rfps/{rfp_id}/requirements/{req_id}/highlight")
def highlight(rfp_id: str, req_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    """Bounding boxes of a requirement on its PDF page, for the source viewer overlay."""
    r = _rfp(db, rfp_id, p)
    q = db.get(Requirement, req_id)
    if not q or q.rfp_id != r.id:
        raise HTTPException(404, "Requirement not found")
    doc = db.get(RfpDocument, q.document_id)
    if doc.mime != "application/pdf":
        return {"page": q.page, "rects": []}
    page = pymupdf.open(doc.storage_path)[q.page - 1]
    words = q.text.split()
    rects = page.search_for(" ".join(words[:8])) if len(words) >= 3 else []
    tail = page.search_for(" ".join(words[-6:])) if len(words) > 10 else []
    w, h = page.rect.width, page.rect.height
    return {"page": q.page, "rects": [{"x": rc.x0 / w, "y": rc.y0 / h, "w": rc.width / w, "h": rc.height / h} for rc in rects[:1] + tail[:1]]}


# ------------------------------------------------------------------ pipeline stage endpoints (n8n Workflow C)
def _stage(fn):
    def handler(rfp_id: str, p: Principal = Depends(require("rfp.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
        r = _rfp(db, rfp_id, p)
        with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="rfp", entity_id=r.id, correlation_id=r.correlation_id) as t:
            res = fn(db, r, p.actor)
            t.detail = {k: v for k, v in res.items() if k in {"pages", "requirements", "counts", "items", "method", "security_flags"}}
        db.commit()
        return {**res, "correlation_id": r.correlation_id}

    return map_errors(handler)


for _path, _fn in [("intake", svc.intake), ("extract", svc.extract), ("requirements/extract", svc.extract_requirements),
                   ("compliance/build", svc.build_matrix), ("compliance/assess", svc.assess_evidence)]:
    router.add_api_route(f"/rfps/{{rfp_id}}/{_path}", _stage(_fn), methods=["POST"], name=f"rfp_{_path.replace('/', '_')}")


@router.post("/rfps/{rfp_id}/proposals")
@map_errors
def draft(rfp_id: str, p: Principal = Depends(require("rfp.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    r = _rfp(db, rfp_id, p)
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="rfp", entity_id=r.id, correlation_id=r.correlation_id) as t:
        prop = svc.draft_proposal(db, r, p.actor)
        t.detail = {"proposal_id": prop.id, "version": prop.version, **prop.generator}
    db.commit()
    return {"proposal_id": prop.id, "version": prop.version, "generator": prop.generator, "correlation_id": r.correlation_id}


@router.post("/proposals/{pid}/request-review")
@map_errors
def request_review(pid: str, p: Principal = Depends(require("rfp.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    prop, r = _proposal(db, pid, p)
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="rfp", entity_id=r.id, correlation_id=r.correlation_id) as t:
        res = svc.request_review(db, r, prop, p.actor)
        t.detail = res
    db.commit()
    return res


@router.post("/proposals/{pid}/export")
@map_errors
def export(pid: str, fmt: str = Query("docx", alias="format", pattern="^(docx|pdf)$"), final: bool = False,
           p: Principal = Depends(require("rfp.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    prop, r = _proposal(db, pid, p)
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="rfp", entity_id=r.id, correlation_id=r.correlation_id) as t:
        art = svc.export_proposal(db, r, prop, fmt, p.actor, final)
        t.detail = {"artifact_id": art.id, "format": fmt, "final": final, "sha256": art.sha256}
    if t.run and wf.node == "Export Draft":
        workflows.finish(db, t.run, "succeeded")
    db.commit()
    return {"artifact_id": art.id, "format": fmt, "final": final, "sha256": art.sha256, "download": f"/api/v1/exports/{art.id}/download"}


@router.get("/exports/{art_id}/download")
def download(art_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    art = db.get(ExportArtifact, art_id)
    if not art:
        raise HTTPException(404, "Export not found")
    _proposal(db, art.proposal_id, p)
    media = "application/pdf" if art.format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(art.path, media_type=media, filename=Path(art.path).name)


@router.get("/exports/{art_id}/manifest")
def manifest(art_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    art = db.get(ExportArtifact, art_id)
    if not art:
        raise HTTPException(404, "Export not found")
    _proposal(db, art.proposal_id, p)
    return art.evidence_manifest


class EscalateIn(BaseModel):
    reason: str = "Submission deadline within 24 hours"


@router.post("/rfps/{rfp_id}/escalate")
@map_errors
def escalate(rfp_id: str, body: EscalateIn, p: Principal = Depends(require("rfp.write")), wf: WfCtx = Depends(wf_ctx), db: Session = Depends(get_db)):
    r = _rfp(db, rfp_id, p)
    with workflows.StepTimer(db, p, wf.workflow, wf.node, entity_type="rfp", entity_id=r.id, correlation_id=r.correlation_id) as t:
        if r.last_deadline_alert_at and (utcnow() - r.last_deadline_alert_at).total_seconds() < 6 * 3600:
            t.detail = {"suppressed": True}
            res = {"rfp_id": r.id, "suppressed": True, "reason": "escalated within the last 6 hours"}
        else:
            slack = connectors.call(db, p.workspace_id, "slack", "post_message",
                                    {"channel": "#bids", "text": f":alarm_clock: RFP '{r.title}' due {r.submission_due_at:%d %b %H:%M} UTC — {body.reason}"},
                                    idempotency_key=f"rfp-escalate-{r.id}-{utcnow():%Y%m%d%H}")
            notifications.notify(db, p.workspace_id, f"Escalation: '{r.title[:60]}' deadline", body.reason, severity="critical", link=f"/app/rfps/{r.id}")
            r.last_deadline_alert_at = utcnow()
            audit.record(db, p.workspace_id, p.actor, "rfp.deadline_escalated", "rfp", r.id, {"reason": body.reason, "slack": slack.get("external_id")},
                         correlation_id=r.correlation_id)
            t.detail = {"slack": slack.get("external_id")}
            res = {"rfp_id": r.id, "suppressed": False, "slack": slack}
    db.commit()
    return res


# ------------------------------------------------------------------ requirements & matrix (human-in-the-loop)
def _req_view(q: Requirement) -> dict[str, Any]:
    d = to_dict(q)
    d["compliance"] = to_dict(q.compliance) if q.compliance else None
    return d


@router.get("/rfps/{rfp_id}/requirements")
def list_requirements(rfp_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    r = _rfp(db, rfp_id, p)
    return [_req_view(q) for q in db.scalars(select(Requirement).where(Requirement.rfp_id == r.id, Requirement.deleted.is_(False)).order_by(Requirement.code))]


class ReqPatch(BaseModel):
    text: str | None = Field(default=None, min_length=10, max_length=2000)
    obligation: str | None = Field(default=None, pattern="^(mandatory|optional|informational)$")
    category: str | None = Field(default=None, pattern="^(technical|commercial|submission|evaluation|deadline|attachment|contractual|general)$")
    deleted: bool | None = None


@router.patch("/requirements/{req_id}")
def patch_requirement(req_id: str, body: ReqPatch, p: Principal = Depends(require("rfp.edit")), db: Session = Depends(get_db)):
    q = db.get(Requirement, req_id)
    if not q:
        raise HTTPException(404, "Requirement not found")
    r = _rfp(db, q.rfp_id, p)
    changes = body.model_dump(exclude_none=True)
    before = {k: getattr(q, k) for k in changes}
    for k, v in changes.items():
        setattr(q, k, v)
    q.human_verified, q.corrected_by, q.extraction_method = True, p.id, q.extraction_method if "human" in q.extraction_method else f"{q.extraction_method}+human"
    audit.record(db, r.workspace_id, p.actor, "requirement.corrected", "requirement", q.id, {"before": before, "after": changes}, correlation_id=r.correlation_id)
    db.commit()
    return _req_view(q)


class CompliancePatch(BaseModel):
    status: str = Field(pattern="^(compliant|partially_compliant|non_compliant|unverified)$")
    rationale: str = Field(min_length=5, max_length=2000)
    missing_info: str | None = None


@router.patch("/requirements/{req_id}/compliance")
def patch_compliance(req_id: str, body: CompliancePatch, p: Principal = Depends(require("rfp.review")), db: Session = Depends(get_db)):
    q = db.get(Requirement, req_id)
    if not q:
        raise HTTPException(404, "Requirement not found")
    r = _rfp(db, q.rfp_id, p)
    item = q.compliance or ComplianceItem(requirement_id=q.id)
    q.compliance = item
    if body.status == "compliant" and not item.evidence:
        raise HTTPException(422, "A requirement cannot be marked compliant without supporting evidence")
    before = {"status": item.status, "rationale": item.rationale}
    item.status, item.rationale, item.missing_info = body.status, body.rationale, body.missing_info
    item.review_status, item.reviewer_id, item.assessed_by = "changed", p.id, "human"
    audit.record(db, r.workspace_id, p.actor, "compliance.reviewed", "requirement", q.id, {"before": before, "after": body.model_dump()}, correlation_id=r.correlation_id)
    db.commit()
    return _req_view(q)


@router.post("/requirements/{req_id}/compliance/accept")
def accept_compliance(req_id: str, p: Principal = Depends(require("rfp.review")), db: Session = Depends(get_db)):
    q = db.get(Requirement, req_id)
    if not q or not q.compliance:
        raise HTTPException(404, "Not assessed")
    r = _rfp(db, q.rfp_id, p)
    q.compliance.review_status, q.compliance.reviewer_id = "accepted", p.id
    audit.record(db, r.workspace_id, p.actor, "compliance.accepted", "requirement", q.id, {"status": q.compliance.status}, correlation_id=r.correlation_id)
    db.commit()
    return _req_view(q)


# ------------------------------------------------------------------ proposals: editing, review, comments, diff
@router.get("/proposals/{pid}")
def get_proposal(pid: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    prop, r = _proposal(db, pid, p)
    d = to_dict(prop)
    d["comments"] = [to_dict(c) for c in prop.comments]
    d["exports"] = [to_dict(a, {"path", "evidence_manifest"}) for a in db.scalars(select(ExportArtifact).where(ExportArtifact.proposal_id == prop.id).order_by(ExportArtifact.created_at.desc()))]
    d["rfp"] = {"id": r.id, "title": r.title}
    return d


class SectionEdit(BaseModel):
    content: str = Field(max_length=20_000)


@router.patch("/proposals/{pid}/sections/{key}")
def edit_section(pid: str, key: str, body: SectionEdit, p: Principal = Depends(require("rfp.edit")), db: Session = Depends(get_db)):
    prop, r = _proposal(db, pid, p)
    if prop.status in {"approved", "exported"}:
        raise HTTPException(409, "Approved proposals are immutable; create a new version")
    sections = [dict(s) for s in prop.sections]
    sec = next((s for s in sections if s["key"] == key), None)
    if not sec:
        raise HTTPException(404, "Section not found")
    from app.models import KnowledgeChunk

    ids = [c["chunk_id"] for c in sec.get("citations", [])]
    texts = {c.id: c.text for c in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids)))} if ids else {}
    cited = {c["ref"]: texts.get(c["chunk_id"], "") for c in sec.get("citations", []) if "ref" in c}
    _, unsupported = check_claims(body.content, cited)
    sec["content"], sec["edited_by"], sec["edited_at"] = body.content, p.id, utcnow().isoformat()
    sec["unsupported_claims"] = unsupported  # human edits are flagged, not removed
    prop.sections = sections
    if prop.status == "in_review":
        prop.status = "draft"
    audit.record(db, r.workspace_id, p.actor, "proposal.section_edited", "proposal", prop.id, {"section": key, "unsupported_flags": len(unsupported)},
                 correlation_id=r.correlation_id)
    db.commit()
    return {"section": sec, "status": prop.status}


class CommentIn(BaseModel):
    section_key: str
    body: str = Field(min_length=1, max_length=4000)


@router.post("/proposals/{pid}/comments")
def add_comment(pid: str, body: CommentIn, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    prop, r = _proposal(db, pid, p)
    if p.kind != "user":
        raise HTTPException(403, "Users only")
    c = ProposalComment(proposal_id=prop.id, section_key=body.section_key, author_id=p.id, author_name=p.name, body=body.body)
    db.add(c)
    db.commit()
    return to_dict(c)


class ReviewIn(BaseModel):
    approve: bool
    note: str | None = None


@router.post("/proposals/{pid}/review")
@map_errors
def review(pid: str, body: ReviewIn, p: Principal = Depends(require("rfp.review")), db: Session = Depends(get_db)):
    if p.kind != "user":
        raise HTTPException(403, "Human reviewer required")
    prop, r = _proposal(db, pid, p)
    svc.review(db, r, prop, user_id=p.id, approve=body.approve, note=body.note)
    db.commit()
    return {"id": prop.id, "status": prop.status}


@router.post("/rfps/{rfp_id}/proposals/{pid}/new-version")
def new_version(rfp_id: str, pid: str, p: Principal = Depends(require("rfp.edit")), db: Session = Depends(get_db)):
    prop, r = _proposal(db, pid, p)
    latest = db.scalars(select(Proposal).where(Proposal.rfp_id == r.id).order_by(Proposal.version.desc())).first()
    np = Proposal(rfp_id=r.id, version=latest.version + 1, sections=prop.sections, generator={**prop.generator, "derived_from": prop.id}, created_by=p.actor)
    db.add(np)
    audit.record(db, r.workspace_id, p.actor, "proposal.versioned", "proposal", np.id or "new", {"from": prop.version}, correlation_id=r.correlation_id)
    db.commit()
    return {"id": np.id, "version": np.version}


@router.get("/proposals/{pid}/diff")
def diff(pid: str, against: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    a, r = _proposal(db, pid, p)
    b, _ = _proposal(db, against, p)
    out = []
    for sa in a.sections:
        sb = next((s for s in b.sections if s["key"] == sa["key"]), {"content": ""})
        ops = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sb["content"].split(" "), sa["content"].split(" ")).get_opcodes():
            ops.append({"op": tag, "old": " ".join(sb["content"].split(" ")[i1:i2]), "new": " ".join(sa["content"].split(" ")[j1:j2])})
        out.append({"key": sa["key"], "title": sa["title"], "changed": sa["content"] != sb["content"], "ops": ops})
    return {"from": b.version, "to": a.version, "sections": out}
