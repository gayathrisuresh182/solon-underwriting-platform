-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Submissions: the top-level entity (replaces direct extraction)
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(255),
    status VARCHAR(30) DEFAULT 'created',
    -- status: created → extracting → extracted → reconciling → reconciled →
    --         scoring → scored → quoted → bound
    sources_attached JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Source documents attached to a submission
CREATE TABLE submission_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    source_type VARCHAR(30) NOT NULL,  -- 'pitch_deck', 'soc2_report', 'github_repo'
    source_ref VARCHAR(500),           -- filename or URL
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    extraction_result JSONB,
    confidence_scores JSONB,
    citations JSONB,
    metadata JSONB,                    -- cost, timing, model used, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Reconciled profile (merged from all sources)
CREATE TABLE reconciled_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    merged_fields JSONB NOT NULL,
    field_sources JSONB NOT NULL,       -- which source each field came from
    conflicts JSONB DEFAULT '[]',       -- list of field conflicts between sources
    coverage_score DECIMAL(3,2),        -- % of fields populated
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rules engine evaluation results
CREATE TABLE rule_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    rules_version VARCHAR(20) NOT NULL,
    rules_applied JSONB NOT NULL,       -- which rules fired and their effects
    risk_score DECIMAL(5,2) NOT NULL,
    risk_breakdown JSONB NOT NULL,      -- detailed score breakdown
    decision VARCHAR(20) NOT NULL,      -- auto_bind, human_review, decline
    decision_reasons JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit log (event sourcing)
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    actor VARCHAR(50) NOT NULL DEFAULT 'system',
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_events_submission ON audit_events(submission_id, created_at);
CREATE INDEX idx_submission_sources_submission ON submission_sources(submission_id);

-- SOC-2 document chunks for vector search (used during knowledge-augmented extraction)
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES submission_sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    chunk_type VARCHAR(30),            -- 'narrative', 'control_table', 'findings', 'opinion'
    embedding vector(1536),            -- OpenAI text-embedding-3-small dimension
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
