import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
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
