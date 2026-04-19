-- Human correction feedback storage (#12)
-- Stores human overrides of reconciled fields for future model improvement.

CREATE TABLE IF NOT EXISTS correction_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    original_value TEXT,
    original_source VARCHAR(30),
    corrected_value TEXT NOT NULL,
    corrected_by VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_correction_feedback_submission
    ON correction_feedback(submission_id);
CREATE INDEX IF NOT EXISTS idx_correction_feedback_field
    ON correction_feedback(field_name);
