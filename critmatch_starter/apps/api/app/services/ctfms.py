"""CTFMS business logic - accrual generation, totals, invoice numbering."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    CtfmsAccrual,
    CtfmsBudget,
    CtfmsBudgetItem,
    CtfmsInvoice,
    CtfmsInvoiceLine,
    CtfmsPayment,
    CtfmsStipend,
    EdcEntry,
    EdcEntryField,
    EdcField,
    StudyParticipant,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def active_budget_for_study(db: Session, study_id: uuid.UUID) -> CtfmsBudget | None:
    """Return the most recent active budget for a study (else most recent draft)."""
    q = db.query(CtfmsBudget).filter(CtfmsBudget.study_id == study_id)
    active = q.filter(CtfmsBudget.status == "active").order_by(CtfmsBudget.version.desc()).first()
    if active is not None:
        return active
    return q.order_by(CtfmsBudget.version.desc()).first()


def next_invoice_number(db: Session, study_id: uuid.UUID) -> str:
    """Generate the next sequential invoice number for the study (INV-0001 ...)."""
    count = (
        db.query(func.count(CtfmsInvoice.id))
        .filter(CtfmsInvoice.study_id == study_id)
        .scalar()
        or 0
    )
    return f"INV-{count + 1:04d}"


# ---------------------------------------------------------------------------
# EDC integration: auto-accrue on entry completion / signing.
# ---------------------------------------------------------------------------


def _entry_field_truthy(value) -> bool:
    """Did the field record a 'positive' value (procedure performed)?"""
    if value is None:
        return False
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "no", "false", "0", "n", "none", "null"}
    return True


def auto_accrue_for_entry(db: Session, entry: EdcEntry, *, by_user_id: uuid.UUID | None) -> list[CtfmsAccrual]:
    """Create accruals + stipends triggered by an EDC entry transition.

    Idempotent: skips items already accrued for this (entry, budget_item)
    pair.
    """
    participant = db.get(StudyParticipant, entry.participant_id) if entry.participant_id else None
    if participant is None:
        return []

    # PATCHED (audit fix, medium): previously only checked that the
    # participant row existed, not that they were actually enrolled in the
    # study. An EDC entry could be marked complete/locked (which triggers
    # this function from routes/edc.py's update_entry and sign_entry) for a
    # participant still in "screening" or already "withdrawn", generating
    # real financial accruals/invoices for visits tied to patients who were
    # never confirmed enrolled. Only participants who are (or have been)
    # actually enrolled can generate an accrual now.
    if participant.status not in {"enrolled", "completed"}:
        return []

    budget = active_budget_for_study(db, participant.study_id)
    if budget is None:
        return []

    # Existing accruals for this entry to avoid duplicates.
    existing = {
        a.budget_item_id
        for a in db.query(CtfmsAccrual).filter(CtfmsAccrual.entry_id == entry.id).all()
    }
    existing_stipends = {
        s.budget_item_id
        for s in db.query(CtfmsStipend).filter(CtfmsStipend.entry_id == entry.id).all()
    }

    items = (
        db.query(CtfmsBudgetItem)
        .filter(
            CtfmsBudgetItem.budget_id == budget.id,
            CtfmsBudgetItem.active.is_(True),
            CtfmsBudgetItem.auto_accrue.is_(True),
        )
        .all()
    )

    # Cache field values for per_procedure triggers.
    field_values_by_id: dict[uuid.UUID, EdcEntryField] = {}
    if any(i.item_type == "per_procedure" for i in items):
        for ef in db.query(EdcEntryField).filter(EdcEntryField.entry_id == entry.id).all():
            field_values_by_id[ef.field_id] = ef

    created: list[CtfmsAccrual] = []
    now = datetime.utcnow()
    for item in items:
        if item.item_type == "per_visit":
            if item.edc_form_id and item.edc_form_id != entry.form_id:
                continue
            if item.id in existing:
                continue
            acc = _make_accrual(item, budget, participant, entry, by_user_id, now)
            db.add(acc)
            created.append(acc)
        elif item.item_type == "per_procedure":
            if item.edc_field_id is None:
                continue
            ef = field_values_by_id.get(item.edc_field_id)
            if ef is None or not _entry_field_truthy(ef.value_json):
                continue
            if item.id in existing:
                continue
            acc = _make_accrual(item, budget, participant, entry, by_user_id, now)
            db.add(acc)
            created.append(acc)
        elif item.item_type == "patient_stipend":
            if item.edc_form_id and item.edc_form_id != entry.form_id:
                continue
            if item.id in existing_stipends:
                continue
            stip = CtfmsStipend(
                id=uuid.uuid4(),
                study_id=participant.study_id,
                participant_id=participant.id,
                budget_item_id=item.id,
                entry_id=entry.id,
                amount=item.unit_price,
                currency=item.currency,
                status="pending",
                created_by=by_user_id,
            )
            db.add(stip)
        # fixed_milestone, passthrough, overhead -> manual only

    return created


def _make_accrual(item, budget, participant, entry, by_user_id, now) -> CtfmsAccrual:
    return CtfmsAccrual(
        id=uuid.uuid4(),
        study_id=participant.study_id,
        budget_id=budget.id,
        budget_item_id=item.id,
        participant_id=participant.id,
        entry_id=entry.id,
        quantity=1,
        unit_price=item.unit_price,
        amount=item.unit_price,
        currency=item.currency,
        status="accrued",
        accrued_by=by_user_id,
        accrued_at=now,
    )


# ---------------------------------------------------------------------------
# Invoice helpers
# ---------------------------------------------------------------------------


def build_invoice_from_accruals(
    db: Session,
    study_id: uuid.UUID,
    accrual_ids: Iterable[uuid.UUID],
    *,
    notes: str | None,
    by_user_id: uuid.UUID | None,
) -> CtfmsInvoice:
    """Create a draft invoice referencing the given accruals.

    All accruals must belong to the study, be in 'accrued' status, and share
    a single currency. Each accrual becomes one invoice line and is marked
    'invoiced'.
    """
    accruals = (
        db.query(CtfmsAccrual)
        .filter(CtfmsAccrual.id.in_(list(accrual_ids)), CtfmsAccrual.study_id == study_id)
        .all()
    )
    if not accruals:
        raise ValueError("No matching accruals")
    statuses = {a.status for a in accruals}
    if statuses != {"accrued"}:
        raise ValueError("All accruals must be in 'accrued' status")
    currencies = {a.currency for a in accruals}
    if len(currencies) != 1:
        raise ValueError("All accruals must share a single currency")
    currency = next(iter(currencies))
    budget_id = accruals[0].budget_id

    item_names = {
        i.id: i.name
        for i in db.query(CtfmsBudgetItem)
        .filter(CtfmsBudgetItem.id.in_({a.budget_item_id for a in accruals}))
        .all()
    }

    invoice = CtfmsInvoice(
        id=uuid.uuid4(),
        study_id=study_id,
        budget_id=budget_id,
        number=next_invoice_number(db, study_id),
        currency=currency,
        subtotal=sum(a.amount for a in accruals),
        total=sum(a.amount for a in accruals),
        amount_paid=0,
        status="draft",
        notes=notes,
        created_by=by_user_id,
    )
    db.add(invoice)
    db.flush()

    for a in accruals:
        line = CtfmsInvoiceLine(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            accrual_id=a.id,
            description=item_names.get(a.budget_item_id, "Line item"),
            quantity=a.quantity,
            unit_price=a.unit_price,
            amount=a.amount,
            currency=a.currency,
        )
        db.add(line)
        db.flush()
        a.status = "invoiced"
        a.invoice_line_id = line.id

    return invoice


def apply_payment_to_invoice(invoice: CtfmsInvoice, payment_amount: int) -> None:
    """Update invoice status after a payment is added/removed. Caller mutates amount_paid."""
    if invoice.amount_paid <= 0:
        invoice.status = "draft" if invoice.status == "draft" else invoice.status
        return
    if invoice.amount_paid >= invoice.total:
        invoice.status = "paid"
    else:
        invoice.status = "partial"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def study_finance_summary(db: Session, study_id: uuid.UUID) -> dict:
    accrued = (
        db.query(func.coalesce(func.sum(CtfmsAccrual.amount), 0))
        .filter(CtfmsAccrual.study_id == study_id, CtfmsAccrual.status == "accrued")
        .scalar()
    )
    invoiced = (
        db.query(func.coalesce(func.sum(CtfmsAccrual.amount), 0))
        .filter(CtfmsAccrual.study_id == study_id, CtfmsAccrual.status == "invoiced")
        .scalar()
    )
    invoice_total = (
        db.query(func.coalesce(func.sum(CtfmsInvoice.total), 0))
        .filter(CtfmsInvoice.study_id == study_id, CtfmsInvoice.status != "void")
        .scalar()
    )
    paid = (
        db.query(func.coalesce(func.sum(CtfmsPayment.amount), 0))
        .filter(CtfmsPayment.study_id == study_id)
        .scalar()
    )
    stipend_pending = (
        db.query(func.coalesce(func.sum(CtfmsStipend.amount), 0))
        .filter(CtfmsStipend.study_id == study_id, CtfmsStipend.status == "pending")
        .scalar()
    )
    stipend_paid = (
        db.query(func.coalesce(func.sum(CtfmsStipend.amount), 0))
        .filter(CtfmsStipend.study_id == study_id, CtfmsStipend.status == "paid")
        .scalar()
    )
    outstanding = invoice_total - paid
    return {
        "accruedOpen": accrued,
        "accruedInvoiced": invoiced,
        "invoiceTotal": invoice_total,
        "paid": paid,
        "outstanding": outstanding,
        "stipendsPending": stipend_pending,
        "stipendsPaid": stipend_paid,
    }
