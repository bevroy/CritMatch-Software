"""Pydantic schemas for the EDC module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ItemType = Literal[
    "string",
    "text",
    "integer",
    "decimal",
    "boolean",
    "date",
    "dateTime",
    "time",
    "choice",
    "open-choice",
    "quantity",
    "attachment",
    "group",
    "display",
]

ParticipantStatus = Literal["screening", "enrolled", "withdrawn", "completed"]
EntryStatus = Literal["in_progress", "complete", "locked"]
SignatureMeaning = Literal["author", "reviewer", "approver"]


def _to_str(v: Any) -> Any:
    return str(v) if isinstance(v, UUID) else v


# ---- Forms / fields ---------------------------------------------------

class EdcFieldInput(BaseModel):
    key: str
    label: str
    item_type: ItemType = "string"
    position: int | None = None
    required: bool = False
    options_json: dict[str, Any] | None = None
    fhir_mapping_json: dict[str, Any] | None = None
    validation_json: dict[str, Any] | None = None


class EdcFieldResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    position: int
    key: str
    label: str
    itemType: str = Field(alias="item_type")
    required: bool
    optionsJson: dict[str, Any] | None = Field(default=None, alias="options_json")
    fhirMappingJson: dict[str, Any] | None = Field(default=None, alias="fhir_mapping_json")
    validationJson: dict[str, Any] | None = Field(default=None, alias="validation_json")

    @field_validator("id", mode="before")
    @classmethod
    def _id(cls, v): return _to_str(v)


class EdcFormCreate(BaseModel):
    study_id: UUID
    name: str
    description: str | None = None
    fields: list[EdcFieldInput] = Field(default_factory=list)


class EdcFormUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: Literal["draft", "active", "locked"] | None = None
    fields: list[EdcFieldInput] | None = None


class EdcFormResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    name: str
    description: str | None
    version: int
    status: str
    createdBy: str | None = Field(default=None, alias="created_by")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    fields: list[EdcFieldResponse] = Field(default_factory=list)

    @field_validator("id", "studyId", "createdBy", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


class EdcFormSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    name: str
    description: str | None
    version: int
    status: str
    fieldCount: int = 0
    updatedAt: datetime = Field(alias="updated_at")

    @field_validator("id", "studyId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Participants -----------------------------------------------------

class ParticipantCreate(BaseModel):
    patient_id: str
    subject_id: str
    status: ParticipantStatus = "screening"
    notes: str | None = None


class ParticipantPromote(BaseModel):
    """Promote one or more cohort matches to participants."""
    run_id: UUID
    patient_ids: list[str]
    subject_id_prefix: str | None = None


class ParticipantUpdate(BaseModel):
    subject_id: str | None = None
    status: ParticipantStatus | None = None
    notes: str | None = None


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studyId: str = Field(alias="study_id")
    patientId: str = Field(alias="patient_id")
    subjectId: str = Field(alias="subject_id")
    status: str
    source: str
    sourceRunId: str | None = Field(default=None, alias="source_run_id")
    enrolledAt: datetime | None = Field(default=None, alias="enrolled_at")
    notes: str | None
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")

    @field_validator("id", "studyId", "sourceRunId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


# ---- Entries ----------------------------------------------------------

class EntryFieldValue(BaseModel):
    """Wire format for a single field value in an entry."""
    field_id: UUID
    value: Any = None
    source: Literal["manual", "fhir_pull"] = "manual"
    fhir_source_ref: str | None = None
    reason_for_change: str | None = None


class EntryUpdate(BaseModel):
    values: list[EntryFieldValue] = Field(default_factory=list)
    status: EntryStatus | None = None


class EntryFieldResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fieldId: str = Field(alias="field_id")
    value: Any = None
    source: str
    fhirSourceRef: str | None = Field(default=None, alias="fhir_source_ref")
    updatedAt: datetime | None = Field(default=None, alias="updated_at")

    @field_validator("fieldId", mode="before")
    @classmethod
    def _id(cls, v): return _to_str(v)


class EntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    formId: str = Field(alias="form_id")
    participantId: str = Field(alias="participant_id")
    status: str
    completedAt: datetime | None = Field(default=None, alias="completed_at")
    lockedAt: datetime | None = Field(default=None, alias="locked_at")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    values: list[EntryFieldResponse] = Field(default_factory=list)
    signatures: list["SignatureResponse"] = Field(default_factory=list)

    @field_validator("id", "formId", "participantId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


class SignatureCreate(BaseModel):
    meaning: SignatureMeaning = "author"
    # We require re-auth via password OR a simple confirmation phrase. Per
    # 21 CFR 11.200, the user must execute a deliberate action; the
    # frontend sends the typed phrase here and we record it (hashed).
    confirmation: str = "I agree"


class SignatureResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    userId: str = Field(alias="user_id")
    meaning: str
    signatureHash: str = Field(alias="signature_hash")
    signedAt: datetime = Field(alias="signed_at")

    @field_validator("id", "userId", mode="before")
    @classmethod
    def _ids(cls, v): return _to_str(v)


class EntryHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fieldId: str = Field(alias="field_id")
    fieldKey: str
    oldValue: Any = None
    newValue: Any = None
    oldSource: str | None = None
    newSource: str | None = None
    changedBy: str | None = None
    reason: str | None = None
    changedAt: datetime


class FhirPullResult(BaseModel):
    field_id: str
    field_key: str
    value: Any = None
    source_ref: str | None = None
    error: str | None = None


EntryResponse.model_rebuild()
