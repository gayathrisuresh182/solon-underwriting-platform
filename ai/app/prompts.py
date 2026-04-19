"""Prompts and schemas for pitch deck extraction (v2).

Changes from v1:
- Structured output JSON schema for guaranteed valid responses
- Few-shot examples from real Coinbase extraction
- Dual-input instructions (text + image)
"""

PROMPT_VERSION = "v2"

RISK_FIELDS = [
    "company_name", "industry", "stage", "headcount", "revenue_range",
    "handles_pii", "handles_payments", "uses_ai_in_product",
    "b2b_or_b2c", "customer_type", "geographic_scope", "has_soc2",
    "tech_stack", "product_description", "key_risks",
]

# ═══════════════════════════════════════════════════════════════════════
# Structured output schema — guarantees valid JSON from GPT-4o
# ═══════════════════════════════════════════════════════════════════════

_nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_nullable_bool = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}
_nullable_int = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
_nullable_float = {"anyOf": [{"type": "number"}, {"type": "null"}]}
_nullable_str_array = {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]}

PAGE_EXTRACTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "page_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "properties": {
                        "company_name": _nullable_string,
                        "industry": _nullable_string,
                        "stage": _nullable_string,
                        "headcount": _nullable_int,
                        "revenue_range": _nullable_string,
                        "handles_pii": _nullable_bool,
                        "handles_payments": _nullable_bool,
                        "uses_ai_in_product": _nullable_bool,
                        "b2b_or_b2c": _nullable_string,
                        "customer_type": _nullable_string,
                        "geographic_scope": _nullable_string,
                        "has_soc2": _nullable_bool,
                        "tech_stack": _nullable_str_array,
                        "product_description": _nullable_string,
                        "key_risks": _nullable_str_array,
                    },
                    "required": [
                        "company_name", "industry", "stage", "headcount",
                        "revenue_range", "handles_pii", "handles_payments",
                        "uses_ai_in_product", "b2b_or_b2c", "customer_type",
                        "geographic_scope", "has_soc2", "tech_stack",
                        "product_description", "key_risks",
                    ],
                    "additionalProperties": False,
                },
                "confidence": {
                    "type": "object",
                    "properties": {
                        "company_name": _nullable_float,
                        "industry": _nullable_float,
                        "stage": _nullable_float,
                        "headcount": _nullable_float,
                        "revenue_range": _nullable_float,
                        "handles_pii": _nullable_float,
                        "handles_payments": _nullable_float,
                        "uses_ai_in_product": _nullable_float,
                        "b2b_or_b2c": _nullable_float,
                        "customer_type": _nullable_float,
                        "geographic_scope": _nullable_float,
                        "has_soc2": _nullable_float,
                        "tech_stack": _nullable_float,
                        "product_description": _nullable_float,
                        "key_risks": _nullable_float,
                    },
                    "required": [
                        "company_name", "industry", "stage", "headcount",
                        "revenue_range", "handles_pii", "handles_payments",
                        "uses_ai_in_product", "b2b_or_b2c", "customer_type",
                        "geographic_scope", "has_soc2", "tech_stack",
                        "product_description", "key_risks",
                    ],
                    "additionalProperties": False,
                },
                "citations": {
                    "type": "object",
                    "properties": {
                        "company_name": _nullable_string,
                        "industry": _nullable_string,
                        "stage": _nullable_string,
                        "headcount": _nullable_string,
                        "revenue_range": _nullable_string,
                        "handles_pii": _nullable_string,
                        "handles_payments": _nullable_string,
                        "uses_ai_in_product": _nullable_string,
                        "b2b_or_b2c": _nullable_string,
                        "customer_type": _nullable_string,
                        "geographic_scope": _nullable_string,
                        "has_soc2": _nullable_string,
                        "tech_stack": _nullable_string,
                        "product_description": _nullable_string,
                        "key_risks": _nullable_string,
                    },
                    "required": [
                        "company_name", "industry", "stage", "headcount",
                        "revenue_range", "handles_pii", "handles_payments",
                        "uses_ai_in_product", "b2b_or_b2c", "customer_type",
                        "geographic_scope", "has_soc2", "tech_stack",
                        "product_description", "key_risks",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": ["fields", "confidence", "citations"],
            "additionalProperties": False,
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════
# System prompt
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are an expert insurance underwriter AI specializing in startup risk assessment.
You analyze pitch deck pages using BOTH the extracted text content AND the page image.
Use the text for reliable content reading and the image for layout/visual context.

For each field you extract, assign a confidence score between 0.0 and 1.0:
- 0.9-1.0: clearly stated on the slide with no ambiguity
- 0.6-0.8: inferred from context or partially stated
- below 0.6: speculative or only weakly supported

Set fields to null when no evidence exists on the page.
Set the corresponding confidence and citation to null for null fields."""

# ═══════════════════════════════════════════════════════════════════════
# Extraction prompt with few-shot examples
# ═══════════════════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """\
Analyze this pitch deck page (page {page_number}) and extract risk-relevant fields.

You receive BOTH the page text (from OCR) and the page image. Use text for accurate \
reading and the image for layout context (charts, logos, formatting).

**Page text content:**
{page_text}

**Fields to extract** (set to null if not found on this page):

Company Info: company_name, industry, stage (pre-seed/seed/series-a/series-b/growth), \
headcount (integer), geographic_scope
Business Model: b2b_or_b2c (B2B/B2C/Both), customer_type (enterprise/smb/consumer), \
revenue_range ($0/<$1M/$1-5M/$5-10M/$10M+), uses_ai_in_product (boolean)
Risk Surface: handles_pii (boolean), handles_payments (boolean), has_soc2 (boolean)
Product & Tech: tech_stack (string array), product_description (one-line summary)
Risk Assessment: key_risks (string array of risk factors from this page)

**Example 1** — A fintech title slide:
{{"fields": {{"company_name": "PayFlow", "industry": "fintech", "stage": null, \
"headcount": null, "revenue_range": null, "handles_pii": null, "handles_payments": true, \
"uses_ai_in_product": null, "b2b_or_b2c": "B2B", "customer_type": null, \
"geographic_scope": null, "has_soc2": null, "tech_stack": null, \
"product_description": "Payment orchestration platform for SaaS companies", \
"key_risks": null}}, \
"confidence": {{"company_name": 0.95, "industry": 0.9, "stage": null, "headcount": null, \
"revenue_range": null, "handles_pii": null, "handles_payments": 0.85, \
"uses_ai_in_product": null, "b2b_or_b2c": 0.8, "customer_type": null, \
"geographic_scope": null, "has_soc2": null, "tech_stack": null, \
"product_description": 0.9, "key_risks": null}}, \
"citations": {{"company_name": "Logo and title text", "industry": "Tagline mentions payments", \
"stage": null, "headcount": null, "revenue_range": null, "handles_pii": null, \
"handles_payments": "Product described as payment platform", \
"uses_ai_in_product": null, "b2b_or_b2c": "Says 'for SaaS companies'", \
"customer_type": null, "geographic_scope": null, "has_soc2": null, \
"tech_stack": null, "product_description": "Subtitle on slide", "key_risks": null}}}}

**Example 2** — A traction/metrics slide:
{{"fields": {{"company_name": null, "industry": null, "stage": "series-a", \
"headcount": 45, "revenue_range": "$1-5M", "handles_pii": null, "handles_payments": null, \
"uses_ai_in_product": null, "b2b_or_b2c": null, "customer_type": "enterprise", \
"geographic_scope": "US-only", "has_soc2": true, "tech_stack": null, \
"product_description": null, \
"key_risks": ["Concentration risk: top 3 clients = 60% revenue"]}}, \
"confidence": {{"company_name": null, "industry": null, "stage": 0.85, \
"headcount": 0.9, "revenue_range": 0.8, "handles_pii": null, "handles_payments": null, \
"uses_ai_in_product": null, "b2b_or_b2c": null, "customer_type": 0.7, \
"geographic_scope": 0.75, "has_soc2": 0.6, "tech_stack": null, \
"product_description": null, "key_risks": 0.7}}, \
"citations": {{"company_name": null, "industry": null, "stage": "Funding round mentioned", \
"headcount": "Team size chart shows 45", "revenue_range": "ARR bar chart ~$2.3M", \
"handles_pii": null, "handles_payments": null, "uses_ai_in_product": null, \
"b2b_or_b2c": null, "customer_type": "Enterprise logos shown", \
"geographic_scope": "Map shows US offices only", "has_soc2": "SOC 2 badge in footer", \
"tech_stack": null, "product_description": null, \
"key_risks": "Revenue concentration visible in client breakdown"}}}}

Now extract from page {page_number}. Return the structured JSON with all fields \
(null for fields not found)."""
