"""add password_hash to users for first-party login

Revision ID: 0009_user_password_hash
Revises: 0008_add_fk_indexes
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_user_password_hash"
down_revision = "0008_add_fk_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
