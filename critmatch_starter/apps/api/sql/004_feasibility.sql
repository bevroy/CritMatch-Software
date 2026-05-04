CREATE TABLE IF NOT EXISTS feasibility_questionnaires (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID REFERENCES studies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_feasibility_questionnaires_study_id ON feasibility_questionnaires(study_id);
CREATE INDEX IF NOT EXISTS ix_feasibility_questionnaires_created_by ON feasibility_questionnaires(created_by);

CREATE TABLE IF NOT EXISTS feasibility_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    questionnaire_id UUID NOT NULL REFERENCES feasibility_questionnaires(id) ON DELETE CASCADE,
    position INT NOT NULL DEFAULT 0,
    text TEXT NOT NULL,
    logic_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_feasibility_questions_questionnaire_id ON feasibility_questions(questionnaire_id);

CREATE TABLE IF NOT EXISTS feasibility_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    questionnaire_id UUID NOT NULL REFERENCES feasibility_questionnaires(id) ON DELETE CASCADE,
    run_by UUID REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'queued',
    total_patients INT,
    execution_ms INT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_feasibility_runs_questionnaire_id ON feasibility_runs(questionnaire_id);
CREATE INDEX IF NOT EXISTS ix_feasibility_runs_status ON feasibility_runs(status);

CREATE TABLE IF NOT EXISTS feasibility_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES feasibility_runs(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES feasibility_questions(id) ON DELETE CASCADE,
    count INT NOT NULL DEFAULT 0,
    detail_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_feasibility_results_run_id ON feasibility_results(run_id);
