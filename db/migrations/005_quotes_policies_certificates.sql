-- Quotes, policies, and certificates for the bind flow

CREATE TABLE IF NOT EXISTS quotes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    quote_number VARCHAR(50) UNIQUE NOT NULL,
    coverages JSONB NOT NULL,
    total_annual_premium DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    valid_until TIMESTAMP WITH TIME ZONE,
    pricing_version VARCHAR(10) DEFAULT 'v1',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id UUID REFERENCES quotes(id),
    submission_id UUID REFERENCES submissions(id) ON DELETE CASCADE,
    policy_number VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    effective_date DATE NOT NULL,
    expiration_date DATE NOT NULL,
    total_premium DECIMAL(10,2) NOT NULL,
    coverages JSONB NOT NULL,
    bound_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS certificates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_id UUID REFERENCES policies(id) ON DELETE CASCADE,
    certificate_number VARCHAR(50) UNIQUE NOT NULL,
    holder_name VARCHAR(255) NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
