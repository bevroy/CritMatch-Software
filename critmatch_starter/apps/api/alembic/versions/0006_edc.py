"""Add EDC module tables

Revision ID: 0006_edc
Revises: 0005_study_investigators
Create Date: 2026-05-04
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_edc"
down_revision: str | Sequence[str] | None = "0005_study_investigators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edc_forms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("study_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_edc_forms_study_id", "edc_forms", ["study_id"])

    op.create_table(
        "edc_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("form_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edc_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False, server_default=sa.text("'string'")),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("options_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fhir_mapping_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_edc_fields_form_id", "edc_fields", ["form_id"])

    op.create_table(
        "study_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("study_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'screening'")),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("query_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(), nullable=True),
        sa.Column("enrolled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("study_id", "subject_id", name="uq_study_participants_subject"),
    )
    op.create_index("ix_study_participants_study_id", "study_participants", ["study_id"])
    op.create_index("ix_study_participants_patient_id", "study_participants", ["patient_id"])

    op.create_table(
        "edc_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("form_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edc_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'in_progress'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_edc_entries_form_id", "edc_entries", ["form_id"])
    op.create_index("ix_edc_entries_participant_id", "edc_entries", ["participant_id"])

    op.create_table(
        "edc_entry_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edc_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edc_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("fhir_source_ref", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("entry_id", "field_id", name="uq_edc_entry_fields_entry_field"),
    )

    op.create_table(
        "edc_entry_field_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entry_field_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edc_entry_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("old_source", sa.Text(), nullable=True),
        sa.Column("new_source", sa.Text(), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_edc_entry_field_history_entry_field_id", "edc_entry_field_history", ["entry_field_id"])

    op.create_table(
        "edc_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edc_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False, server_default=sa.text("'author'")),
        sa.Column("signature_hash", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_edc_signatures_entry_id", "edc_signatures", ["entry_id"])


def downgrade() -> None:
    op.drop_table("edc_signatures")
    op.drop_table("edc_entry_field_history")
    op.drop_table("edc_entry_fields")
    op.drop_table("edc_entries")
    op.drop_table("study_participants")
    op.drop_table("edc_fields")
    op.drop_table("edc_forms")
