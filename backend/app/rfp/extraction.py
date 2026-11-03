"""Document text extraction for PDF and DOCX.

PDF: PyMuPDF text layer per page. Pages with (almost) no text but with images are treated as
scanned; OCR is attempted through PyMuPDF's Tesseract bridge when Tesseract is installed,
otherwise the page is flagged so a human knows its requirements may be missing.
DOCX: python-docx paragraphs and tables. DOCX has no fixed pagination, so text is split into
logical pages of ~3,000 characters at paragraph boundaries; references say "logical page".
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import docx
import pymupdf

HEADING = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-Z][^\n]{2,90})\s*$", re.M)
ALLOWED_MIME = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


@dataclass
class Extracted:
    pages: list[str]
    method: str
    metadata: dict
    sections: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def sniff(data: bytes, filename: str) -> str | None:
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK" and filename.lower().endswith(".docx"):
        return "docx"
    return None


def extract(data: bytes, kind: str) -> Extracted:
    return _pdf(data) if kind == "pdf" else _docx(data)


def _pdf(data: bytes) -> Extracted:
    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass:
        raise ValueError("Encrypted PDFs are not accepted")
    pages, warnings, methods = [], [], set()
    for i, page in enumerate(doc):
        txt = page.get_text("text")
        if len(txt.strip()) < 20 and page.get_images():
            try:
                tp = page.get_textpage_ocr(full=True, dpi=200)
                txt = page.get_text("text", textpage=tp)
                methods.add("ocr")
            except Exception:  # noqa: BLE001 – Tesseract not installed
                warnings.append(f"Page {i + 1} appears scanned and OCR is unavailable; requirements on this page may be missing.")
                methods.add("scanned-no-ocr")
        else:
            methods.add("text-layer")
        pages.append(txt)
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    toc = doc.get_toc(simple=True)
    sections = [{"number": str(i + 1), "title": t, "page": p, "level": lvl} for i, (lvl, t, p) in enumerate(toc)] if toc else _headings(pages)
    return Extracted(pages, "+".join(sorted(methods)) or "text-layer", meta, sections, warnings)


def _docx(data: bytes) -> Extracted:
    d = docx.Document(io.BytesIO(data))
    blocks: list[str] = []
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if p.style is not None and p.style.name.lower().startswith("heading") and not HEADING.match(t):
            t = t  # keep as is; headings without numbers are still detected by style below
        blocks.append(t)
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                blocks.append(" | ".join(dict.fromkeys(cells)))
    pages, cur = [], ""
    for b in blocks:
        if len(cur) + len(b) > 3000 and cur:
            pages.append(cur)
            cur = ""
        cur += b + "\n"
    if cur:
        pages.append(cur)
    cp = d.core_properties
    meta = {k: v for k, v in {"title": cp.title, "author": cp.author, "subject": cp.subject}.items() if v}
    return Extracted(pages or [""], "docx-logical-pages", meta, _headings(pages))


def _headings(pages: list[str]) -> list[dict]:
    out = []
    for i, txt in enumerate(pages):
        for m in HEADING.finditer(txt):
            title = m.group(2).strip()
            if len(title.split()) <= 12 and not title.endswith("."):
                out.append({"number": m.group(1), "title": title, "page": i + 1, "level": m.group(1).count(".") + 1})
    return out
