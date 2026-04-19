"""
Knowledge base loader for SOC-2 ontology and insurance domain terminology.

Loads YAML files once at import time and exposes lookup functions used to
augment extraction prompts with domain context.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).parent

_soc2: dict[str, Any] = {}
_insurance: dict[str, Any] = {}
_loaded = False


def _load_all() -> None:
    global _soc2, _insurance, _loaded
    if _loaded:
        return

    _soc2 = _load_yaml("soc2_ontology.yaml")
    _insurance = _load_yaml("insurance_terms.yaml")
    _loaded = True


def _load_yaml(filename: str) -> dict[str, Any]:
    path = _KB_DIR / filename
    if not path.exists():
        logger.warning("Knowledge base file not found: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        logger.info("Loaded knowledge base: %s (%d top-level keys)", filename, len(data or {}))
        return data or {}
    except Exception:
        logger.exception("Failed to load knowledge base file: %s", filename)
        return {}


# ── Public API ──────────────────────────────────────────────────────────


def get_criteria_definition(criteria_id: str) -> dict[str, Any] | None:
    """Look up a SOC-2 Trust Services Criteria by ID (e.g. 'CC6.1').

    Returns a dict with keys: category, definition, risk_implication,
    affected_coverages, risk_weight — or None if not found.
    """
    _load_all()
    return _soc2.get("trust_services_criteria", {}).get(criteria_id)


def get_term_definition(term: str) -> dict[str, Any] | None:
    """Look up an audit finding type or insurance term by key.

    Searches audit_finding_types first, then coverage_types, then
    trust_services_categories.
    """
    _load_all()

    result = _soc2.get("audit_finding_types", {}).get(term)
    if result:
        return result

    result = _insurance.get("coverage_types", {}).get(term)
    if result:
        return result

    result = _soc2.get("trust_services_categories", {}).get(term)
    if result:
        return result

    return None


def get_security_signals() -> dict[str, Any]:
    """Return all security signal definitions with positive/negative indicators."""
    _load_all()
    return _soc2.get("security_signals", {})


def get_coverage_info(coverage_type: str) -> dict[str, Any] | None:
    """Look up full details for an insurance coverage type (e.g. 'cyber')."""
    _load_all()
    return _insurance.get("coverage_types", {}).get(coverage_type)


def build_context_for_terms(terms_found: list[str]) -> str:
    """Given terms found on a page, build a formatted context block for prompt injection.

    Searches across criteria IDs, audit finding types, security signals,
    and coverage types to provide relevant domain context.
    """
    _load_all()

    sections: list[str] = []

    criteria = _soc2.get("trust_services_criteria", {})
    findings = _soc2.get("audit_finding_types", {})
    signals = _soc2.get("security_signals", {})
    coverages = _insurance.get("coverage_types", {})

    matched_criteria: list[str] = []
    matched_findings: list[str] = []
    matched_signals: list[str] = []
    matched_coverages: list[str] = []

    terms_lower = [t.lower() for t in terms_found]

    for cid, cdef in criteria.items():
        if cid.lower() in terms_lower or cid in terms_found:
            matched_criteria.append(
                f"  {cid} ({cdef['category']}): {cdef['definition']}\n"
                f"    Risk: {cdef['risk_implication']} | Weight: {cdef['risk_weight']}"
            )

    for ftype, fdef in findings.items():
        if ftype.lower() in terms_lower or ftype.replace("_", " ") in terms_lower:
            matched_findings.append(
                f"  {ftype}: {fdef['definition']}\n"
                f"    Severity: {fdef['severity']} | Auto-bind: {fdef['auto_bind_eligible']}"
            )

    for sig_name, sig_def in signals.items():
        all_indicators = sig_def.get("positive_indicators", []) + sig_def.get("negative_indicators", [])
        for indicator in all_indicators:
            if indicator.lower() in terms_lower or any(indicator.lower() in t for t in terms_lower):
                matched_signals.append(
                    f"  {sig_name} (field: {sig_def['risk_field']}): "
                    f"risk impact if absent = +{sig_def['risk_impact_if_absent']} points"
                )
                break

    for ctype, cdef in coverages.items():
        if ctype in terms_lower or cdef.get("full_name", "").lower() in terms_lower:
            abbr = cdef.get("abbreviation", "")
            label = f"{cdef['full_name']} ({abbr})" if abbr else cdef["full_name"]
            matched_coverages.append(f"  {label}: {cdef['description']}")

    if matched_criteria:
        sections.append("SOC-2 CRITERIA REFERENCED:\n" + "\n".join(matched_criteria))
    if matched_findings:
        sections.append("AUDIT FINDING TYPES:\n" + "\n".join(matched_findings))
    if matched_signals:
        sections.append("SECURITY SIGNALS DETECTED:\n" + "\n".join(matched_signals))
    if matched_coverages:
        sections.append("INSURANCE COVERAGES:\n" + "\n".join(matched_coverages))

    if not sections:
        return ""

    return (
        "─── DOMAIN CONTEXT (from knowledge base) ───\n"
        + "\n\n".join(sections)
        + "\n─── END DOMAIN CONTEXT ───"
    )
