"""Company knowledge store with hybrid retrieval.

Lexical: PostgreSQL full-text search (GIN expression index, ts_rank_cd).
Semantic: pgvector cosine distance over 384-d embeddings.
Fusion: Reciprocal Rank Fusion (k=60).

The default embedder is a deterministic feature-hashing embedder (word unigrams + bigrams +
character trigrams). It needs no model download, which keeps the stack usable on an 8 GB
laptop; set AXIOMERA_EMBEDDING_PROVIDER=openai to use a hosted embedding model instead.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import sha256_hex
from app.db import utcnow
from app.models import EMBED_DIM, KnowledgeChunk, KnowledgeDocument

STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to was were will with
we our you your they their shall must should may can not no all any each per via into than then also such""".split())
_WORD = re.compile(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]")


def tokens(text_: str) -> list[str]:
    return [t for t in _WORD.findall(text_.lower()) if t not in STOP]


def _h(feature: str) -> tuple[int, float]:
    d = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    idx = int.from_bytes(d[:4], "little") % EMBED_DIM
    sign = 1.0 if d[4] & 1 else -1.0
    return idx, sign


def hashing_embed(text_: str) -> list[float]:
    vec = [0.0] * EMBED_DIM
    toks = tokens(text_)
    feats: list[tuple[str, float]] = [(f"w:{t}", 1.0) for t in toks]
    feats += [(f"b:{a}_{b}", 0.7) for a, b in zip(toks, toks[1:])]
    for t in toks:
        padded = f"#{t}#"
        feats += [(f"c:{padded[i:i + 3]}", 0.25) for i in range(len(padded) - 2)]
    for f, w in feats:
        i, s = _h(f)
        vec[i] += s * w
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if s.embedding_provider == "openai" and s.openai_api_key:
        r = httpx.post(f"{s.openai_base_url.rstrip('/')}/embeddings", timeout=30,
                       headers={"Authorization": f"Bearer {s.openai_api_key}"},
                       json={"model": "text-embedding-3-small", "input": texts, "dimensions": EMBED_DIM})
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    return [hashing_embed(t) for t in texts]


def chunk_markdown(body: str, max_chars: int = 900) -> list[tuple[str | None, str]]:
    """Split by headings, then by paragraphs, keeping chunks under max_chars."""
    chunks: list[tuple[str | None, str]] = []
    heading: str | None = None
    buf: list[str] = []

    def flush():
        if buf:
            joined = "\n".join(buf).strip()
            if joined:
                chunks.append((heading, joined))
            buf.clear()

    for para in re.split(r"\n\s*\n", body):
        lines = para.strip().splitlines()
        while lines and re.match(r"^#{1,4}\s+", lines[0]):
            flush()
            heading = re.sub(r"^#{1,4}\s+", "", lines.pop(0)).strip()
        p = "\n".join(lines).strip()
        if not p:
            continue
        if sum(len(x) for x in buf) + len(p) > max_chars:
            flush()
        buf.append(p)
    flush()
    return chunks


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        return meta, body
    return meta, raw


def ingest(db: Session, workspace_id: str, *, title: str, kind: str, body: str, source: str,
           approved: bool = True, valid_until: datetime | None = None) -> KnowledgeDocument:
    digest = sha256_hex(body)
    existing = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.workspace_id == workspace_id,
                                                          KnowledgeDocument.sha256 == digest)).first()
    if existing:
        return existing
    doc = KnowledgeDocument(workspace_id=workspace_id, title=title, kind=kind, source=source, sha256=digest,
                            approved=approved, valid_until=valid_until)
    db.add(doc)
    db.flush()
    parts = chunk_markdown(body)
    vectors = embed([f"{h or ''}\n{t}" for h, t in parts])
    for i, ((heading, txt), v) in enumerate(zip(parts, vectors)):
        db.add(KnowledgeChunk(document_id=doc.id, workspace_id=workspace_id, ordinal=i, heading=heading, text=txt, embedding=v))
    db.flush()
    return doc


def _or_query(q: str) -> str | None:
    terms = [re.sub(r"[^a-z0-9]", "", t) for t in tokens(q)]
    terms = [t for t in dict.fromkeys(terms) if len(t) > 1][:24]
    return " | ".join(terms) if terms else None


def search(db: Session, workspace_id: str, query: str, *, k: int = 6, kinds: list[str] | None = None,
           approved_only: bool = True, rrf_k: int = 60) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"ws": workspace_id, "lim": k * 4, "now": utcnow()}
    filt = "c.workspace_id = :ws AND (d.valid_until IS NULL OR d.valid_until > :now)"
    if approved_only:
        filt += " AND d.approved"
    if kinds:
        filt += " AND d.kind = ANY(:kinds)"
        params["kinds"] = kinds

    lexical: list[tuple[str, float]] = []
    tsq = _or_query(query)
    if tsq:
        params["tsq"] = tsq
        lexical = [(r[0], float(r[1])) for r in db.execute(text(f"""
            SELECT c.id, ts_rank_cd(to_tsvector('english', c.text), to_tsquery('english', :tsq)) AS r
            FROM knowledge_chunks c JOIN knowledge_documents d ON d.id = c.document_id
            WHERE {filt} AND to_tsvector('english', c.text) @@ to_tsquery('english', :tsq)
            ORDER BY r DESC LIMIT :lim"""), params)]

    params["qv"] = str(embed([query])[0])
    semantic = [(r[0], 1 - float(r[1])) for r in db.execute(text(f"""
        SELECT c.id, c.embedding <=> CAST(:qv AS vector) AS dist
        FROM knowledge_chunks c JOIN knowledge_documents d ON d.id = c.document_id
        WHERE {filt} ORDER BY dist ASC LIMIT :lim"""), params)]

    fused: dict[str, dict[str, Any]] = {}
    for rank, (cid, score) in enumerate(lexical):
        fused.setdefault(cid, {"rrf": 0.0})["rrf"] += 1 / (rrf_k + rank + 1)
        fused[cid]["lexical"] = round(score, 4)
    for rank, (cid, sim) in enumerate(semantic):
        fused.setdefault(cid, {"rrf": 0.0})["rrf"] += 1 / (rrf_k + rank + 1)
        fused[cid]["semantic"] = round(sim, 4)
    top = sorted(fused.items(), key=lambda kv: kv[1]["rrf"], reverse=True)[:k]
    if not top:
        return []
    chunks = {c.id: c for c in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_([t[0] for t in top])))}
    out = []
    for cid, sc in top:
        c = chunks[cid]
        out.append({
            "chunk_id": c.id, "document_id": c.document_id, "document_title": c.document.title, "kind": c.document.kind,
            "heading": c.heading, "text": c.text, "source": c.document.source,
            "scores": {"rrf": round(sc["rrf"], 5), "lexical": sc.get("lexical"), "semantic": sc.get("semantic")},
        })
    return out
