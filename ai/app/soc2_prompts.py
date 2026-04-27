"""Prompts and schemas for SOC-2 report extraction (v3 — text-only, Docling-powered).

v3 changes from v2:
- All prompts are text-only (no Vision/image references)
- CONTROL_TABLE_PROMPT/SCHEMA removed (tables extracted deterministically via Docling DataFrames)
- CLASSIFICATION_PROMPT/SCHEMA removed (sections classified by heading keywords)
- Remaining prompts updated to accept {section_text} instead of page images
"""

SOC2_SYSTEM_PROMPT = """\
You are an expert insurance underwriter AI analyzing a SOC-2 Type II audit report.
Your job is to extract structured security posture data that determines cyber insurance risk.

Key underwriting principles:
- Exceptions to controls are the most important signals — each one increases risk.
- A qualified opinion is a major red flag; unqualified is positive.
- Security practices (MFA, encryption, incident response) directly affect premium pricing.
- You must capture the EXACT criteria IDs (CC6.1, CC7.2, etc.) for every finding.

You will receive text extracted from specific sections of the report. Extract the requested \
fields accurately based on the text content provided.

Always respond with valid JSON matching the requested schema."""

# ═══════════════════════════════════════════════════════════════════════
# Structured output schemas
# ═══════════════════════════════════════════════════════════════════════

_nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_nullable_float = {"anyOf": [{"type": "number"}, {"type": "null"}]}

OPINION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "opinion_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "audit_opinion": {"type": "string"},
                "company_name": _nullable_string,
                "audit_period": _nullable_string,
                "trust_services_categories": {
                    "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]
                },
                "auditor_name": _nullable_string,
                "confidence": {
                    "type": "object",
                    "properties": {
                        "audit_opinion": _nullable_float,
                        "company_name": _nullable_float,
                        "audit_period": _nullable_float,
                        "trust_services_categories": _nullable_float,
                        "auditor_name": _nullable_float,
                    },
                    "required": ["audit_opinion", "company_name", "audit_period",
                                 "trust_services_categories", "auditor_name"],
                    "additionalProperties": False,
                },
                "citations": {
                    "type": "object",
                    "properties": {
                        "audit_opinion": _nullable_string,
                        "company_name": _nullable_string,
                        "audit_period": _nullable_string,
                        "trust_services_categories": _nullable_string,
                        "auditor_name": _nullable_string,
                    },
                    "required": ["audit_opinion", "company_name", "audit_period",
                                 "trust_services_categories", "auditor_name"],
                    "additionalProperties": False,
                },
            },
            "required": ["audit_opinion", "company_name", "audit_period",
                         "trust_services_categories", "auditor_name",
                         "confidence", "citations"],
            "additionalProperties": False,
        },
    },
}

SYSTEM_DESCRIPTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "system_description_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "properties": {
                        "industry": _nullable_string,
                        "infrastructure_provider": _nullable_string,
                        "tech_stack": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
                        "data_types_handled": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
                        "headcount": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                        "security_practices": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
                        "compliance_frameworks": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
                        "product_description": _nullable_string,
                    },
                    "required": ["industry", "infrastructure_provider", "tech_stack",
                                 "data_types_handled", "headcount", "security_practices",
                                 "compliance_frameworks", "product_description"],
                    "additionalProperties": False,
                },
                "confidence": {
                    "type": "object",
                    "properties": {
                        "industry": _nullable_float,
                        "infrastructure_provider": _nullable_float,
                        "tech_stack": _nullable_float,
                        "data_types_handled": _nullable_float,
                        "headcount": _nullable_float,
                        "security_practices": _nullable_float,
                        "compliance_frameworks": _nullable_float,
                        "product_description": _nullable_float,
                    },
                    "required": ["industry", "infrastructure_provider", "tech_stack",
                                 "data_types_handled", "headcount", "security_practices",
                                 "compliance_frameworks", "product_description"],
                    "additionalProperties": False,
                },
                "citations": {
                    "type": "object",
                    "properties": {
                        "industry": _nullable_string,
                        "infrastructure_provider": _nullable_string,
                        "tech_stack": _nullable_string,
                        "data_types_handled": _nullable_string,
                        "headcount": _nullable_string,
                        "security_practices": _nullable_string,
                        "compliance_frameworks": _nullable_string,
                        "product_description": _nullable_string,
                    },
                    "required": ["industry", "infrastructure_provider", "tech_stack",
                                 "data_types_handled", "headcount", "security_practices",
                                 "compliance_frameworks", "product_description"],
                    "additionalProperties": False,
                },
            },
            "required": ["fields", "confidence", "citations"],
            "additionalProperties": False,
        },
    },
}

_control_entry = {
    "type": "object",
    "properties": {
        "criteria_id": {"type": "string"},
        "category": _nullable_string,
        "control_description": _nullable_string,
        "test_performed": _nullable_string,
        "passed": {"type": "boolean"},
        "exception_description": _nullable_string,
    },
    "required": ["criteria_id", "category", "control_description",
                 "test_performed", "passed", "exception_description"],
    "additionalProperties": False,
}

CONTROL_TABLE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "control_table_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "controls": {"type": "array", "items": _control_entry},
            },
            "required": ["controls"],
            "additionalProperties": False,
        },
    },
}

_finding_entry = {
    "type": "object",
    "properties": {
        "criteria_id": {"type": "string"},
        "finding_title": _nullable_string,
        "condition": _nullable_string,
        "risk_effect": _nullable_string,
        "management_response": _nullable_string,
        "compensating_control": _nullable_string,
        "severity": {"type": "string"},
    },
    "required": ["criteria_id", "finding_title", "condition", "risk_effect",
                 "management_response", "compensating_control", "severity"],
    "additionalProperties": False,
}

FINDINGS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "findings_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "findings": {"type": "array", "items": _finding_entry},
            },
            "required": ["findings"],
            "additionalProperties": False,
        },
    },
}

TESTING_SUMMARY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "testing_summary_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "total_controls_tested": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "controls_passed": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "controls_with_exceptions": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "pass_rate": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                "confidence": {
                    "type": "object",
                    "properties": {
                        "total_controls_tested": _nullable_float,
                    },
                    "required": ["total_controls_tested"],
                    "additionalProperties": False,
                },
                "citations": {
                    "type": "object",
                    "properties": {
                        "total_controls_tested": _nullable_string,
                    },
                    "required": ["total_controls_tested"],
                    "additionalProperties": False,
                },
            },
            "required": ["total_controls_tested", "controls_passed",
                         "controls_with_exceptions", "pass_rate",
                         "confidence", "citations"],
            "additionalProperties": False,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Text-only prompts (no Vision references)
# ═══════════════════════════════════════════════════════════════════════

OPINION_PROMPT = """\
Below is the text from the Independent Auditor's Report section of a SOC-2 Type II report.

{domain_context}

**Section text:**
{section_text}

Extract the following from this text:

1. **audit_opinion**: Is this "unqualified" (clean) or "qualified" (has reservations)?
   Look for phrases like "in our opinion, in all material respects" (unqualified)
   vs "except for the matters described" (qualified).
2. **company_name**: The company being audited.
3. **audit_period**: The date range of the audit (e.g. "January 1, 2025 - December 31, 2025").
4. **trust_services_categories**: Which categories are in scope (Security, Availability,
   Confidentiality, Processing Integrity, Privacy)?
5. **auditor_name**: Name of the audit firm."""

SYSTEM_DESCRIPTION_PROMPT = """\
Below is the text from the System Description section of a SOC-2 Type II report.

{domain_context}

**Section text:**
{section_text}

Extract any of these fields you can identify (null if not found):

- **industry**: Primary industry/vertical of the company
- **infrastructure_provider**: Cloud provider(s) — AWS, GCP, Azure, etc.
- **tech_stack**: Technologies mentioned (languages, frameworks, databases) as an array
- **data_types_handled**: Types of sensitive data — PII, PHI, PCI, financial, etc.
- **headcount**: Number of employees if mentioned
- **security_practices**: Security measures described (array of short descriptions)
- **compliance_frameworks**: Other compliance frameworks mentioned (HIPAA, ISO 27001, etc.)
- **product_description**: What the company does (one sentence)"""

FINDINGS_PROMPT = """\
Below is the text from a Findings and Observations section of a SOC-2 Type II report \
(exceptions found during audit testing).

{domain_context}

**Section text:**
{section_text}

Extract EVERY finding in this text:

- **criteria_id**: The criteria code the finding relates to (CC6.1, CC7.4, etc.)
- **finding_title**: Short title of the finding
- **condition**: What was wrong — the actual exception
- **risk_effect**: The risk or impact described
- **management_response**: Management's corrective action plan
- **compensating_control**: Any compensating control mentioned (null if none)
- **severity**: Your assessment — "critical", "high", "medium", or "low"

CRITICAL: Capture ALL findings. Every exception matters for underwriting."""

CONTROL_TABLE_PROMPT = """\
Below is the text from a Control Activities / Tests of Operating Effectiveness section \
of a SOC-2 Type II report. This section contains control test results.

{domain_context}

**Section text:**
{section_text}

Extract each control tested on this section as a separate entry:

- **criteria_id**: The criteria code (CC6.1, CC7.2, A1.1, etc.)
- **category**: The control category name (null if not stated)
- **control_description**: Brief description of the control activity
- **test_performed**: Brief description of the test
- **passed**: true if "Pass" / "No exceptions noted", false if "Fail" or exceptions exist
- **exception_description**: If failed, the exact exception text. null if passed.

CRITICAL: Capture ALL controls in the text. Do not skip any, even if they passed."""

TESTING_SUMMARY_PROMPT = """\
Below is the text from a Summary of Testing Results section of a SOC-2 Type II report.

{domain_context}

**Section text:**
{section_text}

Extract:
- **total_controls_tested**: integer
- **controls_passed**: integer
- **controls_with_exceptions**: integer
- **pass_rate**: percentage as a decimal (e.g. 0.909 for 90.9%)"""
