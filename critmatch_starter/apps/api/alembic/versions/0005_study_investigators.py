"""Add study_investigators table

Revision ID: 0005_study_investigators
Revises: 0004_feasibility
Create Date: 2026-05-04
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_study_investigators"
down_revision: str | Sequence[str] | None = "0004_feasibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_investigators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("practitioner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("npi", sa.Text(), nullable=True),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'sub_investigator'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "study_id", "practitioner_id", name="uq_study_investigators_study_practitioner"
        ),
    )
    op.create_index(
        "ix_study_investigators_study_id",
        "study_investigators",
        ["study_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_study_investigators_study_id", table_name="study_investigators")
    op.drop_table("study_investigators")
