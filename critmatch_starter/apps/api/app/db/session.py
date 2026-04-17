import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_database_url = os.getenv("DATABASE_URL", "")

# Render provides postgres:// but SQLAlchemy 2.x requires postgresql://
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _database_url.startswith("postgresql://"):
    _database_url = _database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(_database_url) if _database_url else None
SessionLocal = sessionmaker(bind=engine) if engine else None


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
