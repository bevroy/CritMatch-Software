CREATE TABLE study_collaborators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (study_id, user_id)
);
CREATE INDEX ix_study_collaborators_user_id ON study_collaborators(user_id);
