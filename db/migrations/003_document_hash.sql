-- Add document_hash column for extraction caching (#7)
ALTER TABLE risk_profiles ADD COLUMN IF NOT EXISTS document_hash VARCHAR(64);
CREATE INDEX IF NOT EXISTS idx_risk_profiles_document_hash ON risk_profiles(document_hash);

-- Add document_hash to submission_sources for cross-source dedup
ALTER TABLE submission_sources ADD COLUMN IF NOT EXISTS document_hash VARCHAR(64);
CREATE INDEX IF NOT EXISTS idx_submission_sources_document_hash ON submission_sources(document_hash);
