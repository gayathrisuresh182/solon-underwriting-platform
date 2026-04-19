RISK_FIELDS = [
    "company_name",
    "industry",
    "stage",               # pre-seed, seed, series-a, series-b, growth
    "headcount",
    "revenue_range",       # $0, <$1M, $1-5M, $5-10M, $10M+
    "handles_pii",         # boolean
    "handles_payments",    # boolean
    "uses_ai_in_product",  # boolean
    "b2b_or_b2c",
    "customer_type",       # enterprise, smb, consumer
    "geographic_scope",    # US-only, international
    "has_soc2",
    "tech_stack",          # list of technologies mentioned
    "product_description", # one-line summary
    "key_risks",           # list of identified risk factors
]

SYSTEM_PROMPT = """You are an expert insurance underwriter AI specializing in startup risk assessment.
You analyze pitch deck page images and extract structured risk-relevant fields.

For each field you extract, assign a confidence score between 0.0 and 1.0:
- 0.9-1.0: clearly stated on the slide with no ambiguity
- 0.6-0.8: inferred from context or partially stated
- below 0.6: speculative or only weakly supported

Always respond with valid JSON matching the requested schema. Never include markdown fences or commentary outside the JSON."""

EXTRACTION_PROMPT = """Analyze this pitch deck page (page {page_number}) and extract any of these risk-relevant fields you can identify:

**Company Info**
- company_name: Legal or operating name of the company
- industry: Primary industry or vertical (e.g. "fintech", "healthtech", "cybersecurity")
- stage: Company stage — one of: "pre-seed", "seed", "series-a", "series-b", "growth"
- headcount: Number of employees as an integer
- geographic_scope: Where they operate — e.g. "US-only", "international", "EU + US"

**Business Model**
- b2b_or_b2c: Either "B2B", "B2C", or "Both"
- customer_type: Primary customer segment — "enterprise", "smb", or "consumer"
- revenue_range: Revenue bracket — "$0", "<$1M", "$1-5M", "$5-10M", or "$10M+"
- uses_ai_in_product: Whether AI/ML is core to their product (true or false)

**Risk Surface**
- handles_pii: Whether the product handles personally identifiable information (true or false)
- handles_payments: Whether the product processes payments (true or false)
- has_soc2: Whether they mention SOC 2 or similar compliance certification (true or false)

**Product & Technology**
- tech_stack: List of technologies, frameworks, or infrastructure mentioned (as a JSON array of strings)
- product_description: A one-line summary of what the product does

**Risk Assessment**
- key_risks: List of identified risk factors from this page (as a JSON array of strings)

Return a JSON object with exactly three top-level keys:
{{
  "fields": {{
    "field_name": "extracted value or null if not found on this page"
  }},
  "confidence": {{
    "field_name": 0.0 to 1.0
  }},
  "citations": {{
    "field_name": "brief quote or description of where on the page this was found"
  }}
}}

Rules:
- Only include fields you can actually extract from THIS page. Omit fields with no evidence.
- For boolean fields, use true/false (not strings).
- For tech_stack and key_risks, return JSON arrays of strings.
- For headcount, return an integer.
- If a field is partially visible or ambiguous, include it with a lower confidence score."""
