"""ctfms module

Revision ID: 0007_ctfms
Revises: 0006_edc
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007_ctfms"
down_revision = "0006_edc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ctfms_budgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("study_id", UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sponsor", sa.Text),
        sa.Column("contract_number", sa.Text),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("study_id", "version"),
    )
    op.create_index("ix_ctfms_budgets_study", "ctfms_budgets", ["study_id"])

    op.create_table(
        "ctfms_budget_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("budget_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("item_type", sa.Text, nullable=False, server_default="per_visit"),
        sa.Column("unit_price", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("edc_form_id", UUID(as_uuid=True), sa.ForeignKey("edc_forms.id", ondelete="SET NULL")),
        sa.Column("edc_field_id", UUID(as_uuid=True), sa.ForeignKey("edc_fields.id", ondelete="SET NULL")),
        sa.Column("auto_accrue", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ctfms_budget_items_budget", "ctfms_budget_items", ["budget_id"])
    op.create_index("ix_ctfms_budget_items_form", "ctfms_budget_items", ["edc_form_id"])

    op.create_table(
        "ctfms_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("study_id", UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_budgets.id", ondelete="SET NULL")),
        sa.Column("number", sa.Text, nullable=False),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("subtotal", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime),
        sa.Column("notes", sa.Text),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("study_id", "number"),
    )
    op.create_index("ix_ctfms_invoices_study", "ctfms_invoices", ["study_id"])

    op.create_table(
        "ctfms_invoice_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accrual_id", UUID(as_uuid=True)),  # FK added after accruals table
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ctfms_invoice_lines_invoice", "ctfms_invoice_lines", ["invoice_id"])

    op.create_table(
        "ctfms_accruals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("study_id", UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_item_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_budget_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", UUID(as_uuid=True), sa.ForeignKey("study_participants.id", ondelete="SET NULL")),
        sa.Column("entry_id", UUID(as_uuid=True), sa.ForeignKey("edc_entries.id", ondelete="SET NULL")),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("status", sa.Text, nullable=False, server_default="accrued"),
        sa.Column("invoice_line_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_invoice_lines.id", ondelete="SET NULL")),
        sa.Column("notes", sa.Text),
        sa.Column("accrued_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("accrued_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ctfms_accruals_study", "ctfms_accruals", ["study_id"])
    op.create_index("ix_ctfms_accruals_status", "ctfms_accruals", ["status"])
    op.create_index("ix_ctfms_accruals_entry", "ctfms_accruals", ["entry_id"])

    # Now add the deferred FK from invoice_lines.accrual_id to accruals.id
    op.create_foreign_key(
        "fk_ctfms_invoice_lines_accrual",
        "ctfms_invoice_lines", "ctfms_accruals",
        ["accrual_id"], ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "ctfms_payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("study_id", UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_invoices.id", ondelete="SET NULL")),
        sa.Column("amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("paid_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("method", sa.Text),
        sa.Column("reference", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ctfms_payments_study", "ctfms_payments", ["study_id"])
    op.create_index("ix_ctfms_payments_invoice", "ctfms_payments", ["invoice_id"])

    op.create_table(
        "ctfms_stipends",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("study_id", UUID(as_uuid=True), sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", UUID(as_uuid=True), sa.ForeignKey("study_participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_item_id", UUID(as_uuid=True), sa.ForeignKey("ctfms_budget_items.id", ondelete="SET NULL")),
        sa.Column("entry_id", UUID(as_uuid=True), sa.ForeignKey("edc_entries.id", ondelete="SET NULL")),
        sa.Column("amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime),
        sa.Column("method", sa.Text),
        sa.Column("reference", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ctfms_stipends_study", "ctfms_stipends", ["study_id"])
    op.create_index("ix_ctfms_stipends_participant", "ctfms_stipends", ["participant_id"])


def downgrade() -> None:
    op.drop_table("ctfms_stipends")
    op.drop_table("ctfms_payments")
    op.drop_constraint("fk_ctfms_invoice_lines_accrual", "ctfms_invoice_lines", type_="foreignkey")
    op.drop_table("ctfms_accruals")
    op.drop_table("ctfms_invoice_lines")
    op.drop_table("ctfms_invoices")
    op.drop_table("ctfms_budget_items")
    op.drop_table("ctfms_budgets")
