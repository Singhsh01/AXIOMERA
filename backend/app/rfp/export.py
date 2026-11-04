"""Proposal export to DOCX (python-docx) and PDF (ReportLab).

Both formats contain: cover page, table of contents, numbered sections, running header and
footer with page numbers and review status, the compliance matrix as a table, references with
evidence ids, and document metadata. A JSON evidence manifest (chunk id + SHA-256 of the
evidence text for every citation) is stored with the export so any statement can be traced back
to the exact evidence version it was generated from.
"""
from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from app.core.security import sha256_hex

INK = RGBColor(0x14, 0x17, 0x2B)
ACCENT = RGBColor(0x5B, 0x4B, 0xD6)
STATUS_LABEL = {"compliant": "Compliant", "partially_compliant": "Partially compliant", "non_compliant": "Non-compliant", "unverified": "Unverified"}


def manifest(proposal: dict[str, Any], chunk_texts: dict[str, str]) -> dict[str, Any]:
    return {
        "proposal_id": proposal["id"], "version": proposal["version"], "generated_at": datetime.now(UTC).isoformat(),
        "generator": proposal.get("generator", {}),
        "sections": {s["key"]: [{"ref": c["ref"], "chunk_id": c["chunk_id"], "document": c["document"],
                                 "evidence_sha256": sha256_hex(chunk_texts.get(c["chunk_id"], ""))}
                                for c in s.get("citations", []) if "ref" in c] for s in proposal["sections"]},
    }


# ------------------------------------------------------------------ DOCX
def _field(paragraph, instr: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    for tag, attr in (("w:fldChar", {"w:fldCharType": "begin"}), ("w:instrText", None), ("w:fldChar", {"w:fldCharType": "separate"})):
        el = OxmlElement(tag)
        if attr:
            for k, v in attr.items():
                el.set(qn(k), v)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = instr
        run._r.append(el)
    paragraph.add_run(placeholder)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(end)


def _shade(cell, hex_fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def to_docx(ctx: dict[str, Any]) -> bytes:
    p, rfp, company, final = ctx["proposal"], ctx["rfp"], ctx["company"], ctx["final"]
    status_line = "APPROVED FOR SUBMISSION" if final else "DRAFT — NOT APPROVED FOR SUBMISSION"
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)
    for lvl, size in ((1, 15), (2, 12.5)):
        hs = doc.styles[f"Heading {lvl}"]
        hs.font.name, hs.font.size, hs.font.color.rgb, hs.font.bold = "Calibri", Pt(size), INK, True
    cp = doc.core_properties
    cp.title = f"Proposal — {rfp['title']}"
    cp.subject = rfp.get("reference") or ""
    cp.author = company
    cp.keywords = f"axiomera; proposal; v{p['version']}; {'final' if final else 'draft'}"
    cp.comments = f"Review status: {p['status']}. Evidence manifest sha256: {ctx['manifest_sha']}"

    # Cover
    for _ in range(6):
        doc.add_paragraph()
    t = doc.add_paragraph()
    r = t.add_run("PROPOSAL")
    r.font.size, r.font.color.rgb, r.bold = Pt(11), ACCENT, True
    t = doc.add_paragraph()
    r = t.add_run(rfp["title"])
    r.font.size, r.bold, r.font.color.rgb = Pt(26), True, INK
    doc.add_paragraph(f"Submitted to {rfp.get('issuer') or 'the contracting authority'}" + (f" · Ref. {rfp['reference']}" if rfp.get("reference") else ""))
    doc.add_paragraph(f"Prepared by {company}")
    meta = doc.add_table(rows=4, cols=2)
    for i, (k, v) in enumerate([("Version", str(p["version"])), ("Date", datetime.now(UTC).strftime("%d %B %Y")),
                                ("Review status", p["status"].replace("_", " ").title()), ("Submission deadline", rfp.get("due") or "—")]):
        meta.cell(i, 0).text, meta.cell(i, 1).text = k, v
    s = doc.add_paragraph()
    r = s.add_run(status_line)
    r.bold, r.font.color.rgb = True, RGBColor(0x0F, 0x76, 0x6E) if final else RGBColor(0xB4, 0x23, 0x18)

    # Body section with header/footer
    body = doc.add_section(WD_SECTION.NEW_PAGE)
    body.header.is_linked_to_previous = False
    body.footer.is_linked_to_previous = False
    hp = body.header.paragraphs[0]
    hp.text = f"{company} · Proposal for {rfp.get('reference') or rfp['title'][:40]} · {status_line}"
    hp.runs[0].font.size, hp.runs[0].font.color.rgb = Pt(8), RGBColor(0x55, 0x5B, 0x70)
    fp = body.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.add_run("Page ").font.size = Pt(8)
    _field(fp, "PAGE", "1")
    fp.add_run(" · Confidential").font.size = Pt(8)
    doc.sections[0].different_first_page_header_footer = True

    doc.add_heading("Table of Contents", level=1)
    _field(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u', "")
    for i, sec in enumerate(p["sections"], start=1):
        doc.add_paragraph(f"{i}.  {sec['title']}", style="List Paragraph")
    doc.add_paragraph(f"{len(p['sections']) + 1}.  Annex A — Compliance Matrix", style="List Paragraph")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    for i, sec in enumerate(p["sections"], start=1):
        doc.add_heading(f"{i}. {sec['title']}", level=1)
        for para in (sec["content"] or "").split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip()[2:] if para.strip().startswith("- ") else para.strip(),
                                  style="List Bullet" if para.strip().startswith("- ") else None)
        if sec.get("citations") and sec["key"] != "supporting_references":
            src = doc.add_paragraph()
            run = src.add_run("Sources: " + "; ".join(f"[{c['ref']}] {c['document']} (evidence {c['chunk_id'][:8]})" for c in sec["citations"]))
            run.font.size, run.italic, run.font.color.rgb = Pt(8), True, RGBColor(0x55, 0x5B, 0x70)
        if sec.get("unsupported_claims") and not final:
            w = doc.add_paragraph()
            run = w.add_run(f"Reviewer note: {len(sec['unsupported_claims'])} unsupported claim(s) were removed from this section.")
            run.font.size, run.font.color.rgb = Pt(8), RGBColor(0xB4, 0x23, 0x18)

    doc.add_heading(f"{len(p['sections']) + 1}. Annex A — Compliance Matrix", level=1)
    tbl = doc.add_table(rows=1, cols=5)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(["ID", "Requirement", "Source", "Status", "Evidence"]):
        c = tbl.rows[0].cells[i]
        c.text = h
        c.paragraphs[0].runs[0].bold = True
        _shade(c, "E8E6FB")
    fills = {"compliant": "DCF5EA", "partially_compliant": "FFF4D6", "non_compliant": "FDE2E1", "unverified": "EEF0F4"}
    for row in ctx["matrix"]:
        cells = tbl.add_row().cells
        cells[0].text = row["code"]
        cells[1].text = row["text"][:300]
        cells[2].text = f"p. {row['page']}"
        cells[3].text = STATUS_LABEL.get(row["status"], row["status"])
        _shade(cells[3], fills.get(row["status"], "FFFFFF"))
        cells[4].text = "; ".join(e["document"] for e in row["evidence"][:2]) or "—"
        for c in cells:
            for para in c.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(8)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


# ------------------------------------------------------------------ PDF
class _ProposalDoc(BaseDocTemplate):
    def __init__(self, buf, ctx):
        super().__init__(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
                         title=f"Proposal — {ctx['rfp']['title']}", author=ctx["company"], subject=ctx["rfp"].get("reference") or "",
                         keywords=f"axiomera proposal v{ctx['proposal']['version']}")
        self.ctx = ctx
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("cover", [frame]), PageTemplate("body", [frame], onPage=self._decorate)])

    def _decorate(self, canv, doc):
        c = self.ctx
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(colors.HexColor("#555B70"))
        canv.drawString(20 * mm, A4[1] - 12 * mm, f"{c['company']} · Proposal for {c['rfp'].get('reference') or c['rfp']['title'][:40]}")
        status = "APPROVED FOR SUBMISSION" if c["final"] else "DRAFT — NOT APPROVED"
        canv.setFillColor(colors.HexColor("#0F766E" if c["final"] else "#B42318"))
        canv.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, status)
        canv.setFillColor(colors.HexColor("#555B70"))
        canv.drawCentredString(A4[0] / 2, 10 * mm, f"Page {doc.page} · Confidential")
        canv.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {"H1"}:
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))


def to_pdf(ctx: dict[str, Any]) -> bytes:
    p, rfp = ctx["proposal"], ctx["rfp"]
    ss = getSampleStyleSheet()
    ink = colors.HexColor("#14172B")
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, textColor=ink, spaceBefore=6, spaceAfter=8)
    body = ParagraphStyle("B", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.8, leading=14)
    small = ParagraphStyle("S", parent=body, fontSize=7.6, leading=10, textColor=colors.HexColor("#555B70"))
    cell = ParagraphStyle("C", parent=body, fontSize=7.4, leading=9.5)
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731

    story: list[Any] = [Spacer(1, 55 * mm),
                        Paragraph("PROPOSAL", ParagraphStyle("k", parent=body, textColor=colors.HexColor("#5B4BD6"), fontName="Helvetica-Bold")),
                        Paragraph(esc(rfp["title"]), ParagraphStyle("T", parent=H1, fontSize=24, leading=29)),
                        Paragraph(esc(f"Submitted to {rfp.get('issuer') or 'the contracting authority'}" + (f" · Ref. {rfp['reference']}" if rfp.get("reference") else "")), body),
                        Paragraph(esc(f"Prepared by {ctx['company']}"), body), Spacer(1, 8 * mm)]
    meta = [["Version", str(p["version"])], ["Date", datetime.now(UTC).strftime("%d %B %Y")],
            ["Review status", p["status"].replace("_", " ").title()], ["Submission deadline", rfp.get("due") or "—"]]
    t = Table(meta, colWidths=[45 * mm, 90 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555B70")),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9DCE6"))]))
    story += [t, Spacer(1, 6 * mm), Paragraph("APPROVED FOR SUBMISSION" if ctx["final"] else "DRAFT — NOT APPROVED FOR SUBMISSION",
                                              ParagraphStyle("st", parent=body, fontName="Helvetica-Bold",
                                                             textColor=colors.HexColor("#0F766E" if ctx["final"] else "#B42318")))]
    from reportlab.platypus.doctemplate import NextPageTemplate

    story += [NextPageTemplate("body"), PageBreak(), Paragraph("Table of Contents", ParagraphStyle("toc", parent=H1))]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t0", parent=body, fontSize=10, leftIndent=0, firstLineIndent=0)]
    story += [toc, PageBreak()]
    for i, sec in enumerate(p["sections"], start=1):
        story.append(Paragraph(f"{i}. {esc(sec['title'])}", H1))
        for para in (sec["content"] or "").split("\n"):
            if para.strip():
                txt = esc(para.strip())
                story.append(Paragraph(("• " + txt[2:]) if txt.startswith("- ") else txt, body))
                story.append(Spacer(1, 2 * mm))
        if sec.get("citations") and sec["key"] != "supporting_references":
            story.append(Paragraph(esc("Sources: " + "; ".join(f"[{c['ref']}] {c['document']} (evidence {c['chunk_id'][:8]})" for c in sec["citations"])), small))
        story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"{len(p['sections']) + 1}. Annex A — Compliance Matrix", H1))
    rows = [[Paragraph(f"<b>{h}</b>", cell) for h in ["ID", "Requirement", "Src", "Status", "Evidence"]]]
    fills = {"compliant": "#DCF5EA", "partially_compliant": "#FFF4D6", "non_compliant": "#FDE2E1", "unverified": "#EEF0F4"}
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9CCD8")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E6FB")),
             ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, r in enumerate(ctx["matrix"], start=1):
        rows.append([Paragraph(r["code"], cell), Paragraph(esc(r["text"][:260]), cell), Paragraph(f"p.{r['page']}", cell),
                     Paragraph(STATUS_LABEL.get(r["status"], r["status"]), cell),
                     Paragraph(esc("; ".join(e["document"] for e in r["evidence"][:2]) or "—"), cell)])
        style.append(("BACKGROUND", (3, i), (3, i), colors.HexColor(fills.get(r["status"], "#FFFFFF"))))
    tbl = Table(rows, colWidths=[16 * mm, 78 * mm, 11 * mm, 24 * mm, 41 * mm], repeatRows=1)
    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(esc(f"Evidence manifest SHA-256: {ctx['manifest_sha']}"), small))
    buf = io.BytesIO()
    _ProposalDoc(buf, ctx).multiBuild(story)
    return buf.getvalue()


def manifest_bytes(m: dict[str, Any]) -> bytes:
    return json.dumps(m, sort_keys=True, indent=2).encode()


_ = TA_CENTER  # keep import for style tweaks
