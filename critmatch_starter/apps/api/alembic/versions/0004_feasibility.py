"""Add feasibility module tables

Revision ID: 0004_feasibility
Revises: 0003_notifications
Create Date: 2026-05-04
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_feasibility"
down_revision: str | Sequence[str] | None = "0003_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feasibility_questionnaires",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("study_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_feasibility_questionnaires_study_id",
        "feasibility_questionnaires",
        ["study_id"],
        unique=False,
    )
    op.create_index(
        "ix_feasibility_questionnaires_created_by",
        "feasibility_questionnaires",
        ["created_by"],
        unique=False,
    )

    op.create_table(
        "feasibility_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "questionnaire_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feasibility_questionnaires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("logic_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_feasibility_questions_questionnaire_id",
        "feasibility_questions",
        ["questionnaire_id"],
        unique=False,
    )

    op.create_table(
        "feasibility_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "questionnaire_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feasibility_questionnaires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("total_patients", sa.Integer(), nullable=True),
        sa.Column("execution_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_feasibility_runs_questionnaire_id",
        "feasibility_runs",
        ["questionnaire_id"],
        unique=False,
    )
    op.create_index("ix_feasibility_runs_status", "feasibility_runs", ["status"], unique=False)

    op.create_table(
        "feasibility_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feasibility_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feasibility_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("detail_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_feasibility_results_run_id", "feasibility_results", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_feasibility_results_run_id", table_name="feasibility_results")
    op.drop_table("feasibility_results")
    op.drop_index("ix_feasibility_runs_status", table_name="feasibility_runs")
    op.drop_index("ix_feasibility_runs_questionnaire_id", table_name="feasibility_runs")
    op.drop_table("feasibility_runs")
    op.drop_index("ix_feasibility_questions_questionnaire_id", table_name="feasibility_questions")
    op.drop_table("feasibility_questions")
    op.drop_index("ix_feasibility_questionnaires_created_by", table_name="feasibility_questionnaires")
    op.drop_index("ix_feasibility_questionnaires_study_id", table_name="feasibility_questionnaires")
    op.drop_table("feasibility_questionnaires")
