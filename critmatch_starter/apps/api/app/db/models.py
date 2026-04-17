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
