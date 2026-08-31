"""Add oauth_states table for SMART launch state/PKCE storage

Revision ID: 0010_oauth_state
Revises: 0009_user_password_hash
Create Date: 2026-08-31

Replaces routes/auth.py's in-process ``_state_store`` dict (module docstring
flagged it as single-instance-only) with a DB-backed store so state survives
across multiple API instances/restarts between /authorize and /callback.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_oauth_state"
down_revision = "0009_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.Text(), primary_key=True),
        sa.Column("iss", sa.Text(), nullable=False),
        sa.Column("token_endpoint", sa.Text(), nullable=False),
        sa.Column("jwks_uri", sa.Text(), nullable=True),
        sa.Column("code_verifier", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_table("oauth_states")
