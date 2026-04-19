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


def reload() -> None:
    """Force reload of all knowledge base files."""
    global _loaded
    _loaded = False
    _load_all()


# ── Original API ────────────────────────────────────────────────────────


def get_criteria_definition(criteria_id: str) -> dict[str, Any] | None:
    """Look up a SOC-2 Trust Services Criteria by ID (e.g. 'CC6.1')."""
    _load_all()
    return _soc2.get("trust_services_criteria", {}).get(criteria_id)


def get_term_definition(term: str) -> dict[str, Any] | None:
    """Look up an audit finding type or insurance term by key."""
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
    """Given terms found on a page, build a formatted context block for prompt injection."""
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
        "--- DOMAIN CONTEXT (from knowledge base) ---\n"
        + "\n\n".join(sections)
        + "\n--- END DOMAIN CONTEXT ---"
    )


# ── New API: Compliance frameworks (#1) ─────────────────────────────────


def get_compliance_requirements(framework: str) -> dict[str, Any] | None:
    """Look up a compliance framework by name (HIPAA, PCI-DSS, SOX, GDPR).

    Returns dict with: full_name, requirements, mandatory_controls,
    affected_coverages, triggering_conditions, penalty_risk.
    """
    _load_all()
    frameworks = _insurance.get("compliance_frameworks", {})
    # Try exact match first, then case-insensitive
    result = frameworks.get(framework)
    if result:
        return result
    for key, val in frameworks.items():
        if key.lower() == framework.lower() or key.replace("-", "").lower() == framework.replace("-", "").lower():
            return val
    return None


def get_all_compliance_frameworks() -> dict[str, Any]:
    """Return all compliance framework definitions."""
    _load_all()
    return _insurance.get("compliance_frameworks", {})


def detect_applicable_frameworks(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Given a company profile (merged_fields), detect which compliance
    frameworks likely apply.

    Returns list of {framework, full_name, reason, affected_coverages}.
    """
    _load_all()
    frameworks = _insurance.get("compliance_frameworks", {})
    results: list[dict[str, Any]] = []

    industry = str(profile.get("industry", "")).lower()
    data_types = str(profile.get("data_types_handled", "")).lower()
    geo = str(profile.get("geographic_scope", "")).lower()
    handles_payments = str(profile.get("handles_payments", "")).lower() in ("true", "yes")

    for name, fdef in frameworks.items():
        triggers = fdef.get("triggering_conditions", {})
        reasons: list[str] = []

        for ind in triggers.get("industries", []):
            if ind.lower() in industry:
                reasons.append(f"Industry matches: {ind}")

        for dt in triggers.get("data_types", []):
            if dt.lower() in data_types:
                reasons.append(f"Data type detected: {dt}")

        field_triggers = triggers.get("fields", {})
        for field, expected in field_triggers.items():
            actual = profile.get(field, "")
            if str(actual).lower() == str(expected).lower():
                reasons.append(f"Field {field}={expected}")
            elif field == "geographic_scope" and expected == "international" and "international" in geo:
                reasons.append("International scope triggers GDPR")

        if reasons:
            results.append({
                "framework": name,
                "full_name": fdef.get("full_name", name),
                "reasons": reasons,
                "affected_coverages": fdef.get("affected_coverages", []),
                "mandatory_controls": fdef.get("mandatory_controls", []),
            })

    return results


# ── New API: Coverage recommendations (#3) ──────────────────────────────


def get_coverage_recommendation(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Match a company profile to the best coverage recommendation.

    Profile should contain: industry, handles_payments, handles_pii,
    b2b_or_b2c, uses_ai_in_product.

    Returns the best-match recommendation dict or None.
    """
    _load_all()
    recommendations = _insurance.get("coverage_recommendations", [])
    if not recommendations:
        return None

    industry = str(profile.get("industry", "")).lower()
    best_match: dict[str, Any] | None = None
    best_score = 0

    for rec in recommendations:
        rec_profile = rec.get("profile", {})
        score = 0

        # Industry keyword matching
        for keyword in rec_profile.get("industry_keywords", []):
            if keyword.lower() in industry:
                score += 2
                break

        # Boolean field matching
        for field in ("handles_payments", "handles_pii", "uses_ai_in_product"):
            if field in rec_profile:
                actual = str(profile.get(field, "")).lower() in ("true", "yes")
                if actual == rec_profile[field]:
                    score += 1

        # B2B/B2C matching
        if "b2b_or_b2c" in rec_profile:
            actual_model = str(profile.get("b2b_or_b2c", "")).upper()
            if actual_model == rec_profile["b2b_or_b2c"].upper():
                score += 1

        if score > best_score:
            best_score = score
            best_match = rec

    return best_match


def get_all_coverage_recommendations() -> list[dict[str, Any]]:
    """Return all coverage recommendation profiles."""
    _load_all()
    return _insurance.get("coverage_recommendations", [])


# ── New API: Weight justifications (#2) ─────────────────────────────────


def get_weight_justification(rule_id: str) -> str | None:
    """Look up the justification for a rule's weight by rule ID.

    Searches both rule_justifications in soc2_ontology and
    security_signals justifications.
    """
    _load_all()

    # Check rule justifications
    justifications = _soc2.get("rule_justifications", {})
    entry = justifications.get(rule_id)
    if entry:
        return entry.get("justification")

    # Check security signals
    signals = _soc2.get("security_signals", {})
    for sig_name, sig_def in signals.items():
        if sig_name == rule_id:
            return sig_def.get("justification")

    # Check criteria
    criteria = _soc2.get("trust_services_criteria", {})
    entry = criteria.get(rule_id)
    if entry:
        return entry.get("justification")

    return None
