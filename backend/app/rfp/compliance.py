"""Evidence-based compliance assessment.

A requirement is only marked *compliant* when retrieved, approved, unexpired company knowledge
covers its key terms and passes the specific checks (named certifications, numeric thresholds).
Explicit negative statements in approved standard responses yield *non-compliant*. Anything else
is *partially compliant* or *unverified* with a description of what is missing.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.platform import knowledge

GENERIC = set("""bidder supplier vendor contractor provider tenderer solution proposal proposals offer system platform
service services provide provided providing support supported including include ensure ensuring able capability
required requirement requirements shall must should may describe demonstrate state confirm minimum least within
hold holds valid current offered operation bidders suppliers
using industry standards standard appropriate state-of-the-art accordance""".split())
CERT = re.compile(r"\b(ISO(?:/IEC)?\s?\d{4,5}(?::\d{4})?|SOC\s?2(?:\s+Type\s+(?:II|I|2|1))?|BSI\s?C5|TISAX|PCI[\s-]?DSS|ISO\s?9001)\b", re.I)
PERCENT = re.compile(r"(\d{2,3}(?:[.,]\d{1,3})?)\s?%")
NEGATIVE = re.compile(r"\b(not supported|do(?:es)? not (?:support|offer|provide)|is not available|are not available|cannot be|no on-?prem|not offered|we do not)\b", re.I)


def key_terms(text: str) -> set[str]:
    return {t for t in knowledge.tokens(text) if t not in GENERIC and len(t) > 2 and not t.isdigit()}


def _norm_cert(s: str) -> str:
    s = re.sub(r"\s+", "", s.upper().replace("/IEC", ""))
    s = s.replace("TYPE2", "TYPEII").replace("TYPE1", "TYPEI")
    return re.sub(r":\d{4}$", "", s)


def assess(db: Session, workspace_id: str, requirement_text: str, k: int = 5) -> dict[str, Any]:
    hits = knowledge.search(db, workspace_id, requirement_text, k=k)
    terms = key_terms(requirement_text)
    evidence = []
    for h in hits:
        htoks = set(knowledge.tokens(h["text"] + " " + (h["heading"] or "")))
        cov = len(terms & htoks) / len(terms) if terms else 0.0
        evidence.append({"chunk_id": h["chunk_id"], "document_id": h["document_id"], "document": h["document_title"], "kind": h["kind"],
                         "heading": h["heading"], "excerpt": h["text"][:500], "coverage": round(cov, 2), "scores": h["scores"],
                         "matched_terms": sorted(terms & htoks)[:12]})
    evidence.sort(key=lambda e: (e["coverage"], e["scores"]["rrf"]), reverse=True)
    checks: list[dict[str, Any]] = []
    missing: list[str] = []

    # Certification checks: each named certificate must appear in an approved certification document.
    req_certs = {_norm_cert(c) for c in CERT.findall(requirement_text)}
    if req_certs:
        cert_hits = knowledge.search(db, workspace_id, " ".join(req_certs) + " certificate certification", k=8, kinds=["certification"])
        held = {_norm_cert(c) for h in cert_hits for c in CERT.findall(h["text"] + " " + h["document_title"])}
        for c in sorted(req_certs):
            ok = any(c == x or (c.startswith("SOC2") and x.startswith("SOC2") and (c == "SOC2" or c == x)) for x in held)
            checks.append({"check": f"certificate:{c}", "passed": ok})
            if not ok:
                missing.append(f"No approved, valid certificate evidence for {c}.")
            else:
                ch = next(h for h in cert_hits if any(_norm_cert(x) == c or (c == "SOC2" and _norm_cert(x).startswith("SOC2")) for x in CERT.findall(h["text"] + " " + h["document_title"])))
                if ch["chunk_id"] not in {e["chunk_id"] for e in evidence}:
                    evidence.insert(0, {"chunk_id": ch["chunk_id"], "document_id": ch["document_id"], "document": ch["document_title"], "kind": "certification",
                                        "heading": ch["heading"], "excerpt": ch["text"][:500], "coverage": 1.0, "scores": ch["scores"], "matched_terms": [c]})

    # Numeric threshold checks (e.g. availability percentages).
    req_pct = [float(p.replace(",", ".")) for p in PERCENT.findall(requirement_text)]
    if req_pct:
        target = max(req_pct)
        ev_pct = [(float(p.replace(",", ".")), e) for e in evidence if e["coverage"] >= 0.3 for p in PERCENT.findall(e["excerpt"])]
        relevant = [v for v, _ in ev_pct if 90 <= v <= 100] if target >= 90 else [v for v, _ in ev_pct]
        if relevant:
            best = max(relevant)
            checks.append({"check": f"threshold:{target}%", "passed": best >= target, "evidence_value": best})
            if best < target:
                missing.append(f"Evidence states {best}% but the requirement asks for {target}%.")
        else:
            checks.append({"check": f"threshold:{target}%", "passed": False, "evidence_value": None})
            missing.append(f"No evidence stating a value for the {target}% threshold.")

    top = evidence[0] if evidence else None
    best_cov = top["coverage"] if top else 0.0
    def negated(e: dict[str, Any]) -> bool:
        # The negation must be in the same clause as the requirement's key terms.
        for clause in re.split(r"[.;:]\s+|,\s+(?:but|while|whereas)\s+", e["excerpt"]):
            if NEGATIVE.search(clause) and terms:
                ctoks = set(knowledge.tokens(clause))
                if len(terms & ctoks) / len(terms) >= 0.5:
                    return True
        return False

    negative = next((e for e in evidence if e["kind"] in {"standard_response", "product"} and negated(e)), None)
    failed = [c for c in checks if not c["passed"]]

    if negative:
        status = "non_compliant"
        rationale = f"Approved response '{negative['document']}' states this is not offered."
        evidence = [negative] + [e for e in evidence if e is not negative]
    elif req_certs and failed and all(c["check"].startswith("certificate:") for c in failed) and len(failed) == len([c for c in checks if c["check"].startswith("certificate:")]):
        status = "unverified"
        rationale = "Required certification could not be evidenced from approved, valid documents."
    elif req_certs and checks and not failed:
        status = "compliant"
        rationale = "Valid certificate evidence found for " + ", ".join(sorted(req_certs)) + "."
    elif best_cov >= 0.6 and not failed:
        status = "compliant"
        rationale = f"Covered by '{top['document']}' ({int(best_cov * 100)}% of key terms" + (", all checks passed)." if checks else ").")
    elif best_cov >= 0.35 or (top and checks and not failed):
        status = "partially_compliant"
        rationale = f"Partial coverage by '{top['document']}' ({int(best_cov * 100)}% of key terms)" + ("; " + "; ".join(missing) if missing else ".")
        if not missing:
            missing.append("Evidence covers only part of the requirement; confirm remaining scope: " + ", ".join(sorted(terms - set(top["matched_terms"]))[:8]))
    else:
        status = "unverified"
        rationale = "No sufficiently relevant approved evidence found."
        missing.append("Provide evidence or an approved standard response for this requirement.")

    # Only passages that actually bear on the requirement are attached as evidence.
    evidence = [e for e in evidence if e["coverage"] >= 0.35 or e["kind"] == "certification" and any(c["passed"] for c in checks)]
    if status == "compliant" and not evidence:  # invariant: never compliant without evidence
        status = "unverified"
    return {"status": status, "rationale": rationale, "evidence": evidence[:4], "checks": checks,
            "missing_info": " ".join(dict.fromkeys(missing)) or None, "key_terms": sorted(terms)}
