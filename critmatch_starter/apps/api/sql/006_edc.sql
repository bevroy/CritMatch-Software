-- EDC module tables
-- Mirrors alembic/versions/0006_edc.py for direct psql application.

CREATE TABLE IF NOT EXISTS edc_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_edc_forms_study_id ON edc_forms(study_id);

CREATE TABLE IF NOT EXISTS edc_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID NOT NULL REFERENCES edc_forms(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    key TEXT NOT NULL,
    label TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'string',
    required BOOLEAN NOT NULL DEFAULT false,
    options_json JSONB,
    fhir_mapping_json JSONB,
    validation_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_edc_fields_form_id ON edc_fields(form_id);

CREATE TABLE IF NOT EXISTS study_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'screening',
    source TEXT NOT NULL DEFAULT 'manual',
    source_run_id UUID REFERENCES query_runs(id) ON DELETE SET NULL,
    enrolled_at TIMESTAMP,
    enrolled_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_study_participants_subject UNIQUE (study_id, subject_id)
);
CREATE INDEX IF NOT EXISTS ix_study_participants_study_id ON study_participants(study_id);
CREATE INDEX IF NOT EXISTS ix_study_participants_patient_id ON study_participants(patient_id);

CREATE TABLE IF NOT EXISTS edc_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID NOT NULL REFERENCES edc_forms(id) ON DELETE CASCADE,
    participant_id UUID NOT NULL REFERENCES study_participants(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_by UUID REFERENCES users(id),
    completed_at TIMESTAMP,
    locked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_edc_entries_form_id ON edc_entries(form_id);
CREATE INDEX IF NOT EXISTS ix_edc_entries_participant_id ON edc_entries(participant_id);

CREATE TABLE IF NOT EXISTS edc_entry_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id UUID NOT NULL REFERENCES edc_entries(id) ON DELETE CASCADE,
    field_id UUID NOT NULL REFERENCES edc_fields(id) ON DELETE CASCADE,
    value_json JSONB,
    source TEXT NOT NULL DEFAULT 'manual',
    fhir_source_ref TEXT,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_edc_entry_fields_entry_field UNIQUE (entry_id, field_id)
);

CREATE TABLE IF NOT EXISTS edc_entry_field_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_field_id UUID NOT NULL REFERENCES edc_entry_fields(id) ON DELETE CASCADE,
    old_value_json JSONB,
    new_value_json JSONB,
    old_source TEXT,
    new_source TEXT,
    changed_by UUID REFERENCES users(id),
    reason TEXT,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_edc_entry_field_history_entry_field_id ON edc_entry_field_history(entry_field_id);

CREATE TABLE IF NOT EXISTS edc_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id UUID NOT NULL REFERENCES edc_entries(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    meaning TEXT NOT NULL DEFAULT 'author',
    signature_hash TEXT NOT NULL,
    signed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_edc_signatures_entry_id ON edc_signatures(entry_id);
