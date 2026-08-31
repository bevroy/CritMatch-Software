"""CritMatch background worker.

Polls ``query_runs`` for queued work and executes each one against the
configured FHIR server. Designed to run as a single instance per
environment; uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so multiple
workers can be added later without code changes.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from sqlalchemy import select

# The worker shares code with the API. We expect the API package to be
# available on PYTHONPATH (Docker image copies apps/api into /app/api_app).
sys.path.insert(0, os.environ.get("API_APP_PATH", "/app/api_app"))

from app.db.models import QueryRun  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.fhir.client import FHIRRateLimitedError  # noqa: E402
from app.services.query_runner import QueryExecutionError, run_query  # noqa: E402

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("critmatch.worker")


def _claim_next_run() -> str | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        stmt = (
            select(QueryRun)
            .where(QueryRun.status == "queued")
            .order_by(QueryRun.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        run = session.execute(stmt).scalar_one_or_none()
        if run is None:
            return None
        run.status = "claimed"
        session.commit()
        return str(run.id)


def _process(run_id: str) -> None:
    if SessionLocal is None:
        return
    with SessionLocal() as session:
        try:
            count = run_query(session, run_id)
            log.info("run %s completed (%d matches)", run_id, count)
        except QueryExecutionError as exc:
            # run_query() wraps every failure in QueryExecutionError, so the
            # original FHIRRateLimitedError (if any) survives on __cause__.
            # A 429 means "the server asked us to back off", not "this run
            # is permanently broken" - surface that distinction in logs even
            # though there's no retry queue yet to act on it.
            if isinstance(exc.__cause__, FHIRRateLimitedError):
                log.warning(
                    "run %s rate-limited by FHIR server (retry_after=%s); "
                    "marking failed for now, no retry queue yet: %s",
                    run_id,
                    exc.__cause__.retry_after,
                    exc,
                )
            else:
                log.exception("run %s failed: %s", run_id, exc)


def main() -> None:
    interval = int(os.getenv("JOB_POLL_INTERVAL_SECONDS", "5"))
    log.info("CritMatch worker started; poll interval=%ss", interval)
    while True:
        try:
            run_id = _claim_next_run()
            if run_id:
                _process(run_id)
                continue
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("Worker loop error")
        time.sleep(interval)


if __name__ == "__main__":
    main()
