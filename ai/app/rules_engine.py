"""
Generic declarative rules engine v2 — evaluates YAML-defined underwriting rules
against a reconciled risk profile.

v2 additions:
- Coverage recommendation integration from knowledge base (#14)
- Human-readable risk explanation (#15)
- Decline explanation with remediation path (#16)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_rules_cache: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════════════════
# Loading
# ═══════════════════════════════════════════════════════════════════════

def load_rules(path: str) -> dict:
    abs_path = os.path.abspath(path)
    if abs_path in _rules_cache:
        return _rules_cache[abs_path]
    with open(abs_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _rules_cache[abs_path] = data
    return data


def clear_cache() -> None:
    _rules_cache.clear()


# ═══════════════════════════════════════════════════════════════════════
# Value coercion helpers
# ═══════════════════════════════════════════════════════════════════════

def _coerce_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        low = val.strip().lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
    return None


def _coerce_number(val: Any) -> float | None:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.strip())
        except (ValueError, TypeError):
            return None
    return None


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        s = val.strip().lower()
        return s in ("", "none", "null", "n/a", "unknown", "{}", "[]")
    return False


def _parse_json_field(raw: Any) -> Any:
    if isinstance(raw, str):
        raw = raw.strip()
        if raw and raw[0] in ("{", "["):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
    return raw


# ═══════════════════════════════════════════════════════════════════════
# Condition evaluation
# ═══════════════════════════════════════════════════════════════════════

def _resolve_field(profile: dict, field_name: str) -> Any:
    return profile.get(field_name)


def _eval_condition(cond: dict, profile: dict) -> bool:
    field_name = cond.get("field", "")
    op = cond.get("op", "eq")
    expected = cond.get("value")
    raw = _resolve_field(profile, field_name)

    if op == "missing":
        return _is_empty(raw)
    if op == "present":
        return not _is_empty(raw)

    if op == "json_field":
        path = cond.get("path", "")
        parsed = _parse_json_field(raw)
        if isinstance(parsed, dict):
            actual = parsed.get(path)
        else:
            return False
        return _match_value(actual, expected)

    if op == "contains":
        parsed = _parse_json_field(raw)
        if isinstance(parsed, list):
            return any(str(item).lower() == str(expected).lower() for item in parsed)
        if isinstance(parsed, str):
            return str(expected).lower() in parsed.lower()
        return False

    if op == "in":
        if not isinstance(expected, list):
            return False
        raw_str = str(raw).strip() if raw is not None else ""
        return any(raw_str.lower() == str(e).lower() for e in expected)

    if op == "eq":
        return _match_value(raw, expected)
    if op == "ne":
        return not _match_value(raw, expected)

    raw_num = _coerce_number(raw)
    exp_num = _coerce_number(expected)
    if raw_num is None or exp_num is None:
        return False
    if op == "gt":
        return raw_num > exp_num
    if op == "lt":
        return raw_num < exp_num
    if op == "gte":
        return raw_num >= exp_num
    if op == "lte":
        return raw_num <= exp_num

    logger.warning("Unknown operator: %s", op)
    return False


def _match_value(actual: Any, expected: Any) -> bool:
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    if isinstance(expected, bool):
        actual_bool = _coerce_bool(actual)
        if actual_bool is not None:
            return actual_bool == expected
    actual_num = _coerce_number(actual)
    expected_num = _coerce_number(expected)
    if actual_num is not None and expected_num is not None:
        return actual_num == expected_num
    return str(actual).strip().lower() == str(expected).strip().lower()


def _eval_conditions(conditions: dict, profile: dict) -> bool:
    if "all" in conditions:
        return all(_eval_condition(c, profile) for c in conditions["all"])
    if "any" in conditions:
        return any(_eval_condition(c, profile) for c in conditions["any"])
    return _eval_condition(conditions, profile)


# ═══════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════

def evaluate(reconciled_profile: dict, rules_path: str) -> dict:
    """Evaluate all rules against a reconciled profile.

    Returns evaluation with risk_score, decision, explanations, and
    coverage recommendations.
    """
    rules_data = load_rules(rules_path)
    version = rules_data.get("version", "unknown")
    base_score = rules_data.get("base_risk_score", 25)
    rules = rules_data.get("rules", [])
    policy = rules_data.get("decision_policy", {})

    merged = reconciled_profile.get("merged_fields", {})
    conflicts = reconciled_profile.get("conflicts", [])
    coverage_score = reconciled_profile.get("coverage_score", 0.0)

    eval_profile = dict(merged)
    eval_profile["_conflict_count"] = len(conflicts)
    eval_profile["_coverage_score"] = coverage_score
    eval_profile["_conflicts"] = conflicts

    score = float(base_score)
    multiplier = 1.0
    breakdown: list[dict] = []
    fired_ids: list[str] = []
    all_flags: list[str] = []
    all_coverages: list[str] = []
    decline_triggers: list[str] = []
    human_review_triggers: list[str] = []

    for rule in rules:
        rule_id = rule.get("id", "unknown")
        conditions = rule.get("conditions", {})

        if not _eval_conditions(conditions, eval_profile):
            continue

        effects = rule.get("effects", {})
        points = effects.get("risk_points", 0)
        mult = effects.get("risk_multiplier")
        flags = effects.get("flags", [])
        coverages = effects.get("required_coverages", [])
        is_decline = effects.get("decline_trigger", False)
        is_review = effects.get("human_review_trigger", False)

        score += points
        if mult is not None:
            multiplier *= mult

        all_flags.extend(flags)
        all_coverages.extend(coverages)
        fired_ids.append(rule_id)

        if is_decline:
            decline_triggers.append(rule_id)
        if is_review:
            human_review_triggers.append(rule_id)

        breakdown.append({
            "rule_id": rule_id,
            "name": rule.get("name", ""),
            "category": rule.get("category", ""),
            "description": rule.get("description", ""),
            "risk_points": points,
            "flags": flags,
            "required_coverages": coverages,
            "decline_trigger": is_decline,
            "human_review_trigger": is_review,
        })

    score = score * multiplier
    score = max(0, min(100, round(score, 2)))

    all_flags = list(dict.fromkeys(all_flags))
    all_coverages = list(dict.fromkeys(all_coverages))

    decision, reasons = _decide(
        score, all_flags, decline_triggers, human_review_triggers, policy,
        coverage_score,
    )

    logger.info(
        "Rules %s evaluated: %d rules fired, score=%.1f, decision=%s",
        version, len(fired_ids), score, decision,
    )

    # Build coverage recommendation from knowledge base (#14)
    recommended_coverages = _get_coverage_recommendations(merged)

    result = {
        "rules_version": version,
        "risk_score": score,
        "risk_breakdown": breakdown,
        "rules_applied": fired_ids,
        "decision": decision,
        "decision_reasons": reasons,
        "required_coverages": all_coverages,
        "recommended_coverages": recommended_coverages,
        "flags": all_flags,
    }

    # Generate human-readable explanation (#15)
    result["risk_explanation"] = generate_risk_explanation(result)

    # Generate decline explanation with remediation (#16)
    if decision == "decline":
        result["decline_explanation"] = generate_decline_explanation(result, merged)

    return result


def _decide(
    score: float,
    flags: list[str],
    decline_triggers: list[str],
    human_review_triggers: list[str],
    policy: dict,
    coverage_score: float = 1.0,
) -> tuple[str, list[str]]:
    auto_max = policy.get("auto_bind_max_score", 50)
    decline_min = policy.get("decline_min_score", 90)
    blocking_flags = set(policy.get("auto_bind_blocked_by_flags", []))
    decline_flags = set(policy.get("decline_flags", []))
    min_coverage = policy.get("min_coverage_for_auto_bind", 0.0)

    reasons: list[str] = []

    if decline_triggers:
        reasons.append(f"Decline rule(s) triggered: {', '.join(decline_triggers)}")
    if score >= decline_min:
        reasons.append(f"Risk score {score:.0f} exceeds decline threshold ({decline_min})")
    flag_set = set(flags)
    matched_decline_flags = flag_set & decline_flags
    if matched_decline_flags:
        reasons.append(f"Decline flag(s) present: {', '.join(sorted(matched_decline_flags))}")

    if reasons:
        return "decline", reasons

    reasons = []
    if score > auto_max:
        reasons.append(f"Risk score {score:.0f} exceeds auto-bind limit ({auto_max})")
    matched_blockers = flag_set & blocking_flags
    if matched_blockers:
        reasons.append(f"Blocking flag(s): {', '.join(sorted(matched_blockers))}")
    if human_review_triggers:
        reasons.append(f"Human review rule(s): {', '.join(human_review_triggers)}")
    if min_coverage > 0 and coverage_score < min_coverage:
        reasons.append(
            f"Coverage score {coverage_score:.1%} below auto-bind minimum ({min_coverage:.0%})"
        )

    if reasons:
        return "human_review", reasons

    return "auto_bind", [f"Risk score {score:.0f} within auto-bind threshold ({auto_max})"]


# ═══════════════════════════════════════════════════════════════════════
# Coverage recommendation (#14)
# ═══════════════════════════════════════════════════════════════════════

def _get_coverage_recommendations(merged_fields: dict) -> dict[str, Any]:
    """Use knowledge base to get coverage recommendations for the profile."""
    try:
        from knowledge_base.loader import get_coverage_recommendation
        rec = get_coverage_recommendation(merged_fields)
        if rec:
            return {
                "mandatory": rec.get("mandatory", []),
                "recommended": rec.get("recommended", []),
                "optional": rec.get("optional", []),
                "reasoning": rec.get("reasoning", ""),
                "profile_matched": rec.get("id", "unknown"),
            }
    except Exception as e:
        logger.warning("Failed to get coverage recommendation: %s", e)

    return {
        "mandatory": ["cyber", "gl"],
        "recommended": ["tech_eo"],
        "optional": ["d_and_o"],
        "reasoning": "Default recommendation -- no specific profile match.",
        "profile_matched": "default",
    }


# ═══════════════════════════════════════════════════════════════════════
# Human-readable risk explanation (#15)
# ═══════════════════════════════════════════════════════════════════════

def generate_risk_explanation(evaluation: dict) -> str:
    """Generate a plain-English explanation of the risk assessment."""
    score = evaluation.get("risk_score", 0)
    breakdown = evaluation.get("risk_breakdown", [])
    decision = evaluation.get("decision", "unknown")
    rec_coverages = evaluation.get("recommended_coverages", {})

    # Risk tier
    if score <= 30:
        tier = "Low Risk"
    elif score <= 50:
        tier = "Moderate Risk"
    elif score <= 70:
        tier = "Elevated Risk"
    elif score <= 90:
        tier = "High Risk"
    else:
        tier = "Critical Risk"

    # Key factors
    factors = []
    for rule in breakdown:
        pts = rule.get("risk_points", 0)
        if pts > 0:
            factors.append((rule["name"], pts, rule.get("description", "")))
        elif pts < 0:
            factors.append((rule["name"], pts, rule.get("description", "")))

    factors.sort(key=lambda x: abs(x[1]), reverse=True)

    lines = [f"Your company has a risk score of {score:.0f} ({tier})."]

    # Positive risk factors (top 5)
    positive = [f for f in factors if f[1] > 0][:5]
    if positive:
        lines.append("Key factors:")
        for name, pts, desc in positive:
            lines.append(f"  - {desc} (+{pts} points)")

    # Risk reductions
    negative = [f for f in factors if f[1] < 0][:3]
    if negative:
        lines.append("Risk reductions:")
        for name, pts, desc in negative:
            lines.append(f"  - {desc} ({pts} points)")

    # Remediation suggestions
    remediation = _suggest_remediations(evaluation)
    if remediation:
        lines.append("To reduce your risk score, we recommend:")
        for r in remediation[:3]:
            lines.append(f"  - {r}")

    # Coverage recommendations
    if rec_coverages:
        mandatory = rec_coverages.get("mandatory", [])
        recommended = rec_coverages.get("recommended", [])
        if mandatory or recommended:
            coverage_parts = []
            for c in mandatory:
                coverage_parts.append(f"{_coverage_display_name(c)} (mandatory)")
            for c in recommended:
                coverage_parts.append(f"{_coverage_display_name(c)} (recommended)")
            lines.append(f"Recommended coverages: {', '.join(coverage_parts)}.")

    return " ".join(lines) if len(lines) <= 3 else "\n".join(lines)


def _coverage_display_name(code: str) -> str:
    """Convert coverage code to display name."""
    names = {
        "cyber": "Cyber Liability",
        "cyber_liability": "Cyber Liability",
        "tech_eo": "Technology E&O",
        "gl": "General Liability",
        "d_and_o": "Directors & Officers",
        "epli": "Employment Practices",
        "fiduciary": "Fiduciary Liability",
        "media_liability": "Media Liability",
        "ai_liability": "AI Liability",
        "hipaa_compliance": "HIPAA Compliance",
        "financial_crime": "Financial Crime",
        "data_breach": "Data Breach",
    }
    return names.get(code, code.replace("_", " ").title())


def _suggest_remediations(evaluation: dict) -> list[str]:
    """Suggest specific actions to reduce risk score."""
    flags = set(evaluation.get("flags", []))
    suggestions = []

    if "mfa_missing" in flags:
        suggestions.append("Implement MFA for all administrative and production accounts")
    if "encryption_missing" in flags:
        suggestions.append("Enable encryption at rest for all databases and storage systems")
    if "pii_unprotected" in flags:
        suggestions.append("Obtain SOC-2 Type II certification to demonstrate security controls")
    if "no_security_scanning" in flags:
        suggestions.append("Implement automated security scanning (SAST/DAST) in your CI/CD pipeline")
    if "no_ci_cd" in flags:
        suggestions.append("Set up CI/CD pipeline with automated testing and security checks")
    if "qualified_opinion" in flags:
        suggestions.append("Remediate all SOC-2 exceptions and obtain an unqualified opinion")
    if "many_exceptions" in flags:
        suggestions.append("Address all SOC-2 control exceptions before renewal")
    if "low_eng_maturity" in flags:
        suggestions.append("Invest in engineering practices: security policy, CI/CD, code review")
    if "declining_activity" in flags:
        suggestions.append("Address declining engineering activity -- ensure adequate team resourcing")
    if "copyleft_risk" in flags:
        suggestions.append("Review GPL/AGPL dependencies for license compliance in commercial use")

    return suggestions


# ═══════════════════════════════════════════════════════════════════════
# Decline explanation with remediation path (#16)
# ═══════════════════════════════════════════════════════════════════════

def generate_decline_explanation(evaluation: dict, merged_fields: dict) -> str:
    """Generate a specific explanation for decline with remediation path."""
    reasons = evaluation.get("decision_reasons", [])
    flags = set(evaluation.get("flags", []))
    score = evaluation.get("risk_score", 0)

    lines = [
        f"Your submission was declined (risk score: {score:.0f}).",
        "",
        "Decline reasons:",
    ]
    for r in reasons:
        lines.append(f"  - {r}")

    lines.append("")
    lines.append("To become eligible for coverage, the following changes are required:")

    steps = []
    if "qualified_phi" in flags:
        steps.append(
            "Remediate all SOC-2 exceptions and obtain an unqualified opinion. "
            "A qualified SOC-2 combined with PHI handling represents unacceptable risk."
        )
    if "qualified_opinion" in flags and "qualified_phi" not in flags:
        steps.append(
            "Obtain an unqualified SOC-2 opinion by addressing all material control failures."
        )
    if "mfa_missing" in flags:
        steps.append("Implement MFA for all administrative accounts and production systems.")
    if "encryption_missing" in flags:
        steps.append("Enable encryption at rest and in transit for all sensitive data stores.")
    if "pii_unprotected" in flags:
        steps.append(
            "Complete SOC-2 Type II audit to demonstrate adequate security controls for PII handling."
        )
    if "payments_unprotected" in flags:
        steps.append(
            "Obtain PCI-DSS compliance or SOC-2 certification before handling payment data."
        )

    if not steps:
        steps.append("Reduce your overall risk profile to bring the risk score below 90.")
        steps.append("Consider obtaining SOC-2 certification and implementing security best practices.")

    for i, step in enumerate(steps, 1):
        lines.append(f"  {i}. {step}")

    lines.append("")
    lines.append(
        "After these changes, resubmit with updated documentation (SOC-2 report, "
        "security questionnaire, or updated pitch deck)."
    )

    return "\n".join(lines)
