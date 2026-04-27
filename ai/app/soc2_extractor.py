"""
SOC-2 Type II report extractor — Docling-powered architecture (v3).

Uses Docling DocumentConverter for structured document parsing:
  - Tables extracted deterministically as DataFrames (no LLM needed)
  - Prose sections classified by heading keywords and extracted via text-only LLM
  - No Vision API calls — all LLM interactions are text-only

v3 improvements over v2 (PyMuPDF + Vision):
- Deterministic table extraction via Docling's layout-aware parser
- 10x cheaper: text-only LLM calls vs Vision API
- No rate limit issues: no image token consumption
- Faster: no base64 encoding, no Vision API latency

Output shape (unchanged):
    {"fields": {}, "confidence_scores": {}, "citations": {}, "metadata": {}}
"""

from __future__ import annotations

import json
import logging
import re
import time
from io import BytesIO
from typing import Any

import pandas as pd
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from .soc2_prompts import (
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

_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    """Singleton Docling converter — heavy init, reuse across calls.

    Uses PyPdfium2 backend for maximum stability and lowest memory usage.
    Our SOC-2 PDFs are digital text (not scanned), so OCR is unnecessary.
    Table structure from Docling layout model is best-effort; for pages
    where layout detection fails, we fall back to text-only LLM extraction.
    """
    global _converter
    if _converter is None:
        pipeline_options = PdfPipelineOptions(
            do_ocr=False,
            do_code_enrichment=False,
            do_formula_enrichment=False,
            do_picture_classification=False,
            do_picture_description=False,
            generate_page_images=False,
            generate_picture_images=False,
            generate_table_images=False,
            images_scale=1.0,
        )
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=PyPdfiumDocumentBackend,
                ),
            }
        )
    return _converter


# ═══════════════════════════════════════════════════════════════════════
# Section classification (heading-based, replaces page-level keyword pass)
# ═══════════════════════════════════════════════════════════════════════

def _classify_section(heading: str, body_text: str) -> str:
    """Classify a markdown section by heading and body keywords."""
    h = heading.lower()
    t = body_text.lower()[:2000]

    if "independent auditor" in h or "independent service auditor" in h or (
        "opinion" in h and ("auditor" in h or "report" in h)
    ):
        return "auditor_opinion"

    if ("system description" in h
            or ("description of" in h and "system" in h)
            or "overview of operations" in h):
        return "system_description"
    if "infrastructure" in h and ("personnel" in h or "data" in h):
        return "system_description"
    if "security policies" in h or "risk management" in h:
        return "system_description"

    if ("control activit" in h or "tests of operating effectiveness" in h
            or "section iv" in h and "test" in h):
        return "control_table"

    if ("finding" in h or "exception" in h or "observation" in h
            or "section v" in h and ("finding" in h or "exception" in h)):
        return "findings"

    if "summary of testing" in h or "testing results" in h or "testing summary" in h:
        return "testing_summary"

    if "in our opinion" in t and ("material respects" in t or "trust services" in t):
        return "auditor_opinion"
    if "system description" in t and ("infrastructure" in t or "personnel" in t):
        return "system_description"
    if re.search(r"CC\d+\.\d+", body_text) and ("pass" in t or "fail" in t or "none noted" in t):
        return "control_table"
    if "finding" in t and ("condition" in t or "management response" in t):
        return "findings"

    return "other"


def _split_markdown_sections(md_text: str) -> list[dict]:
    """Split markdown into sections by headings."""
    sections: list[dict] = []
    lines = md_text.split("\n")
    current_heading = ""
    current_body_lines: list[str] = []

    for line in lines:
        if line.startswith("#"):
            if current_heading or current_body_lines:
                body = "\n".join(current_body_lines).strip()
                if body:
                    sections.append({
                        "heading": current_heading,
                        "body": body,
                        "type": _classify_section(current_heading, body),
                    })
            current_heading = line.lstrip("#").strip()
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_heading or current_body_lines:
        body = "\n".join(current_body_lines).strip()
        if body:
            sections.append({
                "heading": current_heading,
                "body": body,
                "type": _classify_section(current_heading, body),
            })

    return sections


# ═══════════════════════════════════════════════════════════════════════
# Deterministic table extraction (no LLM)
# ═══════════════════════════════════════════════════════════════════════

def _is_control_table(df: pd.DataFrame) -> bool:
    cols = [str(c).lower() for c in df.columns]
    has_criteria = any("criteria" in c or "control id" in c for c in cols)
    has_result = any("result" in c or "pass" in c or "fail" in c or "status" in c for c in cols)
    return has_criteria and has_result


def _is_testing_summary_table(df: pd.DataFrame) -> bool:
    cols = [str(c).lower() for c in df.columns]
    all_text = " ".join(cols + [str(v).lower() for v in df.values.flatten()])
    return ("metric" in all_text or "summary" in all_text) and (
        "controls tested" in all_text or "pass rate" in all_text or "total" in all_text
    )


def _extract_controls_from_dataframe(df: pd.DataFrame) -> list[dict]:
    """Extract control entries from a SOC-2 control table DataFrame."""
    controls: list[dict] = []
    cols_lower = {c: str(c).lower() for c in df.columns}

    criteria_col = next(
        (c for c, cl in cols_lower.items() if "criteria" in cl or "control id" in cl), None
    )
    desc_col = next(
        (c for c, cl in cols_lower.items()
         if "description" in cl or "control activity" in cl or "activity" in cl),
        None,
    )
    test_col = next(
        (c for c, cl in cols_lower.items()
         if "test performed" in cl or ("test" in cl and "result" not in cl)),
        None,
    )
    result_col = next(
        (c for c, cl in cols_lower.items()
         if "result" in cl or "status" in cl),
        None,
    )
    exception_col = next(
        (c for c, cl in cols_lower.items() if "exception" in cl or "finding" in cl), None
    )

    for _, row in df.iterrows():
        criteria_id = str(row.get(criteria_col, "")).strip() if criteria_col else ""
        if not criteria_id or not re.match(r"[A-Z]+\d", criteria_id):
            continue

        result_text = str(row.get(result_col, "")).lower() if result_col else ""
        passed = "pass" in result_text or "no exception" in result_text or "none noted" in result_text
        if "fail" in result_text or "exception noted" in result_text:
            passed = False

        exception_desc = str(row.get(exception_col, "")).strip() if exception_col else None
        if exception_desc in ("", "nan", "None", "None noted", "None noted.", "N/A", "none noted"):
            exception_desc = None

        controls.append({
            "criteria_id": criteria_id,
            "category": None,
            "control_description": str(row.get(desc_col, "")).strip()[:500] if desc_col else None,
            "test_performed": str(row.get(test_col, "")).strip()[:500] if test_col else None,
            "passed": passed,
            "exception_description": exception_desc if not passed else None,
        })

    return controls


def _extract_testing_summary_from_dataframe(df: pd.DataFrame) -> dict:
    """Extract testing summary metrics from a summary table DataFrame."""
    summary: dict[str, Any] = {}
    for _, row in df.iterrows():
        vals = [str(v).lower().strip() for v in row.values]
        row_text = " ".join(vals)

        if "total" in row_text and ("control" in row_text or "tested" in row_text):
            num = _extract_int(vals)
            if num is not None:
                summary["total_controls_tested"] = num
        elif "pass" in row_text and "rate" not in row_text:
            num = _extract_int(vals)
            if num is not None:
                summary["controls_passed"] = num
        elif "exception" in row_text or ("fail" in row_text and "rate" not in row_text):
            num = _extract_int(vals)
            if num is not None:
                summary["controls_with_exceptions"] = num
        elif "pass rate" in row_text or "pass %" in row_text:
            num = _extract_pct(vals)
            if num is not None:
                summary["pass_rate"] = num

    return summary


def _extract_int(vals: list[str]) -> int | None:
    for v in vals:
        v_clean = v.replace(",", "").strip()
        if v_clean.isdigit():
            return int(v_clean)
    return None


def _extract_pct(vals: list[str]) -> float | None:
    for v in vals:
        v_clean = v.replace("%", "").replace(",", "").strip()
        try:
            f = float(v_clean)
            return f / 100 if f > 1 else f
        except ValueError:
            continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# Domain-term scanning (bridge to knowledge base)
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
# Text-only LLM extraction helpers
# ═══════════════════════════════════════════════════════════════════════

async def _extract_opinion_text(section_text: str) -> dict:
    ctx = _build_domain_context(section_text)
    prompt = OPINION_PROMPT.format(section_text=section_text[:4000], domain_context=ctx)
    try:
        resp = await llm_client.complete(
            system=SOC2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            response_format=OPINION_SCHEMA,
            temperature=0.1,
            max_tokens=2000,
            require_vision=False,
        )
        return json.loads(resp.content or "{}")
    except Exception:
        logger.exception("Opinion text extraction failed")
        return {}


async def _extract_system_description_text(section_text: str) -> dict:
    ctx = _build_domain_context(section_text)
    prompt = SYSTEM_DESCRIPTION_PROMPT.format(section_text=section_text[:6000], domain_context=ctx)
    try:
        resp = await llm_client.complete(
            system=SOC2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            response_format=SYSTEM_DESCRIPTION_SCHEMA,
            temperature=0.1,
            max_tokens=3000,
            require_vision=False,
        )
        return json.loads(resp.content or "{}")
    except Exception:
        logger.exception("System description text extraction failed")
        return {}


async def _extract_findings_text(section_text: str) -> dict:
    ctx = _build_domain_context(section_text)
    prompt = FINDINGS_PROMPT.format(section_text=section_text[:6000], domain_context=ctx)
    try:
        resp = await llm_client.complete(
            system=SOC2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            response_format=FINDINGS_SCHEMA,
            temperature=0.1,
            max_tokens=3000,
            require_vision=False,
        )
        return json.loads(resp.content or "{}")
    except Exception:
        logger.exception("Findings text extraction failed")
        return {}


async def _extract_control_table_text(section_text: str) -> dict:
    """Fallback: extract controls from text when Docling table detection misses them."""
    ctx = _build_domain_context(section_text)
    prompt = CONTROL_TABLE_PROMPT.format(section_text=section_text[:6000], domain_context=ctx)
    try:
        resp = await llm_client.complete(
            system=SOC2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            response_format=CONTROL_TABLE_SCHEMA,
            temperature=0.1,
            max_tokens=4000,
            require_vision=False,
        )
        return json.loads(resp.content or "{}")
    except Exception:
        logger.exception("Control table text extraction failed")
        return {}


async def _extract_testing_summary_text(section_text: str) -> dict:
    ctx = _build_domain_context(section_text)
    prompt = TESTING_SUMMARY_PROMPT.format(section_text=section_text[:4000], domain_context=ctx)
    try:
        resp = await llm_client.complete(
            system=SOC2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            response_format=TESTING_SUMMARY_SCHEMA,
            temperature=0.1,
            max_tokens=1000,
            require_vision=False,
        )
        return json.loads(resp.content or "{}")
    except Exception:
        logger.exception("Testing summary text extraction failed")
        return {}


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
            results[field] = False
            evidence[field] = "inferred"

    return results, evidence


# ═══════════════════════════════════════════════════════════════════════
# Cross-page finding consolidation (#15)
# ═══════════════════════════════════════════════════════════════════════

def _consolidate_findings(findings: list[dict]) -> list[dict]:
    """Merge findings that share the same criteria_id across sections."""
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
            for key in ("finding_title", "condition", "risk_effect",
                        "management_response", "compensating_control"):
                if not existing.get(key) and f.get(key):
                    existing[key] = f[key]
                elif existing.get(key) and f.get(key) and existing[key] != f[key]:
                    existing[key] = f"{existing[key]} | {f[key]}"

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
    """Extract structured risk data from a SOC-2 Type II report PDF.

    Uses Docling for deterministic document parsing (tables as DataFrames)
    and text-only LLM calls for prose section extraction.
    """
    start = time.time()

    # ── Step 1: Parse PDF with Docling ────────────────────────────────
    converter = _get_converter()
    buf = BytesIO(pdf_bytes)
    stream = DocumentStream(name="soc2_report.pdf", stream=buf)
    conv_result = converter.convert(stream)
    doc = conv_result.document

    total_pages = len(doc.pages) if doc.pages else 0
    full_markdown = doc.export_to_markdown()

    # Free PDF backend resources to prevent memory leaks
    try:
        if conv_result.input and conv_result.input._backend:
            conv_result.input._backend.unload()
    except Exception:
        pass

    logger.info(
        "Docling parsed SOC-2: %d pages, %d tables, %d text elements",
        total_pages, len(doc.tables), len(doc.texts),
    )

    # ── Step 2: Deterministic table extraction (no LLM) ──────────────
    all_controls: list[dict] = []
    testing_summary: dict = {}
    tables_processed = 0

    for table in doc.tables:
        try:
            df = table.export_to_dataframe(doc=doc)
            if df.empty:
                continue
            tables_processed += 1

            if _is_control_table(df):
                controls = _extract_controls_from_dataframe(df)
                all_controls.extend(controls)
                logger.info("Control table: extracted %d controls deterministically", len(controls))
            elif _is_testing_summary_table(df):
                testing_summary = _extract_testing_summary_from_dataframe(df)
                logger.info("Testing summary table: %s", testing_summary)
        except Exception:
            logger.warning("Failed to process Docling table %d", tables_processed, exc_info=True)

    # ── Step 3: Classify markdown sections and extract via text-only LLM
    sections = _split_markdown_sections(full_markdown)
    section_map: dict[str, list[dict]] = {}
    for s in sections:
        section_map.setdefault(s["type"], []).append(s)

    logger.info("Sections classified: %s", {k: len(v) for k, v in section_map.items()})

    security_posture, signal_evidence = _extract_security_signals_from_text(full_markdown)

    opinion_data: dict = {}
    system_desc_fields: dict[str, Any] = {}
    system_desc_confidence: dict[str, float] = {}
    system_desc_citations: dict[str, str] = {}
    all_findings: list[dict] = []
    llm_calls = 0

    for s in section_map.get("auditor_opinion", []):
        result = await _extract_opinion_text(s["body"])
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
                            result.get("citations", {}).get(key) or f"section: {s['heading']}"
                        )

    for s in section_map.get("system_description", []):
        result = await _extract_system_description_text(s["body"])
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
                    system_desc_citations[field] = cit.get(field) or f"section: {s['heading']}"

    # Extract controls from text when Docling didn't find control tables
    if not all_controls:
        for s in section_map.get("control_table", []):
            result = await _extract_control_table_text(s["body"])
            llm_calls += 1
            if result:
                all_controls.extend(result.get("controls", []))

    for s in section_map.get("findings", []):
        result = await _extract_findings_text(s["body"])
        llm_calls += 1
        if result:
            all_findings.extend(result.get("findings", []))

    if not testing_summary:
        for s in section_map.get("testing_summary", []):
            result = await _extract_testing_summary_text(s["body"])
            llm_calls += 1
            if result:
                testing_summary = result

    # ── Step 4: Consolidate and score ─────────────────────────────────
    consolidated_findings = _consolidate_findings(all_findings)
    elapsed_ms = int((time.time() - start) * 1000)

    controls_total = len(all_controls) or testing_summary.get("total_controls_tested", 0)
    controls_passed = sum(1 for c in all_controls if c.get("passed", True))
    controls_failed = controls_total - controls_passed

    exceptions_from_controls = [c for c in all_controls if not c.get("passed", True)]

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

    # ── Build output (same shape as v2 for pipeline compatibility) ────
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
    confidence_scores["exception_count"] = (
        "high" if consolidated_findings
        else ("medium" if exceptions_from_controls else "low")
    )

    citations: dict[str, str] = {}
    citations.update(opinion_data.get("citations", {}))
    citations.update(system_desc_citations)
    if all_controls:
        citations["controls_tested"] = (
            f"Deterministic extraction from {tables_processed} Docling tables "
            f"({len(all_controls)} controls)"
        )
    if consolidated_findings:
        citations["exceptions"] = f"Consolidated from {len(all_findings)} raw findings"

    for field, ev_type in signal_evidence.items():
        citations[field] = f"security signal ({ev_type})"

    metadata: dict[str, Any] = {
        "source_type": "soc2_report",
        "extraction_method": "docling",
        "extraction_time_ms": elapsed_ms,
        "total_pages": total_pages,
        "docling_tables_found": len(doc.tables),
        "docling_text_elements": len(doc.texts),
        "tables_processed": tables_processed,
        "sections_classified": {k: len(v) for k, v in section_map.items()},
        "llm_calls": llm_calls,
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
