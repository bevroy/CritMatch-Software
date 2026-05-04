import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ehr_user_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="research_user")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    studies: Mapped[list["Study"]] = relationship(back_populates="owner")


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped[User | None] = relationship(back_populates="studies")
    criteria_sets: Mapped[list["CriteriaSet"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    collaborators: Mapped[list["StudyCollaborator"]] = relationship(
        back_populates="study", cascade="all, delete-orphan"
    )


class StudyCollaborator(Base):
    __tablename__ = "study_collaborators"
    __table_args__ = (UniqueConstraint("study_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    study: Mapped[Study] = relationship(back_populates="collaborators")
    user: Mapped[User] = relationship()


class StudyInvestigator(Base):
    """A PI or Sub-Investigator participating in a study.

    ``practitioner_id`` is the FHIR ``Practitioner`` resource id on the
    configured server. The matching/feasibility engines use this set to
    optionally restrict cohort searches to patients seen by these providers
    (typically by walking ``Encounter.participant`` references).
    """

    __tablename__ = "study_investigators"
    __table_args__ = (UniqueConstraint("study_id", "practitioner_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studies.id", ondelete="CASCADE"), nullable=False
    )
    practitioner_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    npi: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="sub_investigator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    study: Mapped[Study] = relationship()


class CriteriaSet(Base):
    __tablename__ = "criteria_sets"
    __table_args__ = (UniqueConstraint("study_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    logic_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    study: Mapped[Study] = relationship(back_populates="criteria_sets")


class TerminologyExpansion(Base):
    __tablename__ = "terminology_expansions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    criteria_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("criteria_sets.id", ondelete="CASCADE"), nullable=False)
    source_term: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_term: Mapped[str | None] = mapped_column(Text)
    expansion_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class QueryRun(Base):
    __tablename__ = "query_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    criteria_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("criteria_sets.id", ondelete="CASCADE"), nullable=False)
    run_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    result_count: Mapped[int | None] = mapped_column(Integer)
    execution_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    results: Mapped[list["QueryResult"]] = relationship(back_populates="query_run", cascade="all, delete-orphan")


class QueryResult(Base):
    __tablename__ = "query_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False)
    mrn_hash: Mapped[str | None] = mapped_column(Text)
    matched_rules_json: Mapped[dict | None] = mapped_column(JSONB)
    primary_match_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    query_run: Mapped[QueryRun] = relationship(back_populates="results")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Feasibility module
#
# A feasibility "questionnaire" is a collection of questions a researcher
# would typically answer on a study feasibility form (e.g. "How many adult
# patients with type 2 diabetes do you see per year?"). Each question is
# evaluated against the EMR via FHIR and produces an aggregate count — the
# module deliberately does NOT persist patient ids, since feasibility is an
# aggregate workflow and aggregate-only avoids new PHI surface area.
# ---------------------------------------------------------------------------


class FeasibilityQuestionnaire(Base):
    __tablename__ = "feasibility_questionnaires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("studies.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    questions: Mapped[list["FeasibilityQuestion"]] = relationship(
        back_populates="questionnaire",
        cascade="all, delete-orphan",
        order_by="FeasibilityQuestion.position",
    )
    runs: Mapped[list["FeasibilityRun"]] = relationship(
        back_populates="questionnaire", cascade="all, delete-orphan"
    )


class FeasibilityQuestion(Base):
    __tablename__ = "feasibility_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feasibility_questionnaires.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # logic_json shape mirrors a CriteriaSet but at single-question granularity:
    # {"operator": "AND", "rules": [...]}  (rules.kind in condition|observation|
    # medication|demographic). See services/feasibility_engine.py.
    logic_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    questionnaire: Mapped[FeasibilityQuestionnaire] = relationship(back_populates="questions")


class FeasibilityRun(Base):
    __tablename__ = "feasibility_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feasibility_questionnaires.id", ondelete="CASCADE"), nullable=False
    )
    run_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    total_patients: Mapped[int | None] = mapped_column(Integer)
    execution_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    questionnaire: Mapped[FeasibilityQuestionnaire] = relationship(back_populates="runs")
    results: Mapped[list["FeasibilityResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class FeasibilityResult(Base):
    __tablename__ = "feasibility_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feasibility_runs.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feasibility_questions.id", ondelete="CASCADE"), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    run: Mapped[FeasibilityRun] = relationship(back_populates="results")


# ---------------------------------------------------------------------------
# EDC (Electronic Data Capture) module
#
# Researchers design forms made of typed fields (FHIR Questionnaire-style
# item types). Patients are enrolled as study participants (manually or
# promoted from a cohort run). For each (form, participant) pair an
# ``EdcEntry`` is created; field values can be entered by hand or pulled
# from the EMR via per-field FHIR mappings. Every value change is recorded
# in ``EdcEntryFieldHistory`` with a reason-for-change, and a completed
# entry can carry one or more ``EdcSignature`` rows for 21 CFR Part 11.
# ---------------------------------------------------------------------------


class EdcForm(Base):
    __tablename__ = "edc_forms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # draft | active | locked
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    fields: Mapped[list["EdcField"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="EdcField.position",
    )


class EdcField(Base):
    __tablename__ = "edc_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edc_forms.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # stable machine-readable identifier within the form (e.g. "systolic_bp")
    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # FHIR Questionnaire item.type: string | text | integer | decimal |
    # boolean | date | dateTime | time | choice | open-choice | quantity |
    # attachment | group | display
    item_type: Mapped[str] = mapped_column(Text, nullable=False, default="string")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # answerOptions / units / etc.
    options_json: Mapped[dict | None] = mapped_column(JSONB)
    # Per-field FHIR mapping. Shape:
    # {"resource": "Observation", "params": {"code": "8480-6"},
    #  "extract": "valueQuantity.value", "unit": "mm[Hg]"}
    fhir_mapping_json: Mapped[dict | None] = mapped_column(JSONB)
    validation_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    form: Mapped[EdcForm] = relationship(back_populates="fields")


class StudyParticipant(Base):
    __tablename__ = "study_participants"
    __table_args__ = (
        UniqueConstraint("study_id", "subject_id", name="uq_study_participants_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studies.id", ondelete="CASCADE"), nullable=False
    )
    # FHIR Patient.id on the configured server.
    patient_id: Mapped[str] = mapped_column(Text, nullable=False)
    # Study-specific subject identifier shown to coordinators (e.g. "DM-001").
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    # screening | enrolled | withdrawn | completed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="screening")
    # manual | cohort_promotion
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("query_runs.id", ondelete="SET NULL"), nullable=True
    )
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime)
    enrolled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EdcEntry(Base):
    __tablename__ = "edc_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edc_forms.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_participants.id", ondelete="CASCADE"), nullable=False
    )
    # in_progress | complete | locked
    status: Mapped[str] = mapped_column(Text, nullable=False, default="in_progress")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    field_values: Mapped[list["EdcEntryField"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    signatures: Mapped[list["EdcSignature"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class EdcEntryField(Base):
    __tablename__ = "edc_entry_fields"
    __table_args__ = (
        UniqueConstraint("entry_id", "field_id", name="uq_edc_entry_fields_entry_field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edc_entries.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edc_fields.id", ondelete="CASCADE"), nullable=False
    )
    # Always wrapped: {"value": <native>}
    value_json: Mapped[dict | None] = mapped_column(JSONB)
    # manual | fhir_pull
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    fhir_source_ref: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    entry: Mapped[EdcEntry] = relationship(back_populates="field_values")


class EdcEntryFieldHistory(Base):
    __tablename__ = "edc_entry_field_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edc_entry_fields.id", ondelete="CASCADE"), nullable=False
    )
    old_value_json: Mapped[dict | None] = mapped_column(JSONB)
    new_value_json: Mapped[dict | None] = mapped_column(JSONB)
    old_source: Mapped[str | None] = mapped_column(Text)
    new_source: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class EdcSignature(Base):
    __tablename__ = "edc_signatures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edc_entries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    # author | reviewer | approver
    meaning: Mapped[str] = mapped_column(Text, nullable=False, default="author")
    # HMAC over (entry snapshot + user + timestamp) using SESSION_SECRET.
    signature_hash: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    entry: Mapped[EdcEntry] = relationship(back_populates="signatures")


# ============================================================================
# CTFMS module — Clinical Trial Financial Management
# ============================================================================


class CtfmsBudget(Base):
    """One budget per study (versioned via the `version` column)."""
    __tablename__ = "ctfms_budgets"
    __table_args__ = (UniqueConstraint("study_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sponsor: Mapped[str | None] = mapped_column(Text)
    contract_number: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")  # draft | active | archived
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    items: Mapped[list["CtfmsBudgetItem"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class CtfmsBudgetItem(Base):
    """A line item in a budget; can be linked to an EDC form or specific field."""
    __tablename__ = "ctfms_budget_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ctfms_budgets.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # per_visit | per_procedure | fixed_milestone | passthrough | overhead | patient_stipend
    item_type: Mapped[str] = mapped_column(Text, nullable=False, default="per_visit")
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # minor units (cents)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    # Optional EDC trigger linkage
    edc_form_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edc_forms.id", ondelete="SET NULL")
    )
    edc_field_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edc_fields.id", ondelete="SET NULL")
    )
    # When True, an EDC entry signing produces an accrual automatically.
    auto_accrue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    budget: Mapped[CtfmsBudget] = relationship(back_populates="items")


class CtfmsAccrual(Base):
    """A revenue accrual: 'we have earned X for completing Y'."""
    __tablename__ = "ctfms_accruals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ctfms_budgets.id", ondelete="CASCADE"), nullable=False)
    budget_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ctfms_budget_items.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("study_participants.id", ondelete="SET NULL")
    )
    # Optional EDC source pointer (entry that triggered the accrual)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edc_entries.id", ondelete="SET NULL")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # snapshot
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # quantity * unit_price
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    # accrued | invoiced | void
    status: Mapped[str] = mapped_column(Text, nullable=False, default="accrued")
    invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ctfms_invoice_lines.id", ondelete="SET NULL", use_alter=True)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    accrued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    accrued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class CtfmsInvoice(Base):
    __tablename__ = "ctfms_invoices"
    __table_args__ = (UniqueConstraint("study_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    budget_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ctfms_budgets.id", ondelete="SET NULL")
    )
    number: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # draft | sent | partial | paid | void
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    lines: Mapped[list["CtfmsInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class CtfmsInvoiceLine(Base):
    __tablename__ = "ctfms_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ctfms_invoices.id", ondelete="CASCADE"), nullable=False
    )
    accrual_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ctfms_accruals.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    invoice: Mapped[CtfmsInvoice] = relationship(back_populates="lines")


class CtfmsPayment(Base):
    __tablename__ = "ctfms_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ctfms_invoices.id", ondelete="SET NULL")
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    method: Mapped[str | None] = mapped_column(Text)  # ach | wire | check | other
    reference: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class CtfmsStipend(Base):
    """A patient (participant) stipend owed for a visit/procedure."""
    __tablename__ = "ctfms_stipends"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_participants.id", ondelete="CASCADE"), nullable=False
    )
    budget_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ctfms_budget_items.id", ondelete="SET NULL")
    )
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edc_entries.id", ondelete="SET NULL")
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    # pending | paid | void
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    method: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
