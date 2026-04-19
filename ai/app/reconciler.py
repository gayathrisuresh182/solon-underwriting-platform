"""
Multi-source reconciler v2 — merges extraction results from pitch deck, SOC-2,
and GitHub into a single unified risk profile.

v2 improvements:
- Fuzzy string matching for conflict detection (#10)
- Weighted coverage score by field importance (#11)
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Canonical field schema
# ═══════════════════════════════════════════════════════════════════════

CANONICAL_FIELDS: list[tuple[str, str, list[str]]] = [
    ("company_name",            "scalar", ["pitch_deck", "soc2_report", "github_repo"]),
    ("industry",                "scalar", ["pitch_deck", "soc2_report"]),
    ("product_description",     "scalar", ["soc2_report", "github_repo"]),
    ("stage",                   "passthrough", ["pitch_deck"]),
    ("headcount",               "scalar", ["pitch_deck", "soc2_report", "github_repo"]),
    ("revenue_range",           "passthrough", ["pitch_deck"]),
    ("b2b_or_b2c",              "passthrough", ["pitch_deck"]),
    ("geographic_scope",        "passthrough", ["pitch_deck"]),
    ("tech_stack",              "list", ["pitch_deck", "soc2_report", "github_repo"]),
    ("primary_languages",       "list", ["github_repo"]),
    ("frameworks",              "list", ["github_repo"]),
    ("infrastructure",          "list", ["github_repo", "soc2_report"]),
    ("key_risks",               "list", ["pitch_deck"]),
    ("data_types_handled",      "list", ["soc2_report"]),
    ("compliance_frameworks",   "list", ["soc2_report"]),
    ("handles_pii",             "scalar", ["pitch_deck"]),
    ("handles_payments",        "scalar", ["pitch_deck"]),
    ("uses_ai_in_product",      "scalar", ["pitch_deck"]),
    ("has_soc2",                "scalar", ["pitch_deck", "soc2_report"]),
    ("audit_opinion",           "passthrough", ["soc2_report"]),
    ("audit_period",            "passthrough", ["soc2_report"]),
    ("auditor_name",            "passthrough", ["soc2_report"]),
    ("trust_services_categories", "list", ["soc2_report"]),
    ("controls_tested",         "passthrough", ["soc2_report"]),
    ("controls_passed",         "passthrough", ["soc2_report"]),
    ("controls_failed",         "passthrough", ["soc2_report"]),
    ("exception_count",         "passthrough", ["soc2_report"]),
    ("exceptions",              "passthrough", ["soc2_report"]),
    ("security_posture",        "passthrough", ["soc2_report"]),
    ("soc2_risk_score",         "passthrough", ["soc2_report"]),
    ("infrastructure_provider", "passthrough", ["soc2_report"]),
    ("github_org",              "passthrough", ["github_repo"]),
    ("engineering_maturity_score", "passthrough", ["github_repo"]),
    ("has_ci_cd",               "passthrough", ["github_repo"]),
    ("has_security_scanning",   "passthrough", ["github_repo"]),
    ("has_security_policy",     "passthrough", ["github_repo"]),
    ("has_docker",              "passthrough", ["github_repo"]),
    ("has_k8s",                 "passthrough", ["github_repo"]),
    ("security_tools",          "list", ["github_repo"]),
    ("repos_analyzed",          "passthrough", ["github_repo"]),
    ("public_repos_total",      "passthrough", ["github_repo"]),
]

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

# ═══════════════════════════════════════════════════════════════════════
# Weighted coverage score (#11)
# ═══════════════════════════════════════════════════════════════════════

FIELD_WEIGHTS: dict[str, int] = {
    # Critical fields (weight 3)
    "handles_pii": 3,
    "handles_payments": 3,
    "industry": 3,
    "stage": 3,
    "has_soc2": 3,
    # Important fields (weight 2)
    "headcount": 2,
    "revenue_range": 2,
    "uses_ai_in_product": 2,
    "b2b_or_b2c": 2,
    # Standard fields (weight 1)
    "geographic_scope": 1,
    "customer_type": 1,
    "tech_stack": 1,
    "product_description": 1,
    "key_risks": 1,
    "audit_opinion": 1,
    "exception_count": 1,
    "security_posture": 1,
    "engineering_maturity_score": 1,
    "has_security_scanning": 1,
}


# ═══════════════════════════════════════════════════════════════════════
# Fuzzy string matching (#10)
# ═══════════════════════════════════════════════════════════════════════

def _fuzzy_ratio(a: str, b: str) -> int:
    """Compute fuzzy similarity ratio (0-100) between two strings.

    Uses thefuzz if available, falls back to simple containment heuristic.
    """
    try:
        from thefuzz import fuzz
        return fuzz.token_sort_ratio(a, b)
    except ImportError:
        # Fallback: simple containment and length-based similarity
        a_lower = a.lower().strip()
        b_lower = b.lower().strip()
        if a_lower == b_lower:
            return 100
        if a_lower in b_lower or b_lower in a_lower:
            shorter = min(len(a_lower), len(b_lower))
            longer = max(len(a_lower), len(b_lower))
            return int(shorter / longer * 100) if longer > 0 else 0
        return 0


# ═══════════════════════════════════════════════════════════════════════
# Value helpers
# ═══════════════════════════════════════════════════════════════════════

def _parse_list_value(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(v) for v in raw]
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except (json.JSONDecodeError, TypeError):
                pass
        if raw:
            return [raw]
    return []


def _normalise_scalar(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("none", "null", "unknown", "n/a", "{}"):
        return None
    return s


def _values_agree(a: str, b: str) -> bool:
    """Check if two scalar values are semantically equivalent using fuzzy matching."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if a_lower == b_lower:
        return True
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        pass
    # Fuzzy matching: >= 85% similarity = agreement
    ratio = _fuzzy_ratio(a, b)
    if ratio >= 85:
        return True
    return False


def _classify_conflict(a: str, b: str) -> str:
    """Classify the type of conflict between two values.

    Returns: "match" | "soft_conflict" | "hard_conflict"
    """
    ratio = _fuzzy_ratio(a, b)
    if ratio >= 85:
        return "match"
    elif ratio >= 50:
        return "soft_conflict"
    else:
        return "hard_conflict"


def _conf_rank(level: str) -> int:
    return _CONFIDENCE_RANK.get(level, 0)


# ═══════════════════════════════════════════════════════════════════════
# Core reconciliation
# ═══════════════════════════════════════════════════════════════════════

def reconcile(extractions: list[dict]) -> dict[str, Any]:
    """Merge N extraction results into a unified risk profile."""
    by_type: dict[str, dict] = {}
    for ext in extractions:
        st = ext.get("source_type", "unknown")
        by_type[st] = ext

    merged_fields: dict[str, Any] = {}
    field_sources: dict[str, list[str]] = {}
    conflicts: list[dict] = []

    for field_name, strategy, provider_types in CANONICAL_FIELDS:
        candidates: list[tuple[Any, str, str]] = []
        for st in provider_types:
            ext = by_type.get(st)
            if ext is None:
                continue
            raw = ext.get("fields", {}).get(field_name)
            conf = ext.get("confidence_scores", {}).get(field_name, "medium")
            val = _normalise_scalar(raw) if strategy == "scalar" else raw
            if strategy == "scalar" and val is None:
                continue
            if strategy == "list" and not _parse_list_value(raw):
                continue
            if strategy == "passthrough" and _normalise_scalar(raw) is None:
                continue
            candidates.append((raw, conf, st))

        if not candidates:
            continue

        if strategy == "list":
            merged = _merge_list(field_name, candidates, field_sources)
            merged_fields[field_name] = json.dumps(merged)
        elif strategy == "passthrough":
            raw, conf, st = candidates[0]
            merged_fields[field_name] = str(raw)
            field_sources[field_name] = [st]
        else:
            value, conflict = _merge_scalar(field_name, candidates, field_sources)
            merged_fields[field_name] = value
            if conflict:
                conflicts.append(conflict)

    if "audit_opinion" in merged_fields and "has_soc2" not in merged_fields:
        merged_fields["has_soc2"] = "True"
        field_sources["has_soc2"] = ["soc2_report"]

    coverage = _calculate_coverage(merged_fields)

    return {
        "merged_fields": merged_fields,
        "field_sources": field_sources,
        "conflicts": conflicts,
        "coverage_score": coverage,
    }


def _merge_scalar(
    field_name: str,
    candidates: list[tuple[Any, str, str]],
    field_sources: dict[str, list[str]],
) -> tuple[str, dict | None]:
    """Merge scalar candidates with fuzzy conflict detection."""
    sources = [st for _, _, st in candidates]
    field_sources[field_name] = sources

    if len(candidates) == 1:
        return str(candidates[0][0]), None

    normalised = [(str(raw), conf, st) for raw, conf, st in candidates]
    normalised.sort(key=lambda x: _conf_rank(x[1]), reverse=True)
    best_val, best_conf, best_source = normalised[0]

    # Check agreement with fuzzy matching
    all_agree = all(_values_agree(best_val, v) for v, _, _ in normalised[1:])

    if all_agree:
        # If fuzzy match chose a shorter version, prefer the longer/more complete one
        longest = max(normalised, key=lambda x: len(x[0]))
        return longest[0], None

    # Classify the conflict type
    source_values = {st: val for val, _, st in normalised}
    second_val, second_conf, second_source = normalised[1]
    conflict_type = _classify_conflict(best_val, second_val)

    if conflict_type == "soft_conflict":
        reason = (
            f"Possible match (review recommended) -- {best_source} '{best_val}' vs "
            f"{second_source} '{second_val}' (similarity {_fuzzy_ratio(best_val, second_val)}%)"
        )
    else:
        reason = (
            f"{best_source} selected (confidence: {best_conf} vs "
            f"{second_source}: {second_conf})"
        )

    conflict = {
        "field": field_name,
        "sources": source_values,
        "selected": best_val,
        "selected_source": best_source,
        "conflict_type": conflict_type,
        "reason": reason,
    }
    return best_val, conflict


def _merge_list(
    field_name: str,
    candidates: list[tuple[Any, str, str]],
    field_sources: dict[str, list[str]],
) -> list[str]:
    sources = [st for _, _, st in candidates]
    field_sources[field_name] = sources

    seen_lower: dict[str, str] = {}
    for raw, _, _ in candidates:
        items = _parse_list_value(raw)
        for item in items:
            key = item.lower().strip()
            if not key:
                continue
            existing = seen_lower.get(key)
            if existing is None or (item[0].isupper() and not existing[0].isupper()):
                seen_lower[key] = item

    return sorted(seen_lower.values())


# ═══════════════════════════════════════════════════════════════════════
# Weighted coverage scoring (#11)
# ═══════════════════════════════════════════════════════════════════════

def _calculate_coverage(merged_fields: dict[str, Any]) -> float:
    """Weighted coverage score: critical fields count more than standard ones."""
    total_weight = sum(FIELD_WEIGHTS.values())
    populated_weight = 0

    for field, weight in FIELD_WEIGHTS.items():
        val = merged_fields.get(field)
        if val is not None and _normalise_scalar(val) is not None:
            populated_weight += weight

    return round(populated_weight / total_weight, 3) if total_weight > 0 else 0.0
