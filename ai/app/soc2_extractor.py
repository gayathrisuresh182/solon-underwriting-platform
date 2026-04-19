"""
SOC-2 Type II report extractor — two-pass hybrid architecture (v2).

Pass 1 (cheap):  PyMuPDF text extraction -> keyword-based page classification
                  with LLM fallback for ambiguous pages (#14).
Pass 2 (targeted): GPT-4o vision on high-value pages with knowledge-base
                    context injection and dual input for tables/findings (#11).

v2 improvements:
- Structured output JSON schemas (#10)
- Dual input (text + image) for control_table and findings pages (#11)
- Table-aware prompting for control extraction (#12)
- LLM fallback for ambiguous page classification (#14)
- Cross-page finding consolidation (#15)
- Security signal confidence tracking — explicit vs inferred (#17)

Output shape:
    {"fields": {}, "confidence_scores": {}, "citations": {}, "metadata": {}}
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from typing import Any

import fitz
from PIL import Image

from .soc2_prompts import (
    CLASSIFICATION_PROMPT,
    CLASSIFICATION_SCHEMA,
    CONTROL_TABLE_PROMPT,
    CONTROL_TABLE_SCHEMA,
    FINDINGS_PROMPT,
    FINDINGS_SCHEMA,
    OPINION_PROMPT,
    OPINION_SCHEMA,
    SOC2_SYSTEM_PROMPT,
    SYSTEM_DESCRIPTION_PROMPT,
    SYSTEM_DESCRIPTION_SCHEMA,
    TESTING_SUMMARY_PROMPT,
    TESTING_SUMMARY_SCHEMA,
)

from . import llm_client

logger = logging.getLogger(__name__)


# ── Page type taxonomy ─────────────────────────────────────────────────

PAGE_TYPES = (
    "cover", "table_of_contents", "auditor_opinion", "management_assertion",
    "system_description", "testing_methodology", "control_table",
    "testing_summary", "findings", "appendix", "glossary", "narrative",
)

HIGH_VALUE_TYPES = {"auditor_opinion", "system_description", "control_table", "findings", "testing_summary"}

# Pages that get dual input (text + image)
DUAL_INPUT_TYPES = {"control_table", "findings"}


# ═══════════════════════════════════════════════════════════════════════
# PASS 1 — Keyword-based page classification with LLM fallback (#14)
# ═══════════════════════════════════════════════════════════════════════

def _classify_page(text: str, page_num: int, total_pages: int) -> tuple[str, float]:
    """Classify a page by its dominant content type using keyword heuristics.

    Returns (page_type, confidence). Confidence < 0.5 means the classification
    is ambiguous and should be sent to LLM fallback.
    """
    t = text.lower()

    if page_num == 1 and ("soc 2" in t or "soc2" in t) and ("prepared by" in t or "audit period" in t):
        return "cover", 0.95

    if "table of contents" in t:
        return "table_of_contents", 0.95

    if ("independent auditor" in t or "independent service auditor" in t) and (
        "opinion" in t or "scope" in t or "in our opinion" in t
    ):
        return "auditor_opinion", 0.9

    if "management's assertion" in t or "management assertion" in t:
        return "management_assertion", 0.9

    if "appendix" in t or "complementary user entity" in t or "cuec-" in t:
        return "appendix", 0.85

    if "glossary" in t and "definition" not in t[:50].lower():
        return "glossary", 0.85

    if "summary of testing" in t and ("controls tested" in t or "pass rate" in t or "controls_passed" in t
                                      or "controls operating" in t or "metric" in t):
        return "testing_summary", 0.85

    if (("finding" in t and ("condition" in t or "management response" in t))
            or ("findings and observations" in t and "exception" in t)):
        return "findings", 0.8

    criteria_ids = re.findall(r"CC\d+\.\d+", text)
    if len(criteria_ids) >= 2 and ("pass" in t or "fail" in t or "test performed" in t
                                    or "test result" in t or "none noted" in t
                                    or "control activity" in t):
        return "control_table", 0.8

    if ("system description" in t or "overview of operations" in t
            or ("infrastructure" in t and ("data flow" in t or "personnel" in t))
            or "security policies and practices" in t
            or "risk management program" in t
            or ("subservice organization" in t or "third-party" in t and "management" in t)
            or ("personnel" in t and ("security" in t or "employees" in t) and page_num > 3)):
        return "system_description", 0.7

    if "testing methodology" in t or ("test procedures" in t and "sampling" in t):
        return "testing_methodology", 0.7

    if len(criteria_ids) >= 1 and ("exception" in t or "compensating" in t):
        return "findings", 0.6

    # If no strong match, return narrative with low confidence for LLM fallback
    keyword_count = sum(1 for kw in ["control", "security", "exception", "audit", "test"]
                        if kw in t)
    conf = 0.3 if keyword_count >= 2 else 0.7
    return "narrative", conf


async def _llm_classify_page(text: str) -> tuple[str, float]:
    """Use GPT-4o-mini to classify an ambiguous page. Cost ~$0.0005."""
    try:
        llm_resp = await llm_client.complete(
            system="You classify SOC-2 report pages into content categories.",
            messages=[
                {"role": "user", "content": CLASSIFICATION_PROMPT.format(
                    page_text=text[:2000]
                )},
            ],
            response_format=CLASSIFICATION_SCHEMA,
            temperature=0.0,
            max_tokens=200,
        )
        data = json.loads(llm_resp.content or "{}")
        page_type = data.get("page_type", "narrative")
        confidence = float(data.get("confidence", 0.5))
        if page_type not in PAGE_TYPES:
            page_type = "narrative"
        return page_type, confidence
    except Exception:
        logger.warning("LLM page classification fallback failed")
        return "narrative", 0.3


def _extract_text_pages(pdf_bytes: bytes) -> list[tuple[str, Image.Image]]:
    """Extract (text, PIL image) for every page in the PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[tuple[str, Image.Image]] = []
    for page in doc:
        text = page.get_text()
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        pages.append((text, img))
    doc.close()
    return pages


async def classify_all_pages(pdf_bytes: bytes) -> list[dict]:
    """Pass 1: classify every page, with LLM fallback for ambiguous ones."""
    pages = _extract_text_pages(pdf_bytes)
    total = len(pages)
    classified: list[dict] = []
    llm_fallback_count = 0

    for idx, (text, img) in enumerate(pages):
        ptype, conf = _classify_page(text, idx + 1, total)

        # #14: LLM fallback for low-confidence classifications
        if conf < 0.5 and ptype == "narrative":
            llm_type, llm_conf = await _llm_classify_page(text)
            if llm_conf > conf:
                ptype = llm_type
                conf = llm_conf
                llm_fallback_count += 1

        classified.append({
            "page": idx + 1,
            "type": ptype,
            "classification_confidence": round(conf, 2),
            "text": text,
            "image": img,
        })

    if llm_fallback_count:
        logger.info("LLM fallback classified %d ambiguous pages", llm_fallback_count)

    return classified


# ═══════════════════════════════════════════════════════════════════════
# Domain-term scanning (bridge between Pass 1 and Pass 2)
# ═══════════════════════════════════════════════════════════════════════

_CRITERIA_RE = re.compile(r"CC\d+\.\d+")
_SIGNAL_KEYWORDS = [
    "multi-factor authentication", "mfa", "2fa", "two-factor",
    "aes-256", "encrypted at rest", "encryption", "tls 1.2", "tls 1.3",
    "incident response", "penetration test", "pen test",
    "access review", "backup", "disaster recovery",
    "exception", "qualified", "unqualified", "compensating control",
]


def _scan_domain_terms(text: str) -> list[str]:
    terms: list[str] = []
    terms.extend(_CRITERIA_RE.findall(text))
    text_lower = text.lower()
    for kw in _SIGNAL_KEYWORDS:
        if kw in text_lower:
            terms.append(kw)
    return list(dict.fromkeys(terms))


def _build_domain_context(text: str) -> str:
    try:
        from knowledge_base.loader import build_context_for_terms
        terms = _scan_domain_terms(text)
        if not terms:
            return ""
        return build_context_for_terms(terms)
    except Exception:
        logger.debug("Knowledge base not available, skipping domain context")
        return ""


# ═══════════════════════════════════════════════════════════════════════
# PASS 2 — Targeted GPT-4o extraction with structured outputs
# ═══════════════════════════════════════════════════════════════════════

def _image_to_base64(img: Image.Image, max_dim: int = 1024) -> str:
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def _call_vision(
    img: Image.Image,
    prompt: str,
    schema: dict,
    page_text: str | None = None,
) -> dict | None:
    """Send a page to GPT-4o with structured output schema via unified client."""
    b64 = _image_to_base64(img)

    content: list[dict] = [{"type": "text", "text": prompt}]
    content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
    })

    try:
        llm_resp = await llm_client.complete(
            system=SOC2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            response_format=schema,
            temperature=0.1,
            max_tokens=3000,
            require_vision=True,
        )
        return json.loads(llm_resp.content or "{}")
    except json.JSONDecodeError:
        logger.warning("GPT-4o returned malformed JSON")
        return None
    except Exception:
        logger.exception("GPT-4o vision call failed")
        return None


# ── Per-page-type extraction helpers ───────────────────────────────────

async def _extract_opinion(page: dict) -> dict:
    ctx = _build_domain_context(page["text"])
    prompt = OPINION_PROMPT.format(page_number=page["page"], domain_context=ctx)
    result = await _call_vision(page["image"], prompt, OPINION_SCHEMA)
    return result or {}


async def _extract_system_description(page: dict) -> dict:
    ctx = _build_domain_context(page["text"])
    prompt = SYSTEM_DESCRIPTION_PROMPT.format(page_number=page["page"], domain_context=ctx)
    result = await _call_vision(page["image"], prompt, SYSTEM_DESCRIPTION_SCHEMA)
    return result or {}


async def _extract_control_table(page: dict) -> dict:
    """#11 + #12: Dual input with table-aware prompting."""
    ctx = _build_domain_context(page["text"])
    prompt = CONTROL_TABLE_PROMPT.format(
        page_number=page["page"],
        domain_context=ctx,
        page_text=page["text"][:3000],
    )
    result = await _call_vision(page["image"], prompt, CONTROL_TABLE_SCHEMA, page_text=page["text"])
    return result or {}


async def _extract_findings(page: dict) -> dict:
    """#11: Dual input for findings pages."""
    ctx = _build_domain_context(page["text"])
    prompt = FINDINGS_PROMPT.format(
        page_number=page["page"],
        domain_context=ctx,
        page_text=page["text"][:3000],
    )
    result = await _call_vision(page["image"], prompt, FINDINGS_SCHEMA, page_text=page["text"])
    return result or {}


async def _extract_testing_summary(page: dict) -> dict:
    ctx = _build_domain_context(page["text"])
    prompt = TESTING_SUMMARY_PROMPT.format(page_number=page["page"], domain_context=ctx)
    result = await _call_vision(page["image"], prompt, TESTING_SUMMARY_SCHEMA)
    return result or {}


# ═══════════════════════════════════════════════════════════════════════
# Security signal extraction with confidence tracking (#17)
# ═══════════════════════════════════════════════════════════════════════

def _extract_security_signals_from_text(all_text: str) -> tuple[dict[str, bool], dict[str, str]]:
    """Scan all text for security practice indicators.

    Returns (signals_dict, signal_evidence_dict) where evidence is
    "explicit" (directly stated) or "inferred" (absence-based).
    """
    try:
        from knowledge_base.loader import get_security_signals
        signals = get_security_signals()
    except Exception:
        return {}, {}

    results: dict[str, bool] = {}
    evidence: dict[str, str] = {}
    text_lower = all_text.lower()

    for sig_name, sig_def in signals.items():
        field = sig_def["risk_field"]
        positive_indicators = sig_def.get("positive_indicators", [])
        negative_indicators = sig_def.get("negative_indicators", [])

        found_positive = any(ind.lower() in text_lower for ind in positive_indicators)
        found_negative = any(ind.lower() in text_lower for ind in negative_indicators)

        if found_positive and not found_negative:
            results[field] = True
            evidence[field] = "explicit"
        elif found_negative and not found_positive:
            results[field] = False
            evidence[field] = "explicit"
        elif found_positive and found_negative:
            results[field] = True
            evidence[field] = "explicit"
        else:
            # No mentions at all — infer absence
            results[field] = False
            evidence[field] = "inferred"

    return results, evidence


# ═══════════════════════════════════════════════════════════════════════
# Cross-page finding consolidation (#15)
# ═══════════════════════════════════════════════════════════════════════

def _consolidate_findings(findings: list[dict]) -> list[dict]:
    """Merge findings that share the same criteria_id across pages."""
    by_criteria: dict[str, dict] = {}

    for f in findings:
        cid = f.get("criteria_id", "")
        if not cid:
            by_criteria[f"unknown_{len(by_criteria)}"] = f
            continue

        if cid not in by_criteria:
            by_criteria[cid] = dict(f)
        else:
            existing = by_criteria[cid]
            # Merge fields: prefer non-null values from later pages
            for key in ("finding_title", "condition", "risk_effect",
                        "management_response", "compensating_control"):
                if not existing.get(key) and f.get(key):
                    existing[key] = f[key]
                elif existing.get(key) and f.get(key) and existing[key] != f[key]:
                    existing[key] = f"{existing[key]} | {f[key]}"

            # Keep highest severity
            severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            if severity_rank.get(f.get("severity", ""), 0) > severity_rank.get(existing.get("severity", ""), 0):
                existing["severity"] = f["severity"]

    return list(by_criteria.values())


# ═══════════════════════════════════════════════════════════════════════
# SOC-2 risk scoring
# ═══════════════════════════════════════════════════════════════════════

def _calculate_soc2_risk_score(
    opinion: str,
    exceptions: list[dict],
    security_posture: dict[str, bool],
    controls_passed: int,
    controls_total: int,
) -> int:
    score = 15
    if opinion == "qualified":
        score += 25
    elif opinion != "unqualified":
        score += 15

    for exc in exceptions:
        severity = exc.get("severity", "high")
        if severity == "critical":
            score += 15
        elif severity == "high":
            score += 10
        elif severity == "medium":
            score += 5
        else:
            score += 3
        if exc.get("compensating_control"):
            score -= 3

    try:
        from knowledge_base.loader import get_security_signals
        signals = get_security_signals()
    except Exception:
        signals = {}

    for sig_name, sig_def in signals.items():
        field = sig_def["risk_field"]
        impact = sig_def.get("risk_impact_if_absent", 0)
        if not security_posture.get(field, False):
            score += impact

    return max(0, min(score, 100))


# ═══════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════

async def extract_from_soc2(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract structured risk data from a SOC-2 Type II report PDF."""
    start = time.time()

    # ── Pass 1: classify pages (with LLM fallback) ───────────────────
    classified = await classify_all_pages(pdf_bytes)
    total_pages = len(classified)
    all_text = "\n".join(p["text"] for p in classified)

    page_map: dict[str, list[dict]] = {}
    for p in classified:
        page_map.setdefault(p["type"], []).append(p)

    high_value_pages = [p for p in classified if p["type"] in HIGH_VALUE_TYPES]
    llm_classified = sum(1 for p in classified if p.get("classification_confidence", 1.0) < 0.5)

    logger.info(
        "SOC-2 Pass 1: %d pages total, %d high-value for GPT-4o, %d LLM-classified. Types: %s",
        total_pages, len(high_value_pages), llm_classified,
        {pt: len(ps) for pt, ps in page_map.items()},
    )

    # ── Pass 1b: security signal extraction with evidence tracking (#17) ──
    security_posture, signal_evidence = _extract_security_signals_from_text(all_text)

    # ── Pass 2: targeted GPT-4o extraction ────────────────────────────
    opinion_data: dict = {}
    system_desc_fields: dict[str, Any] = {}
    system_desc_confidence: dict[str, float] = {}
    system_desc_citations: dict[str, str] = {}
    all_controls: list[dict] = []
    all_findings: list[dict] = []
    testing_summary: dict = {}
    llm_calls = 0

    for p in page_map.get("auditor_opinion", []):
        result = await _extract_opinion(p)
        llm_calls += 1
        if result:
            for key in ("audit_opinion", "company_name", "audit_period",
                        "trust_services_categories", "auditor_name"):
                if key in result and result[key] is not None:
                    existing_conf = opinion_data.get("confidence", {}).get(key, -1)
                    new_conf = result.get("confidence", {}).get(key, 0.5) or 0.5
                    if new_conf > existing_conf:
                        opinion_data[key] = result[key]
                        opinion_data.setdefault("confidence", {})[key] = new_conf
                        opinion_data.setdefault("citations", {})[key] = (
                            result.get("citations", {}).get(key) or f"page {p['page']}"
                        )

    for p in page_map.get("system_description", []):
        result = await _extract_system_description(p)
        llm_calls += 1
        if result:
            fields = result.get("fields", result)
            conf = result.get("confidence", {})
            cit = result.get("citations", {})
            for field, value in fields.items():
                if value is None or field in ("confidence", "citations"):
                    continue
                new_conf = float(conf.get(field, 0.5) or 0.5)
                old_conf = system_desc_confidence.get(field, -1.0)
                if new_conf > old_conf:
                    system_desc_fields[field] = value
                    system_desc_confidence[field] = new_conf
                    system_desc_citations[field] = cit.get(field) or f"page {p['page']}"

    for p in page_map.get("control_table", []):
        result = await _extract_control_table(p)
        llm_calls += 1
        if result:
            all_controls.extend(result.get("controls", []))

    for p in page_map.get("findings", []):
        result = await _extract_findings(p)
        llm_calls += 1
        if result:
            all_findings.extend(result.get("findings", []))

    for p in page_map.get("testing_summary", []):
        result = await _extract_testing_summary(p)
        llm_calls += 1
        if result:
            testing_summary = result

    # ── #15: Cross-page finding consolidation ─────────────────────────
    consolidated_findings = _consolidate_findings(all_findings)

    # ── Merge and structure results ───────────────────────────────────
    elapsed_ms = int((time.time() - start) * 1000)

    controls_total = len(all_controls) or testing_summary.get("total_controls_tested", 0)
    controls_passed = sum(1 for c in all_controls if c.get("passed", True))
    controls_failed = controls_total - controls_passed

    exceptions_from_controls = [c for c in all_controls if not c.get("passed", True)]
    exception_criteria_from_controls = {
        c["criteria_id"] for c in exceptions_from_controls if "criteria_id" in c
    }
    exception_criteria_from_findings = {
        f["criteria_id"] for f in consolidated_findings if "criteria_id" in f
    }
    all_exception_criteria = exception_criteria_from_controls | exception_criteria_from_findings

    merged_exceptions: list[dict] = []
    seen_criteria: set[str] = set()
    for finding in consolidated_findings:
        cid = finding.get("criteria_id", "")
        merged_exceptions.append(finding)
        seen_criteria.add(cid)
    for ctrl in exceptions_from_controls:
        cid = ctrl.get("criteria_id", "")
        if cid not in seen_criteria:
            merged_exceptions.append({
                "criteria_id": cid,
                "finding_title": f"{cid} Exception",
                "condition": ctrl.get("exception_description", "Exception noted"),
                "severity": "high",
            })
            seen_criteria.add(cid)

    opinion = opinion_data.get("audit_opinion", "unknown")

    risk_score = _calculate_soc2_risk_score(
        opinion=opinion,
        exceptions=merged_exceptions,
        security_posture=security_posture,
        controls_passed=controls_passed,
        controls_total=controls_total,
    )

    # ── Build output ──────────────────────────────────────────────────
    fields: dict[str, Any] = {
        "company_name": opinion_data.get("company_name", system_desc_fields.get("company_name", "Unknown")),
        "industry": system_desc_fields.get("industry"),
        "product_description": system_desc_fields.get("product_description"),
        "infrastructure_provider": system_desc_fields.get("infrastructure_provider"),
        "tech_stack": system_desc_fields.get("tech_stack", []),
        "data_types_handled": system_desc_fields.get("data_types_handled", []),
        "headcount": system_desc_fields.get("headcount"),
        "compliance_frameworks": system_desc_fields.get("compliance_frameworks", []),
        "audit_opinion": opinion,
        "audit_period": opinion_data.get("audit_period"),
        "auditor_name": opinion_data.get("auditor_name"),
        "trust_services_categories": opinion_data.get("trust_services_categories", []),
        "controls_tested": controls_total,
        "controls_passed": controls_passed,
        "controls_failed": controls_failed,
        "exception_count": len(merged_exceptions),
        "exceptions": json.dumps(merged_exceptions),
        "security_posture": json.dumps(security_posture),
        "soc2_risk_score": risk_score,
    }

    confidence_scores: dict[str, Any] = {}
    for k, v in opinion_data.get("confidence", {}).items():
        confidence_scores[k] = _conf_level(v)
    for k, v in system_desc_confidence.items():
        confidence_scores[k] = _conf_level(v)
    confidence_scores["controls_tested"] = "high" if all_controls else "low"
    confidence_scores["exception_count"] = "high" if consolidated_findings else ("medium" if exceptions_from_controls else "low")

    citations: dict[str, str] = {}
    citations.update(opinion_data.get("citations", {}))
    citations.update(system_desc_citations)
    if all_controls:
        ctrl_pages = sorted({c.get("page_number", "?") for c in all_controls if "page_number" in c}
                            | {p["page"] for p in page_map.get("control_table", [])})
        citations["controls_tested"] = f"Control tables on pages {ctrl_pages}"
    if consolidated_findings:
        finding_pages = sorted({p["page"] for p in page_map.get("findings", [])})
        citations["exceptions"] = f"Findings on pages {finding_pages}"

    # #17: Security signal evidence in citations
    for field, ev_type in signal_evidence.items():
        citations[field] = f"security signal ({ev_type})"

    metadata: dict[str, Any] = {
        "source_type": "soc2_report",
        "extraction_time_ms": elapsed_ms,
        "total_pages": total_pages,
        "pages_sent_to_llm": len(high_value_pages),
        "llm_calls": llm_calls,
        "llm_classified_pages": llm_classified,
        "page_classification": {p["page"]: p["type"] for p in classified},
        "audit_opinion": opinion,
        "controls_tested": controls_total,
        "controls_passed": controls_passed,
        "exceptions_found": len(merged_exceptions),
        "exception_details": merged_exceptions,
        "security_posture": security_posture,
        "signal_evidence": signal_evidence,
        "soc2_risk_score": risk_score,
        "findings_consolidated": len(all_findings) != len(consolidated_findings),
        "raw_findings_count": len(all_findings),
        "consolidated_findings_count": len(consolidated_findings),
    }

    serialized_fields: dict[str, str] = {}
    for k, v in fields.items():
        if isinstance(v, (list, dict)):
            serialized_fields[k] = json.dumps(v)
        elif v is not None:
            serialized_fields[k] = str(v)

    return {
        "fields": serialized_fields,
        "confidence_scores": confidence_scores,
        "citations": citations,
        "metadata": metadata,
    }


def _conf_level(score: float | None) -> str:
    if score is None:
        return "low"
    if score >= 0.8:
        return "high"
    elif score >= 0.5:
        return "medium"
    return "low"
