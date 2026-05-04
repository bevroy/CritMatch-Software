"""Pydantic schemas for the CTFMS module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_str(v: Any) -> Any:
    return str(v) if isinstance(v, UUID) else v


BudgetItemType = Literal[
    "per_visit",
    "per_procedure",
    "fixed_milestone",
    "passthrough",
    "overhead",
    "patient_stipend",
]
BudgetStatus = Literal["draft", "active", "archived"]
AccrualStatus = Literal["accrued", "invoiced", "void"]
InvoiceStatus = Literal["draft", "sent", "partial", "paid", "void"]
StipendStatus = Literal["pending", "paid", "void"]


# ---- Budget items ---------------------------------------------------------

class BudgetItemInput(BaseModel):
    code: str | None = None
    name: str
    description: str | None = None
    item_type: BudgetItemType = "per_visit"
    unit_price: int = 0  # minor units
    currency: str = "USD"
    edc_form_id: UUID | None = None
    edc_field_id: UUID | None = None
    auto_accrue: bool = True
    active: bool = True


class BudgetItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    budgetId: str = Field(alias="budget_id")
    code: str | None = None
    name: str
    description: str | None = None
    itemType: str = Field(alias="item_type")
    unitPrice: int = Field(alias="unit_price")
    currency: str
    edcFormId: str | None = Field(default=None, alias="edc_form_id")
    edcFieldId: str | None = Field(default=None, alias="edc_field_id")
    autoAccrue: bool = Field(alias="auto_accrue")
    active: bool
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")

    @field_validator("id", "budgetId", "edcFormId", "edcFieldId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Budgets --------------------------------------------------------------

class BudgetCreate(BaseModel):
    study_id: UUID
    name: str
    sponsor: str | None = None
    contract_number: str | None = None
    currency: str = "USD"
    notes: str | None = None
    items: list[BudgetItemInput] = Field(default_factory=list)


class BudgetUpdate(BaseModel):
    name: str | None = None
    sponsor: str | None = None
    contract_number: str | None = None
    currency: str | None = None
    notes: str | None = None
    status: BudgetStatus | None = None
    items: list[BudgetItemInput] | None = None  # full replacement when provided


class BudgetResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    name: str
    sponsor: str | None = None
    contractNumber: str | None = Field(default=None, alias="contract_number")
    currency: str
    version: int
    status: str
    notes: str | None = None
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    items: list[BudgetItemResponse] = Field(default_factory=list)

    @field_validator("id", "studyId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


class BudgetSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    name: str
    currency: str
    version: int
    status: str
    itemCount: int = 0
    updatedAt: datetime = Field(alias="updated_at")

    @field_validator("id", "studyId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Accruals -------------------------------------------------------------

class AccrualCreate(BaseModel):
    budget_item_id: UUID
    participant_id: UUID | None = None
    quantity: int = 1
    unit_price: int | None = None  # default to budget item price
    notes: str | None = None


class AccrualUpdate(BaseModel):
    status: AccrualStatus | None = None
    notes: str | None = None


class AccrualResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    budgetId: str = Field(alias="budget_id")
    budgetItemId: str = Field(alias="budget_item_id")
    participantId: str | None = Field(default=None, alias="participant_id")
    entryId: str | None = Field(default=None, alias="entry_id")
    quantity: int
    unitPrice: int = Field(alias="unit_price")
    amount: int
    currency: str
    status: str
    invoiceLineId: str | None = Field(default=None, alias="invoice_line_id")
    notes: str | None = None
    accruedAt: datetime = Field(alias="accrued_at")

    @field_validator("id", "studyId", "budgetId", "budgetItemId", "participantId", "entryId", "invoiceLineId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Invoices -------------------------------------------------------------

class InvoiceCreate(BaseModel):
    accrual_ids: list[UUID]
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    notes: str | None = None


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    accrualId: str | None = Field(default=None, alias="accrual_id")
    description: str
    quantity: int
    unitPrice: int = Field(alias="unit_price")
    amount: int
    currency: str

    @field_validator("id", "accrualId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    budgetId: str | None = Field(default=None, alias="budget_id")
    number: str
    currency: str
    subtotal: int
    total: int
    amountPaid: int = Field(alias="amount_paid")
    status: str
    issuedAt: datetime = Field(alias="issued_at")
    sentAt: datetime | None = Field(default=None, alias="sent_at")
    notes: str | None = None
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    lines: list[InvoiceLineResponse] = Field(default_factory=list)

    @field_validator("id", "studyId", "budgetId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Payments -------------------------------------------------------------

class PaymentCreate(BaseModel):
    invoice_id: UUID | None = None
    amount: int
    currency: str = "USD"
    paid_at: datetime | None = None
    method: str | None = None
    reference: str | None = None
    notes: str | None = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    invoiceId: str | None = Field(default=None, alias="invoice_id")
    amount: int
    currency: str
    paidAt: datetime = Field(alias="paid_at")
    method: str | None = None
    reference: str | None = None
    notes: str | None = None
    createdAt: datetime = Field(alias="created_at")

    @field_validator("id", "studyId", "invoiceId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Stipends -------------------------------------------------------------

class StipendCreate(BaseModel):
    participant_id: UUID
    budget_item_id: UUID | None = None
    amount: int
    currency: str = "USD"
    notes: str | None = None


class StipendUpdate(BaseModel):
    status: StipendStatus | None = None
    method: str | None = None
    reference: str | None = None
    notes: str | None = None


class StipendResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    participantId: str = Field(alias="participant_id")
    budgetItemId: str | None = Field(default=None, alias="budget_item_id")
    entryId: str | None = Field(default=None, alias="entry_id")
    amount: int
    currency: str
    status: str
    paidAt: datetime | None = Field(default=None, alias="paid_at")
    method: str | None = None
    reference: str | None = None
    notes: str | None = None
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")

    @field_validator("id", "studyId", "participantId", "budgetItemId", "entryId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Summary --------------------------------------------------------------

class FinanceSummary(BaseModel):
    accruedOpen: int
    accruedInvoiced: int
    invoiceTotal: int
    paid: int
    outstanding: int
    stipendsPending: int
    stipendsPaid: int
