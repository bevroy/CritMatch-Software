"""Pytest fixtures.

Tests run against an in-memory SQLite database. We register custom
type compilers so the existing Postgres-typed models (UUID, JSONB)
compile against the sqlite dialect.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


# Make postgresql.UUID(as_uuid=True) bind/return strings on sqlite without
# touching the production models.
def _uuid_bind_processor(self, dialect):  # noqa: ANN001
    if dialect.name != "sqlite":
        return _orig_bind(self, dialect)

    def process(value):
        if value is None:
            return None
        return str(value)

    return process


def _uuid_result_processor(self, dialect, coltype):  # noqa: ANN001
    if dialect.name != "sqlite":
        return _orig_result(self, dialect, coltype)

    def process(value):
        if value is None:
            return None
        return uuid.UUID(value) if self.as_uuid else value

    return process


_orig_bind = UUID.bind_processor
_orig_result = UUID.result_processor
UUID.bind_processor = _uuid_bind_processor  # type: ignore[assignment]
UUID.result_processor = _uuid_result_processor  # type: ignore[assignment]


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret-please-change")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("FRONTEND_BASE_URL", "http://localhost:3000")

# sqlite3 doesn't know how to bind UUID/dict natively
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))
sqlite3.register_adapter(dict, lambda d: json.dumps(d))
sqlite3.register_adapter(list, lambda v: json.dumps(v))


@pytest.fixture()
def db_session() -> Iterator:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import models, session as session_module

    # StaticPool keeps a single connection so the in-memory DB survives across sessions.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session_module.engine = engine
    session_module.SessionLocal = SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def authed_user(db_session):
    from app.db.models import User

    user = User(id=uuid.uuid4(), ehr_user_id="test-ehr-user", name="Test User", role="research_user")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def authed_client(client, authed_user):
    from app.core.config import get_settings
    from app.core.security import issue_session_token

    token = issue_session_token({"sub": str(authed_user.id), "role": authed_user.role})
    client.cookies.set(get_settings().session_cookie_name, token)
    return client
