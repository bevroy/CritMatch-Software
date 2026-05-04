"""Feasibility engine: answer aggregate questions about the EMR.

A feasibility questionnaire is a list of questions a researcher would
typically answer on a study feasibility form, e.g.:

  - "How many adult patients with type 2 diabetes do you see?"
  - "How many of those are also on metformin?"
  - "How many had a HbA1c > 7 in the last year?"

For each question we evaluate a small criteria block (same shape as
``criteria_sets.logic_json``) against the configured FHIR server and
return the **count of distinct patients** that satisfy it. We never
persist the patient ids — feasibility is an aggregate workflow and
keeping it aggregate-only avoids enlarging the PHI surface.

The engine reuses :class:`app.services.query_runner.QueryExecutor` so
rule evaluation stays consistent with the cohort matcher.
"""

from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    FeasibilityQuestion,
    FeasibilityQuestionnaire,
    FeasibilityResult,
    FeasibilityRun,
)
from app.fhir.client import FHIRClient
from app.services.query_runner import QueryExecutor


class FeasibilityExecutionError(RuntimeError):
    pass


def _evaluate_question(
    executor: QueryExecutor,
    logic: dict[str, Any],
    allowed_patients: set[str] | None,
) -> tuple[int, set[str]]:
    """Return ``(count_of_distinct_patients, patient_id_set)``.

    ``allowed_patients`` is the set of patient ids that have at least one
    Encounter with one of the study's investigators. ``None`` means no
    restriction is in effect.
    """
    matches = executor.execute(logic or {})
    pids = set(matches.keys())
    if allowed_patients is not None:
        pids &= allowed_patients
    return len(pids), pids


def run_feasibility(
    db: Session,
    run_id: str,
    *,
    fhir_client: FHIRClient | None = None,
) -> int:
    """Execute a feasibility run; persist per-question counts.

    Returns the total number of distinct patients across all questions
    (the union). This number is also stored on ``FeasibilityRun.total_patients``
    so the UI can show a headline figure.
    """

    fr = db.get(FeasibilityRun, run_id)
    if fr is None:
        raise FeasibilityExecutionError(f"FeasibilityRun {run_id} not found")
    if fr.status == "cancelled":
        return 0

    questionnaire = db.get(FeasibilityQuestionnaire, fr.questionnaire_id)
    if questionnaire is None:
        raise FeasibilityExecutionError("Questionnaire missing for run")

    questions: list[FeasibilityQuestion] = sorted(
        questionnaire.questions, key=lambda q: q.position
    )

    fr.status = "running"
    db.commit()

    started = time.monotonic()
    owns_client = False
    client = fhir_client
    try:
        if client is None:
            client = FHIRClient(
                os.getenv("FHIR_BASE_URL", ""),
                os.getenv("FHIR_ACCESS_TOKEN"),
            )
            owns_client = True

        executor = QueryExecutor(client)

        # Apply investigator scoping when the questionnaire is attached to a
        # study with PI / Sub-I rows.
        from app.services.investigators import (
            allowed_patient_ids,
            list_practitioner_refs,
        )

        allowed: set[str] | None = None
        if questionnaire.study_id is not None:
            practitioner_refs = list_practitioner_refs(db, questionnaire.study_id)
            allowed = allowed_patient_ids(client, practitioner_refs)

        # Wipe any prior results then write fresh.
        db.query(FeasibilityResult).filter(FeasibilityResult.run_id == fr.id).delete()

        union_patients: set[str] = set()
        for question in questions:
            count, pids = _evaluate_question(executor, question.logic_json or {}, allowed)
            union_patients.update(pids)
            db.add(
                FeasibilityResult(
                    run_id=fr.id,
                    question_id=question.id,
                    count=count,
                    detail_json={"sample": sorted(list(pids))[:5]} if pids else None,
                )
            )

        fr.total_patients = len(union_patients)
        fr.execution_ms = int((time.monotonic() - started) * 1000)
        fr.status = "completed"
        db.commit()
        return fr.total_patients
    except Exception as exc:  # noqa: BLE001
        fr.execution_ms = int((time.monotonic() - started) * 1000)
        fr.status = "failed"
        fr.error_message = str(exc)[:500]
        db.commit()
        raise FeasibilityExecutionError(str(exc)) from exc
    finally:
        if owns_client and client is not None:
            client.close()


__all__ = ["run_feasibility", "FeasibilityExecutionError"]
