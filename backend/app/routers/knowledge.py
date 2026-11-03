from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, require
from app.models import KnowledgeChunk, KnowledgeDocument
from app.platform import audit, knowledge
from app.rfp import extraction
from app.routers.serialize import to_dict

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
KINDS = {"capability", "certification", "reference_project", "product", "standard_response", "policy", "previous_proposal"}


@router.get("")
def list_docs(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    rows = db.execute(select(KnowledgeDocument, func.count(KnowledgeChunk.id)).outerjoin(KnowledgeChunk)
                      .where(KnowledgeDocument.workspace_id == p.workspace_id).group_by(KnowledgeDocument.id).order_by(KnowledgeDocument.kind, KnowledgeDocument.title)).all()
    return [{**to_dict(d), "chunks": n} for d, n in rows]


@router.get("/search")
def search(q: str = Query(min_length=2), kinds: str | None = None, k: int = Query(6, le=20), p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    return knowledge.search(db, p.workspace_id, q, k=k, kinds=kinds.split(",") if kinds else None)


@router.get("/{doc_id}")
def get_doc(doc_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d or d.workspace_id != p.workspace_id:
        raise HTTPException(404, "Not found")
    return {**to_dict(d), "chunks": [to_dict(c, {"embedding"}) for c in d.chunks]}


@router.post("")
def upload(title: str = Form(...), kind: str = Form(...), valid_until: str | None = Form(None), approved: bool = Form(False),
           file: UploadFile = File(...), p: Principal = Depends(require("knowledge.write")), db: Session = Depends(get_db)):
    if kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {sorted(KINDS)}")
    data = file.file.read()
    t = extraction.sniff(data, file.filename or "")
    if t:
        body = "\n\n".join(extraction.extract(data, t).pages)
    else:
        try:
            body = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise HTTPException(415, "Upload PDF, DOCX, Markdown or plain text") from e
    # Only admins/approvers may publish approved knowledge directly; others submit for approval.
    is_approved = approved and p.role in {"admin", "approver"}
    doc = knowledge.ingest(db, p.workspace_id, title=title, kind=kind, body=body, source=f"upload:{file.filename}", approved=is_approved,
                           valid_until=datetime.fromisoformat(valid_until) if valid_until else None)
    audit.record(db, p.workspace_id, p.actor, "knowledge.ingested", "knowledge_document", doc.id, {"title": title, "kind": kind, "approved": is_approved})
    db.commit()
    return {**to_dict(doc), "chunks": len(doc.chunks)}


@router.post("/{doc_id}/approve")
def approve(doc_id: str, p: Principal = Depends(require("approval.decide")), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d or d.workspace_id != p.workspace_id:
        raise HTTPException(404, "Not found")
    d.approved = True
    audit.record(db, p.workspace_id, p.actor, "knowledge.approved", "knowledge_document", d.id, {})
    db.commit()
    return to_dict(d)
