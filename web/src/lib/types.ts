export type ConfidenceLevel = "high" | "medium" | "low";

export interface RiskProfile {
  id: string;
  company_name: string;
  industry: string | null;
  stage: string | null;
  headcount: number | null;
  revenue_range: string | null;
  handles_pii: boolean | null;
  handles_payments: boolean | null;
  uses_ai_in_product: boolean | null;
  b2b_or_b2c: string | null;
  geographic_scope: string | null;
  has_soc2: boolean | null;
  risk_score: number | null;
  overall_confidence: number | null;
  extracted_fields: Record<string, string>;
  confidence_scores: Record<string, ConfidenceLevel>;
  source_citations: Record<string, string>;
  source_filename: string | null;
  extraction_time_ms: number | null;
  created_at: string;
  overrides?: FieldOverride[];
}

export interface FieldOverride {
  id: string;
  risk_profile_id: string;
  field_name: string;
  original_value: string | null;
  override_value: string;
  reason: string | null;
  created_at: string;
}

export interface AIExtractionResult {
  company_name: string;
  industry: string | null;
  stage: string | null;
  headcount: number | null;
  revenue_range: string | null;
  handles_pii: boolean | null;
  handles_payments: boolean | null;
  uses_ai_in_product: boolean | null;
  b2b_or_b2c: string | null;
  geographic_scope: string | null;
  has_soc2: boolean | null;
  risk_score: number;
  overall_confidence: number;
  extracted_fields: Record<string, string>;
  confidence_scores: Record<string, ConfidenceLevel>;
  source_citations: Record<string, string>;
  extraction_time_ms: number;
}

export interface DisplayField {
  field_name: string;
  field_value: string;
  confidence: ConfidenceLevel;
  confidence_numeric: number;
  source: string;
  category: string;
}

/** Maps confidence level labels to representative numeric values for display */
export function confidenceToNumeric(level: ConfidenceLevel): number {
  switch (level) {
    case "high":
      return 0.9;
    case "medium":
      return 0.65;
    case "low":
      return 0.3;
  }
}

export const FIELD_CATEGORIES: Record<
  string,
  { label: string; fields: string[] }
> = {
  company_info: {
    label: "Company Info",
    fields: [
      "company_name",
      "industry",
      "stage",
      "headcount",
      "geographic_scope",
    ],
  },
  business_model: {
    label: "Business Model",
    fields: ["b2b_or_b2c", "customer_type", "revenue_range", "uses_ai_in_product"],
  },
  risk_surface: {
    label: "Risk Surface",
    fields: ["handles_pii", "handles_payments", "has_soc2"],
  },
  product_tech: {
    label: "Product & Technology",
    fields: ["product_description", "tech_stack"],
  },
  risk_assessment: {
    label: "Risk Assessment",
    fields: ["key_risks"],
  },
};

export const FIELD_LABELS: Record<string, string> = {
  company_name: "Company Name",
  industry: "Industry",
  stage: "Stage",
  headcount: "Headcount",
  geographic_scope: "Geographic Scope",
  b2b_or_b2c: "B2B or B2C",
  customer_type: "Customer Type",
  revenue_range: "Revenue Range",
  uses_ai_in_product: "Uses AI in Product",
  handles_pii: "Handles PII",
  handles_payments: "Handles Payments",
  has_soc2: "Has SOC 2",
  product_description: "Product Description",
  tech_stack: "Tech Stack",
  key_risks: "Key Risks",
};
