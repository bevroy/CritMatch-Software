"""add fk indexes for access-heavy lookups

Revision ID: 0008_add_fk_indexes
Revises: 0007_ctfms
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op

revision = "0008_add_fk_indexes"
down_revision = "0007_ctfms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Added by audit follow-up: these are not present in prior migrations.
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)
    op.create_index("ix_edc_entry_fields_entry_id", "edc_entry_fields", ["entry_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_edc_entry_fields_entry_id", table_name="edc_entry_fields")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
