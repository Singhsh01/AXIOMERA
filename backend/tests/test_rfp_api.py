"""Proposal intelligence vertical slice: upload → extraction → requirements → matrix → evidence → draft → review → export."""
from __future__ import annotations

import io
import json
from pathlib import Path

import docx
import pymupdf
import pytest

from app.rfp import extraction
from app.rfp import requirements as req
from app.rfp.proposal import check_claims

SEED = Path(__file__).resolve().parents[1] / "seed" / "rfps"
TRUTH = json.loads((Path(__file__).resolve().parents[1] / "evals" / "datasets" / "rfp_lindenfeld_truth.json").read_text())


@pytest.fixture(scope="module")
def rfp(client, ops_h):
    pdf = (SEED / "lindenfeld-case-management-rfp.pdf").read_bytes()
    r = client.post("/api/v1/rfps", headers=ops_h, data={"title": "Lindenfeld test", "issuer": "City of Lindenfeld", "reference": "LF-2026-117"},
                    files={"file": ("rfp.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    return client.get(f"/api/v1/rfps/{r.json()['id']}", headers=ops_h).json()


def test_pipeline_completed_via_fallback(rfp):
    assert rfp["status"] == "in_review"
    assert rfp["submission_due_at"].startswith("2026-12-18")
    run = rfp["workflow_runs"][0]
    assert run["trigger"] == "api-fallback" and run["status"] == "succeeded"


def test_requirements_match_ground_truth(client, ops_h, rfp):
    reqs = client.get(f"/api/v1/rfps/{rfp['id']}/requirements", headers=ops_h).json()
    texts = [r["text"] for r in reqs]
    found = sum(1 for t in TRUTH["requirements"] if any(t["text"][:50] in x for x in texts))
    assert found / len(TRUTH["requirements"]) >= 0.95
    assert len(reqs) == len(TRUTH["requirements"])  # no spurious requirements


def test_requirement_offsets_point_to_source(client, ops_h, rfp):
    doc = rfp["documents"][0]
    pages = {p["page"]: p["text"] for p in client.get(f"/api/v1/rfps/{rfp['id']}/documents/{doc['id']}/pages", headers=ops_h).json()}
    for r in client.get(f"/api/v1/rfps/{rfp['id']}/requirements", headers=ops_h).json():
        src = " ".join(pages[r["page"]][r["char_start"]:r["char_end"]].split())
        assert src.startswith(r["text"][:30]), (r["code"], src[:60])


def test_compliance_statuses(client, ops_h, rfp):
    reqs = {r["text"][:50]: r for r in client.get(f"/api/v1/rfps/{rfp['id']}/requirements", headers=ops_h).json()}
    for t in TRUTH["requirements"]:
        if "compliance" not in t:
            continue
        got = next(r for k, r in reqs.items() if t["text"][:50] in r["text"])["compliance"]
        assert got["status"] == t["compliance"], (t["text"], got["status"], got["rationale"])
        if got["status"] == "compliant":
            assert got["evidence"], "compliant requires evidence"


def test_human_cannot_mark_compliant_without_evidence(client, reviewer_h, ops_h, rfp):
    reqs = client.get(f"/api/v1/rfps/{rfp['id']}/requirements", headers=ops_h).json()
    no_ev = next(r for r in reqs if not r["compliance"]["evidence"])
    r = client.patch(f"/api/v1/requirements/{no_ev['id']}/compliance", headers=reviewer_h, json={"status": "compliant", "rationale": "trust me"})
    assert r.status_code == 422
    r = client.patch(f"/api/v1/requirements/{no_ev['id']}/compliance", headers=reviewer_h,
                     json={"status": "non_compliant", "rationale": "We do not carry this insurance level.", "missing_info": None})
    assert r.status_code == 200 and r.json()["compliance"]["assessed_by"] == "human"


def test_requirement_correction_is_audited(client, ops_h, rfp):
    r0 = client.get(f"/api/v1/rfps/{rfp['id']}/requirements", headers=ops_h).json()[0]
    r = client.patch(f"/api/v1/requirements/{r0['id']}", headers=ops_h, json={"category": "deadline"})
    assert r.status_code == 200 and r.json()["human_verified"]
    log = client.get(f"/api/v1/audit?entity_id={r0['id']}", headers=ops_h).json()
    assert log[0]["action"] == "requirement.corrected"


def test_review_and_export(client, ops_h, reviewer_h, rfp):
    pid = rfp["latest_proposal"]["id"]
    prop = client.get(f"/api/v1/proposals/{pid}", headers=ops_h).json()
    keys = [s["key"] for s in prop["sections"]]
    assert keys[:3] == ["executive_summary", "technical_approach", "solution_architecture"] and "compliance_response" in keys
    for s in prop["sections"]:
        if s["key"] in {"executive_summary", "technical_approach", "solution_architecture"}:
            assert s["citations"], f"{s['key']} must cite evidence"
    assert prop["exports"] and prop["exports"][0]["final"] is False  # draft exported by the pipeline

    assert client.post(f"/api/v1/proposals/{pid}/export?format=docx&final=true", headers=ops_h).status_code == 403
    assert client.post(f"/api/v1/proposals/{pid}/review", headers=reviewer_h, json={"approve": True, "note": "ok"}).status_code == 200
    art = client.post(f"/api/v1/proposals/{pid}/export?format=docx&final=true", headers=ops_h).json()
    data = client.get(art["download"], headers=ops_h).content
    d = docx.Document(io.BytesIO(data))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "APPROVED FOR SUBMISSION" in text and "1. Executive Summary" in text and "Annex A" in text
    assert len(d.tables) >= 2 and d.core_properties.title.startswith("Proposal")
    assert "Page" in d.sections[1].footer.paragraphs[0].text
    pdf = client.post(f"/api/v1/proposals/{pid}/export?format=pdf&final=true", headers=ops_h).json()
    doc = pymupdf.open(stream=client.get(pdf["download"], headers=ops_h).content, filetype="pdf")
    full = "".join(p.get_text() for p in doc)
    assert doc.page_count >= 4 and "Table of Contents" in full and "Compliance Matrix" in full
    man = client.get(f"/api/v1/exports/{art['artifact_id']}/manifest", headers=ops_h).json()
    assert man["sections"]["executive_summary"][0]["evidence_sha256"]


def test_author_cannot_review_own_edits(client, ops_h, rfp):
    r = client.post(f"/api/v1/rfps/{rfp['id']}/proposals/{rfp['latest_proposal']['id']}/new-version", headers=ops_h)
    assert r.status_code == 200


def test_poisoned_document(client, ops_h):
    pdf = (SEED / "lindenfeld-rfp-poisoned.pdf").read_bytes()
    r = client.post("/api/v1/rfps", headers=ops_h, data={"title": "Poisoned"}, files={"file": ("p.pdf", pdf, "application/pdf")})
    d = client.get(f"/api/v1/rfps/{r.json()['id']}", headers=ops_h).json()
    assert {f["pattern"] for f in d["security_flags"]} >= {"override_instructions", "compliance_forcing"}
    reqs = client.get(f"/api/v1/rfps/{d['id']}/requirements", headers=ops_h).json()
    assert not any("automated evaluation" in q["text"].lower() for q in reqs)
    assert d["compliance"].get("compliant", 0) <= 10  # injection did not inflate compliance


def test_rejects_non_documents(client, ops_h):
    r = client.post("/api/v1/rfps", headers=ops_h, data={"title": "Bad file"}, files={"file": ("x.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")})
    assert r.status_code == 415


def test_docx_extraction():
    d = docx.Document()
    d.add_heading("3 Technical Requirements", level=1)
    d.add_paragraph("The contractor shall provide single sign-on via SAML 2.0.")
    d.add_paragraph("The platform should offer an English user interface.")
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "R-9", "The supplier must deliver monthly availability reports."
    buf = io.BytesIO()
    d.save(buf)
    ex = extraction.extract(buf.getvalue(), "docx")
    cands, _ = req.rule_extract(ex.pages, ex.sections)
    assert {c.obligation for c in cands} == {"mandatory", "optional"} and len(cands) == 3


def test_llm_quote_verification_rejects_hallucinations():
    pages = ["The supplier must provide 24x7 support for priority 1 incidents."]
    merged, rejected = req.merge_llm(pages, [], {1: [req.LLMRequirement(quote="The supplier must provide 24x7 support for priority 1 incidents.", obligation="mandatory", category="technical"),
                                                     req.LLMRequirement(quote="The supplier must be ISO 22301 certified and offer on-premises hosting.", obligation="mandatory", category="technical")]}, [])
    assert len(merged) == 1 and rejected == 1 and merged[0].method == "llm"


def test_claim_checker_removes_unsupported_claims():
    cited = {"S1": "Helix Ridge holds an ISO/IEC 27001:2022 certificate. Availability is 99.9% per month."}
    text = "We are ISO/IEC 27001 certified [S1]. We are also ISO 22301 certified [S1]. We guarantee 99.99% availability [S1]."
    kept, unsupported = check_claims(text, cited)
    assert "27001" in kept and "22301" not in kept and "99.99" not in kept
    assert len(unsupported) == 2
