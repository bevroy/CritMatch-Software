CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ehr_user_id TEXT,
    name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'research_user',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE studies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    owner_user_id UUID REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE criteria_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    version INT NOT NULL,
    logic_json JSONB NOT NULL,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (study_id, version)
);

CREATE TABLE terminology_expansions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    criteria_set_id UUID NOT NULL REFERENCES criteria_sets(id) ON DELETE CASCADE,
    source_term TEXT NOT NULL,
    normalized_term TEXT,
    expansion_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE query_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    criteria_set_id UUID NOT NULL REFERENCES criteria_sets(id) ON DELETE CASCADE,
    run_by UUID REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'queued',
    result_count INT,
    execution_ms INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE query_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_run_id UUID NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL,
    mrn_hash TEXT,
    matched_rules_json JSONB,
    primary_match_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
