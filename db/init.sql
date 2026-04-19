CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE risk_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    stage VARCHAR(50),
    headcount INTEGER,
    revenue_range VARCHAR(50),
    handles_pii BOOLEAN,
    handles_payments BOOLEAN,
    uses_ai_in_product BOOLEAN,
    b2b_or_b2c VARCHAR(10),
    geographic_scope VARCHAR(100),
    has_soc2 BOOLEAN,
    risk_score DECIMAL(5,2),
    overall_confidence DECIMAL(3,2),
    extracted_fields JSONB NOT NULL,
    confidence_scores JSONB NOT NULL,
    source_citations JSONB NOT NULL,
    source_filename VARCHAR(255),
    extraction_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE field_overrides (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    risk_profile_id UUID REFERENCES risk_profiles(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    original_value TEXT,
    override_value TEXT NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
