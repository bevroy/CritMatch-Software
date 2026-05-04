"""CTFMS routes — budgets, accruals, invoices, payments, stipends, dashboards.

All routes are mounted under /api/ctfms (and a few study-scoped helpers under
/api/studies/{id}/finance/...). Read access requires study viewer; mutations
require editor for accruals/budgets and `finance` role for invoices/payments.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.models import (
    CtfmsAccrual,
    CtfmsBudget,
    CtfmsBudgetItem,
    CtfmsInvoice,
    CtfmsInvoiceLine,
    CtfmsPayment,
    CtfmsStipend,
    Study,
    StudyParticipant,
    User,
)
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.ctfms import (
    AccrualCreate,
    AccrualResponse,
    AccrualUpdate,
    BudgetCreate,
    BudgetItemInput,
    BudgetItemResponse,
    BudgetResponse,
    BudgetSummary,
    BudgetUpdate,
    FinanceSummary,
    InvoiceCreate,
    InvoiceLineResponse,
    InvoiceResponse,
    InvoiceUpdate,
    PaymentCreate,
    PaymentResponse,
    StipendCreate,
    StipendResponse,
    StipendUpdate,
)
from app.services.access import require_access, require_finance_access
from app.services.audit_service import record as record_audit
from app.services.ctfms import (
    apply_payment_to_invoice,
    build_invoice_from_accruals,
    study_finance_summary,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _study_for_budget(db: Session, budget: CtfmsBudget) -> Study | None:
    return db.get(Study, budget.study_id)


def _serialize_item(i: CtfmsBudgetItem) -> BudgetItemResponse:
    return BudgetItemResponse(
        id=str(i.id),
        budget_id=str(i.budget_id),
        code=i.code,
        name=i.name,
        description=i.description,
        item_type=i.item_type,
        unit_price=i.unit_price,
        currency=i.currency,
        edc_form_id=str(i.edc_form_id) if i.edc_form_id else None,
        edc_field_id=str(i.edc_field_id) if i.edc_field_id else None,
        auto_accrue=i.auto_accrue,
        active=i.active,
        created_at=i.created_at,
        updated_at=i.updated_at,
    )


def _serialize_budget(b: CtfmsBudget) -> BudgetResponse:
    return BudgetResponse(
        id=str(b.id),
        study_id=str(b.study_id),
        name=b.name,
        sponsor=b.sponsor,
        contract_number=b.contract_number,
        currency=b.currency,
        version=b.version,
        status=b.status,
        notes=b.notes,
        created_at=b.created_at,
        updated_at=b.updated_at,
        items=[_serialize_item(i) for i in sorted(b.items, key=lambda x: (not x.active, x.name))],
    )


def _serialize_accrual(a: CtfmsAccrual) -> AccrualResponse:
    return AccrualResponse(
        id=str(a.id),
        study_id=str(a.study_id),
        budget_id=str(a.budget_id),
        budget_item_id=str(a.budget_item_id),
        participant_id=str(a.participant_id) if a.participant_id else None,
        entry_id=str(a.entry_id) if a.entry_id else None,
        quantity=a.quantity,
        unit_price=a.unit_price,
        amount=a.amount,
        currency=a.currency,
        status=a.status,
        invoice_line_id=str(a.invoice_line_id) if a.invoice_line_id else None,
        notes=a.notes,
        accrued_at=a.accrued_at,
    )


def _serialize_invoice_line(line: CtfmsInvoiceLine) -> InvoiceLineResponse:
    return InvoiceLineResponse(
        id=str(line.id),
        accrual_id=str(line.accrual_id) if line.accrual_id else None,
        description=line.description,
        quantity=line.quantity,
        unit_price=line.unit_price,
        amount=line.amount,
        currency=line.currency,
    )


def _serialize_invoice(inv: CtfmsInvoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=str(inv.id),
        study_id=str(inv.study_id),
        budget_id=str(inv.budget_id) if inv.budget_id else None,
        number=inv.number,
        currency=inv.currency,
        subtotal=inv.subtotal,
        total=inv.total,
        amount_paid=inv.amount_paid,
        status=inv.status,
        issued_at=inv.issued_at,
        sent_at=inv.sent_at,
        notes=inv.notes,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        lines=[_serialize_invoice_line(l) for l in inv.lines],
    )


def _serialize_payment(p: CtfmsPayment) -> PaymentResponse:
    return PaymentResponse(
        id=str(p.id),
        study_id=str(p.study_id),
        invoice_id=str(p.invoice_id) if p.invoice_id else None,
        amount=p.amount,
        currency=p.currency,
        paid_at=p.paid_at,
        method=p.method,
        reference=p.reference,
        notes=p.notes,
        created_at=p.created_at,
    )


def _serialize_stipend(s: CtfmsStipend) -> StipendResponse:
    return StipendResponse(
        id=str(s.id),
        study_id=str(s.study_id),
        participant_id=str(s.participant_id),
        budget_item_id=str(s.budget_item_id) if s.budget_item_id else None,
        entry_id=str(s.entry_id) if s.entry_id else None,
        amount=s.amount,
        currency=s.currency,
        status=s.status,
        paid_at=s.paid_at,
        method=s.method,
        reference=s.reference,
        notes=s.notes,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _replace_items(db: Session, budget: CtfmsBudget, items: list[BudgetItemInput]) -> None:
    for old in list(budget.items):
        db.delete(old)
    db.flush()
    for spec in items:
        db.add(CtfmsBudgetItem(
            id=uuid.uuid4(),
            budget_id=budget.id,
            code=spec.code,
            name=spec.name,
            description=spec.description,
            item_type=spec.item_type,
            unit_price=spec.unit_price,
            currency=spec.currency,
            edc_form_id=spec.edc_form_id,
            edc_field_id=spec.edc_field_id,
            auto_accrue=spec.auto_accrue,
            active=spec.active,
        ))


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


@router.get("/budgets", response_model=list[BudgetSummary])
def list_budgets(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = Query(None),
) -> list[BudgetSummary]:
    q = db.query(CtfmsBudget)
    if studyId:
        q = q.filter(CtfmsBudget.study_id == uuid.UUID(studyId))
    rows = q.order_by(CtfmsBudget.updated_at.desc()).all()
    out: list[BudgetSummary] = []
    for b in rows:
        study = db.get(Study, b.study_id)
        if study is None:
            continue
        try:
            require_access(study, user, db, minimum="viewer")
        except HTTPException:
            continue
        out.append(BudgetSummary(
            id=str(b.id),
            study_id=str(b.study_id),
            name=b.name,
            currency=b.currency,
            version=b.version,
            status=b.status,
            itemCount=len(b.items),
            updated_at=b.updated_at,
        ))
    return out


@router.post("/budgets", response_model=BudgetResponse, status_code=201)
def create_budget(
    payload: BudgetCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> BudgetResponse:
    study = db.get(Study, payload.study_id)
    require_access(study, user, db, minimum="editor")
    next_version = (
        db.query(CtfmsBudget)
        .filter(CtfmsBudget.study_id == payload.study_id)
        .order_by(CtfmsBudget.version.desc())
        .first()
    )
    version = (next_version.version + 1) if next_version else 1
    budget = CtfmsBudget(
        id=uuid.uuid4(),
        study_id=payload.study_id,
        name=payload.name,
        sponsor=payload.sponsor,
        contract_number=payload.contract_number,
        currency=payload.currency,
        version=version,
        status="draft",
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(budget)
    db.flush()
    _replace_items(db, budget, payload.items)
    record_audit(
        db,
        user_id=user.id,
        action="ctfms_budget_create",
        object_type="ctfms_budget",
        object_id=str(budget.id),
        request=request,
        extra={"study_id": str(payload.study_id), "version": version},
    )
    db.commit()
    db.refresh(budget)
    return _serialize_budget(budget)


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> BudgetResponse:
    b = db.get(CtfmsBudget, uuid.UUID(budget_id))
    if b is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    require_access(_study_for_budget(db, b), user, db, minimum="viewer")
    return _serialize_budget(b)


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: str,
    payload: BudgetUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> BudgetResponse:
    b = db.get(CtfmsBudget, uuid.UUID(budget_id))
    if b is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    require_access(_study_for_budget(db, b), user, db, minimum="editor")
    if b.status == "archived":
        raise HTTPException(status_code=409, detail="Budget is archived")

    if payload.name is not None: b.name = payload.name
    if payload.sponsor is not None: b.sponsor = payload.sponsor
    if payload.contract_number is not None: b.contract_number = payload.contract_number
    if payload.currency is not None: b.currency = payload.currency
    if payload.notes is not None: b.notes = payload.notes
    if payload.status is not None: b.status = payload.status
    if payload.items is not None:
        _replace_items(db, b, payload.items)

    record_audit(
        db, user_id=user.id, action="ctfms_budget_update",
        object_type="ctfms_budget", object_id=str(b.id), request=request,
    )
    db.commit()
    db.refresh(b)
    return _serialize_budget(b)


@router.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    b = db.get(CtfmsBudget, uuid.UUID(budget_id))
    if b is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    require_access(_study_for_budget(db, b), user, db, minimum="editor")
    bid = str(b.id)
    db.delete(b)
    record_audit(
        db, user_id=user.id, action="ctfms_budget_delete",
        object_type="ctfms_budget", object_id=bid, request=request,
    )
    db.commit()
    return {"id": bid, "deleted": True}


# ---------------------------------------------------------------------------
# Accruals
# ---------------------------------------------------------------------------


@router.get("/accruals", response_model=list[AccrualResponse])
def list_accruals(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> list[AccrualResponse]:
    if not studyId:
        raise HTTPException(status_code=400, detail="studyId is required")
    sid = uuid.UUID(studyId)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="viewer")
    q = db.query(CtfmsAccrual).filter(CtfmsAccrual.study_id == sid)
    if status:
        q = q.filter(CtfmsAccrual.status == status)
    rows = q.order_by(CtfmsAccrual.accrued_at.desc()).all()
    return [_serialize_accrual(a) for a in rows]


@router.post("/budgets/{budget_id}/accruals", response_model=AccrualResponse, status_code=201)
def create_accrual(
    budget_id: str,
    payload: AccrualCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> AccrualResponse:
    b = db.get(CtfmsBudget, uuid.UUID(budget_id))
    if b is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    require_access(_study_for_budget(db, b), user, db, minimum="editor")
    item = db.get(CtfmsBudgetItem, payload.budget_item_id)
    if item is None or item.budget_id != b.id:
        raise HTTPException(status_code=400, detail="budget_item_id not in this budget")
    if payload.participant_id is not None:
        p = db.get(StudyParticipant, payload.participant_id)
        if p is None or p.study_id != b.study_id:
            raise HTTPException(status_code=400, detail="participant_id not in this study")
    unit_price = payload.unit_price if payload.unit_price is not None else item.unit_price
    qty = max(1, payload.quantity)
    a = CtfmsAccrual(
        id=uuid.uuid4(),
        study_id=b.study_id,
        budget_id=b.id,
        budget_item_id=item.id,
        participant_id=payload.participant_id,
        quantity=qty,
        unit_price=unit_price,
        amount=qty * unit_price,
        currency=item.currency,
        status="accrued",
        notes=payload.notes,
        accrued_by=user.id,
    )
    db.add(a)
    record_audit(
        db, user_id=user.id, action="ctfms_accrual_create",
        object_type="ctfms_accrual", object_id=str(a.id), request=request,
    )
    db.commit()
    db.refresh(a)
    return _serialize_accrual(a)


@router.patch("/accruals/{accrual_id}", response_model=AccrualResponse)
def update_accrual(
    accrual_id: str,
    payload: AccrualUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> AccrualResponse:
    a = db.get(CtfmsAccrual, uuid.UUID(accrual_id))
    if a is None:
        raise HTTPException(status_code=404, detail="Accrual not found")
    study = db.get(Study, a.study_id)
    require_access(study, user, db, minimum="editor")
    if a.status == "invoiced":
        raise HTTPException(status_code=409, detail="Accrual already invoiced; void/edit invoice instead")
    if payload.status is not None: a.status = payload.status
    if payload.notes is not None: a.notes = payload.notes
    record_audit(
        db, user_id=user.id, action="ctfms_accrual_update",
        object_type="ctfms_accrual", object_id=str(a.id), request=request,
    )
    db.commit()
    db.refresh(a)
    return _serialize_accrual(a)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = Query(None),
) -> list[InvoiceResponse]:
    if not studyId:
        raise HTTPException(status_code=400, detail="studyId is required")
    sid = uuid.UUID(studyId)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="viewer")
    rows = (
        db.query(CtfmsInvoice)
        .filter(CtfmsInvoice.study_id == sid)
        .order_by(CtfmsInvoice.issued_at.desc())
        .all()
    )
    return [_serialize_invoice(i) for i in rows]


@router.post("/studies/{study_id}/invoices", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    study_id: str,
    payload: InvoiceCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_finance_access(study, user, db)
    try:
        invoice = build_invoice_from_accruals(
            db, sid, [uuid.UUID(str(a)) for a in payload.accrual_ids],
            notes=payload.notes, by_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    record_audit(
        db, user_id=user.id, action="ctfms_invoice_create",
        object_type="ctfms_invoice", object_id=str(invoice.id), request=request,
        extra={"line_count": len(invoice.lines), "total": invoice.total},
    )
    db.commit()
    db.refresh(invoice)
    return _serialize_invoice(invoice)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    inv = db.get(CtfmsInvoice, uuid.UUID(invoice_id))
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    study = db.get(Study, inv.study_id)
    require_access(study, user, db, minimum="viewer")
    return _serialize_invoice(inv)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> InvoiceResponse:
    inv = db.get(CtfmsInvoice, uuid.UUID(invoice_id))
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    study = db.get(Study, inv.study_id)
    require_finance_access(study, user, db)
    if payload.status is not None:
        if payload.status == "sent" and inv.sent_at is None:
            inv.sent_at = datetime.utcnow()
        if payload.status == "void":
            # Free up the accruals so they can be re-billed.
            for line in inv.lines:
                if line.accrual_id:
                    a = db.get(CtfmsAccrual, line.accrual_id)
                    if a is not None:
                        a.status = "accrued"
                        a.invoice_line_id = None
        inv.status = payload.status
    if payload.notes is not None:
        inv.notes = payload.notes
    record_audit(
        db, user_id=user.id, action="ctfms_invoice_update",
        object_type="ctfms_invoice", object_id=str(inv.id), request=request,
    )
    db.commit()
    db.refresh(inv)
    return _serialize_invoice(inv)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = Query(None),
) -> list[PaymentResponse]:
    if not studyId:
        raise HTTPException(status_code=400, detail="studyId is required")
    sid = uuid.UUID(studyId)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="viewer")
    rows = (
        db.query(CtfmsPayment)
        .filter(CtfmsPayment.study_id == sid)
        .order_by(CtfmsPayment.paid_at.desc())
        .all()
    )
    return [_serialize_payment(p) for p in rows]


@router.post("/studies/{study_id}/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    study_id: str,
    payload: PaymentCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_finance_access(study, user, db)
    invoice = db.get(CtfmsInvoice, payload.invoice_id) if payload.invoice_id else None
    if payload.invoice_id and (invoice is None or invoice.study_id != sid):
        raise HTTPException(status_code=400, detail="invoice not in this study")
    p = CtfmsPayment(
        id=uuid.uuid4(),
        study_id=sid,
        invoice_id=payload.invoice_id,
        amount=payload.amount,
        currency=payload.currency,
        paid_at=payload.paid_at or datetime.utcnow(),
        method=payload.method,
        reference=payload.reference,
        notes=payload.notes,
        recorded_by=user.id,
    )
    db.add(p)
    if invoice is not None:
        invoice.amount_paid += payload.amount
        apply_payment_to_invoice(invoice, payload.amount)
    record_audit(
        db, user_id=user.id, action="ctfms_payment_create",
        object_type="ctfms_payment", object_id=str(p.id), request=request,
        extra={"amount": p.amount, "invoice_id": str(p.invoice_id) if p.invoice_id else None},
    )
    db.commit()
    db.refresh(p)
    return _serialize_payment(p)


# ---------------------------------------------------------------------------
# Stipends
# ---------------------------------------------------------------------------


@router.get("/stipends", response_model=list[StipendResponse])
def list_stipends(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> list[StipendResponse]:
    if not studyId:
        raise HTTPException(status_code=400, detail="studyId is required")
    sid = uuid.UUID(studyId)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="viewer")
    q = db.query(CtfmsStipend).filter(CtfmsStipend.study_id == sid)
    if status:
        q = q.filter(CtfmsStipend.status == status)
    rows = q.order_by(CtfmsStipend.created_at.desc()).all()
    return [_serialize_stipend(s) for s in rows]


@router.post("/studies/{study_id}/stipends", response_model=StipendResponse, status_code=201)
def create_stipend(
    study_id: str,
    payload: StipendCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> StipendResponse:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="editor")
    p = db.get(StudyParticipant, payload.participant_id)
    if p is None or p.study_id != sid:
        raise HTTPException(status_code=400, detail="participant not in this study")
    s = CtfmsStipend(
        id=uuid.uuid4(),
        study_id=sid,
        participant_id=payload.participant_id,
        budget_item_id=payload.budget_item_id,
        amount=payload.amount,
        currency=payload.currency,
        status="pending",
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(s)
    record_audit(
        db, user_id=user.id, action="ctfms_stipend_create",
        object_type="ctfms_stipend", object_id=str(s.id), request=request,
    )
    db.commit()
    db.refresh(s)
    return _serialize_stipend(s)


@router.patch("/stipends/{stipend_id}", response_model=StipendResponse)
def update_stipend(
    stipend_id: str,
    payload: StipendUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> StipendResponse:
    s = db.get(CtfmsStipend, uuid.UUID(stipend_id))
    if s is None:
        raise HTTPException(status_code=404, detail="Stipend not found")
    study = db.get(Study, s.study_id)
    require_finance_access(study, user, db)
    if payload.status is not None:
        if payload.status == "paid" and s.status != "paid":
            s.paid_at = datetime.utcnow()
        s.status = payload.status
    if payload.method is not None: s.method = payload.method
    if payload.reference is not None: s.reference = payload.reference
    if payload.notes is not None: s.notes = payload.notes
    record_audit(
        db, user_id=user.id, action="ctfms_stipend_update",
        object_type="ctfms_stipend", object_id=str(s.id), request=request,
    )
    db.commit()
    db.refresh(s)
    return _serialize_stipend(s)


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


@router.get("/studies/{study_id}/summary", response_model=FinanceSummary)
def finance_summary(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FinanceSummary:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="viewer")
    return FinanceSummary(**study_finance_summary(db, sid))
