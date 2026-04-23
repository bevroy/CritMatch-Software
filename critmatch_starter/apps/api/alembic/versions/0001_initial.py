"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-23

Mirrors apps/api/sql/001_initial_schema.sql so that a fresh deploy can be
brought to current schema with ``alembic upgrade head``.
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ehr_user_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'research_user'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_ehr_user_id", "users", ["ehr_user_id"], unique=False)

    op.create_table(
        "studies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_studies_owner_user_id", "studies", ["owner_user_id"], unique=False)

    op.create_table(
        "criteria_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("study_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("logic_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("study_id", "version", name="uq_criteria_sets_study_version"),
    )

    op.create_table(
        "terminology_expansions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("criteria_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("criteria_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_term", sa.Text(), nullable=False),
        sa.Column("normalized_term", sa.Text(), nullable=True),
        sa.Column("expansion_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "query_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("study_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criteria_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("criteria_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("execution_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_query_runs_status", "query_runs", ["status"], unique=False)
    op.create_index("ix_query_runs_study_id", "query_runs", ["study_id"], unique=False)

    op.create_table(
        "query_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Text(), nullable=False),
        sa.Column("mrn_hash", sa.Text(), nullable=True),
        sa.Column("matched_rules_json", postgresql.JSONB(), nullable=True),
        sa.Column("primary_match_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_query_results_query_run_id", "query_results", ["query_run_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_query_results_query_run_id", table_name="query_results")
    op.drop_table("query_results")
    op.drop_index("ix_query_runs_study_id", table_name="query_runs")
    op.drop_index("ix_query_runs_status", table_name="query_runs")
    op.drop_table("query_runs")
    op.drop_table("terminology_expansions")
    op.drop_table("criteria_sets")
    op.drop_index("ix_studies_owner_user_id", table_name="studies")
    op.drop_table("studies")
    op.drop_index("ix_users_ehr_user_id", table_name="users")
    op.drop_table("users")
