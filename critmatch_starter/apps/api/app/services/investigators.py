"""Investigator-scoped patient filtering.

When a study lists Principal or Sub-Investigators, both the cohort matcher
and the feasibility engine restrict results to patients who have an
``Encounter`` with at least one of those practitioners as a participant.
This makes multi-provider sites able to scope research searches to the
slice of the EMR that's actually under their study team's care.
"""

from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models import StudyInvestigator
from app.fhir.client import FHIRClient

# Roles considered eligible to drive cohort scoping.
INVESTIGATOR_ROLES = {"principal_investigator", "sub_investigator"}


def list_practitioner_refs(db: Session, study_id: uuid.UUID) -> list[str]:
    """Return the FHIR ``Practitioner/{id}`` references for a study."""
    rows = (
        db.query(StudyInvestigator)
        .filter(StudyInvestigator.study_id == study_id)
        .all()
    )
    refs: list[str] = []
    for row in rows:
        pid = (row.practitioner_id or "").strip()
        if not pid:
            continue
        if "/" not in pid:
            pid = f"Practitioner/{pid}"
        refs.append(pid)
    return refs


def _patient_id_from_subject(reference: str | None) -> str | None:
    if not reference:
        return None
    if "Patient/" in reference:
        return reference.split("Patient/", 1)[1].split("?")[0]
    return None


def allowed_patient_ids(
    client: FHIRClient, practitioner_refs: Iterable[str]
) -> set[str] | None:
    """Patients seen by any of the supplied practitioners.

    Returns ``None`` when no practitioners are supplied — meaning "do not
    restrict". An empty ``set()`` means restriction is in effect but no
    patients qualify (callers should treat that as "no matches").
    """
    refs = [r for r in practitioner_refs if r]
    if not refs:
        return None

    allowed: set[str] = set()
    for ref in refs:
        for encounter in client.search("Encounter", {"participant": ref}):
            pid = _patient_id_from_subject(
                (encounter.get("subject") or {}).get("reference")
            )
            if pid:
                allowed.add(pid)
    return allowed


__all__ = [
    "INVESTIGATOR_ROLES",
    "allowed_patient_ids",
    "list_practitioner_refs",
]
