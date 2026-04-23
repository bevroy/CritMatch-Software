#!/bin/sh
set -e

# Run database migrations (idempotent) before starting the API.
if [ -n "$DATABASE_URL" ]; then
  echo "Running alembic migrations..."
  alembic upgrade head
else
  echo "DATABASE_URL not set; skipping migrations."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
