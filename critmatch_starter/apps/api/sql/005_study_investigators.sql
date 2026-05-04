CREATE TABLE IF NOT EXISTS study_investigators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    practitioner_id TEXT NOT NULL,
    name TEXT,
    npi TEXT,
    role TEXT NOT NULL DEFAULT 'sub_investigator',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (study_id, practitioner_id)
);
CREATE INDEX IF NOT EXISTS ix_study_investigators_study_id ON study_investigators(study_id);
