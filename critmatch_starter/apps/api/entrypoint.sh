#!/bin/sh
set -e

if [ -n "$DATABASE_URL" ]; then
  # If the schema already exists (from a pre-Alembic bootstrap) but the
  # alembic_version table is missing, stamp the baseline so we don't try
  # to re-create tables.
  python - <<'PY'
import os, sys
from sqlalchemy import create_engine, inspect

url = os.environ["DATABASE_URL"]
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://") and "+psycopg" not in url:
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(url)
insp = inspect(engine)
tables = set(insp.get_table_names())
if "alembic_version" not in tables and "users" in tables:
    print("Existing schema detected without alembic_version; will stamp baseline.")
    sys.exit(2)
sys.exit(0)
PY
  rc=$?
  if [ "$rc" = "2" ]; then
    alembic stamp 0001_initial
  elif [ "$rc" != "0" ]; then
    echo "DB inspection failed (exit $rc)"
    exit "$rc"
  fi

  echo "Running alembic migrations..."
  alembic upgrade head
else
  echo "DATABASE_URL not set; skipping migrations."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
