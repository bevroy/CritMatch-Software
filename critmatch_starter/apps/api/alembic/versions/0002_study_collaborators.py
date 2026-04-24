"""Add study_collaborators table

Revision ID: 0002_study_collaborators
Revises: 0001_initial
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_study_collaborators"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_collaborators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("study_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("study_id", "user_id", name="uq_study_collaborators_study_user"),
    )
    op.create_index("ix_study_collaborators_user_id", "study_collaborators", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_study_collaborators_user_id", table_name="study_collaborators")
    op.drop_table("study_collaborators")
