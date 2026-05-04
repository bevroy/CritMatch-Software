"""Tests for the study investigator scoping feature."""

from __future__ import annotations

import uuid
from typing import Any


class FakeFHIR:
    """In-memory FHIR stand-in supporting both list and parameterised search."""

    def __init__(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        self._resources = resources

    def search(self, resource_type: str, params=None, *, page_limit: int = 20):
        items = self._resources.get(resource_type, [])
        if resource_type == "Encounter" and params and "participant" in params:
            wanted = params["participant"]
            for r in items:
                participants = r.get("participant", []) or []
                refs = [(p.get("individual") or {}).get("reference") for p in participants]
                if wanted in refs:
                    yield r
            return
        for r in items:
            yield r

    def close(self) -> None:
        pass


def _condition(pid: str) -> dict:
    return {"resourceType": "Condition", "subject": {"reference": f"Patient/{pid}"}}


def _encounter(pid: str, practitioner_ref: str) -> dict:
    return {
        "resourceType": "Encounter",
        "subject": {"reference": f"Patient/{pid}"},
        "participant": [{"individual": {"reference": practitioner_ref}}],
    }


def _seed_study(db_session, owner_id):
    from app.db.models import Study

    study = Study(id=uuid.uuid4(), name="S", owner_user_id=owner_id)
    db_session.add(study)
    db_session.commit()
    return study


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_add_list_and_remove_investigator(authed_client, authed_user, db_session):
    study = _seed_study(db_session, authed_user.id)

    # initially empty
    listing = authed_client.get(f"/api/studies/{study.id}/investigators").json()
    assert listing["items"] == []

    add = authed_client.post(
        f"/api/studies/{study.id}/investigators",
        json={
            "practitioner_id": "prac-1",
            "name": "Dr. Alpha",
            "npi": "1234567890",
            "role": "principal_investigator",
        },
    )
    assert add.status_code == 200, add.text
    body = add.json()
    assert body["practitionerId"] == "prac-1"
    assert body["role"] == "principal_investigator"

    listing = authed_client.get(f"/api/studies/{study.id}/investigators").json()
    assert len(listing["items"]) == 1
    inv_id = listing["items"][0]["id"]

    # update role
    upd = authed_client.patch(
        f"/api/studies/{study.id}/investigators/{inv_id}",
        json={"role": "sub_investigator"},
    )
    assert upd.status_code == 200
    assert upd.json()["role"] == "sub_investigator"

    rm = authed_client.delete(f"/api/studies/{study.id}/investigators/{inv_id}")
    assert rm.status_code == 200
    assert authed_client.get(f"/api/studies/{study.id}/investigators").json()["items"] == []


def test_invalid_role_rejected(authed_client, authed_user, db_session):
    study = _seed_study(db_session, authed_user.id)
    resp = authed_client.post(
        f"/api/studies/{study.id}/investigators",
        json={"practitioner_id": "p", "role": "nurse"},
    )
    assert resp.status_code == 400


def test_other_user_cannot_see_investigators(authed_client, db_session):
    from app.db.models import Study, User

    other = User(id=uuid.uuid4(), name="Other", role="research_user")
    db_session.add(other)
    db_session.flush()
    study = Study(id=uuid.uuid4(), name="Theirs", owner_user_id=other.id)
    db_session.add(study)
    db_session.commit()

    resp = authed_client.get(f"/api/studies/{study.id}/investigators")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Engine integration: query_runner restricts to investigator-seen patients
# ---------------------------------------------------------------------------


def test_query_runner_scopes_to_investigator_patients(db_session, authed_user):
    from app.db.models import (
        CriteriaSet,
        QueryResult,
        QueryRun,
        Study,
        StudyInvestigator,
    )
    from app.services.query_runner import run_query

    study = Study(id=uuid.uuid4(), name="S", owner_user_id=authed_user.id)
    db_session.add(study)
    db_session.flush()
    db_session.add(
        StudyInvestigator(
            study_id=study.id,
            practitioner_id="prac-1",
            role="principal_investigator",
        )
    )
    cs = CriteriaSet(
        id=uuid.uuid4(),
        study_id=study.id,
        version=1,
        logic_json={
            "operator": "AND",
            "rules": [{"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]}],
        },
    )
    db_session.add(cs)
    db_session.flush()
    qr = QueryRun(
        id=uuid.uuid4(),
        study_id=study.id,
        criteria_set_id=cs.id,
        status="queued",
    )
    db_session.add(qr)
    db_session.commit()

    fake = FakeFHIR(
        {
            "Condition": [_condition("p1"), _condition("p2"), _condition("p3")],
            # Only p1 and p3 have an encounter with prac-1; p2 does not.
            "Encounter": [
                _encounter("p1", "Practitioner/prac-1"),
                _encounter("p3", "Practitioner/prac-1"),
                _encounter("p2", "Practitioner/other"),
            ],
        }
    )

    count = run_query(db_session, str(qr.id), fhir_client=fake)
    assert count == 2
    pids = {
        row.patient_id
        for row in db_session.query(QueryResult)
        .filter(QueryResult.query_run_id == qr.id)
        .all()
    }
    assert pids == {"p1", "p3"}


def test_query_runner_unrestricted_when_no_investigators(db_session, authed_user):
    from app.db.models import CriteriaSet, QueryRun, Study
    from app.services.query_runner import run_query

    study = Study(id=uuid.uuid4(), name="S", owner_user_id=authed_user.id)
    db_session.add(study)
    db_session.flush()
    cs = CriteriaSet(
        id=uuid.uuid4(),
        study_id=study.id,
        version=1,
        logic_json={
            "operator": "AND",
            "rules": [{"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]}],
        },
    )
    db_session.add(cs)
    db_session.flush()
    qr = QueryRun(
        id=uuid.uuid4(),
        study_id=study.id,
        criteria_set_id=cs.id,
        status="queued",
    )
    db_session.add(qr)
    db_session.commit()

    fake = FakeFHIR(
        {
            "Condition": [_condition("p1"), _condition("p2")],
            "Encounter": [],
        }
    )
    count = run_query(db_session, str(qr.id), fhir_client=fake)
    assert count == 2  # no restriction since study has no investigators


# ---------------------------------------------------------------------------
# Engine integration: feasibility engine respects investigator scoping
# ---------------------------------------------------------------------------


def test_feasibility_run_scopes_to_investigators(authed_client, authed_user, db_session):
    from app.db.models import Study, StudyInvestigator
    from app.main import app

    study = Study(id=uuid.uuid4(), name="S", owner_user_id=authed_user.id)
    db_session.add(study)
    db_session.flush()
    db_session.add(
        StudyInvestigator(
            study_id=study.id,
            practitioner_id="prac-1",
            role="principal_investigator",
        )
    )
    db_session.commit()

    create = authed_client.post(
        "/api/feasibility/questionnaires",
        json={
            "name": "Scoped feasibility",
            "studyId": str(study.id),
            "questions": [
                {
                    "text": "Has E11",
                    "logic_json": {
                        "operator": "AND",
                        "rules": [
                            {"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]}
                        ],
                    },
                }
            ],
        },
    )
    assert create.status_code == 200, create.text
    qid = create.json()["id"]

    app.state.feasibility_fhir_client = FakeFHIR(
        {
            "Condition": [_condition("p1"), _condition("p2"), _condition("p3")],
            "Encounter": [
                _encounter("p1", "Practitioner/prac-1"),
                _encounter("p2", "Practitioner/other"),
            ],
        }
    )

    resp = authed_client.post(f"/api/feasibility/questionnaires/{qid}/run")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["totalPatients"] == 1  # only p1 qualifies
    assert body["results"][0]["count"] == 1
