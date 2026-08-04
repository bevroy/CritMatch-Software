"""Tests for the EDC module."""

from __future__ import annotations

import uuid
from typing import Any


class FakeFHIR:
    """Tiny FHIR stand-in compatible with edc_fhir.pull_field_value."""

    def __init__(self, resources: dict[str, list[dict[str, Any]]] | None = None,
                 reads: dict[str, dict[str, Any]] | None = None) -> None:
        self._resources = resources or {}
        self._reads = reads or {}

    def search(self, resource_type, params=None, *, page_limit=20, on_limit="raise"):
        _ = on_limit
        for r in self._resources.get(resource_type, []):
            yield r

    def read(self, ref):
        if ref in self._reads:
            return self._reads[ref]
        raise RuntimeError(f"no fake for {ref}")

    def close(self): pass


def _make_study(db, owner_id):
    from app.db.models import Study
    s = Study(id=uuid.uuid4(), name="Trial X", owner_user_id=owner_id, status="active")
    db.add(s)
    db.commit()
    return s


def _install_fake(client, fake):
    from app.main import app
    app.state.edc_fhir_client = fake


# ---------------------------------------------------------------------------


def test_create_form_and_field(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    payload = {
        "study_id": str(study.id),
        "name": "Baseline visit",
        "description": "v1",
        "fields": [
            {"key": "sbp", "label": "Systolic BP", "item_type": "integer", "required": True,
             "fhir_mapping_json": {"resource": "Observation", "params": {"code": "8480-6"},
                                    "extract": "valueQuantity.value"}},
            {"key": "consent", "label": "Consented?", "item_type": "boolean"},
        ],
    }
    r = authed_client.post("/api/edc/forms", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["study_id"] == str(study.id)
    assert body["status"] == "draft"
    assert len(body["fields"]) == 2
    assert body["fields"][0]["fhir_mapping_json"]["params"]["code"] == "8480-6"


def test_form_list_and_update_replaces_fields(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    r = authed_client.post(
        "/api/edc/forms",
        json={"study_id": str(study.id), "name": "F1", "fields": [{"key": "a", "label": "A"}]},
    )
    fid = r.json()["id"]

    r = authed_client.get(f"/api/edc/forms?studyId={study.id}")
    assert r.status_code == 200
    assert any(f["id"] == fid for f in r.json())

    r = authed_client.patch(
        f"/api/edc/forms/{fid}",
        json={"fields": [{"key": "b", "label": "B"}, {"key": "c", "label": "C"}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [f["key"] for f in body["fields"]] == ["b", "c"]
    assert body["version"] == 2  # bumped on field replacement


def test_participant_create_and_promote(authed_client, db_session, authed_user):
    from app.db.models import CriteriaSet, QueryRun, QueryResult
    study = _make_study(db_session, authed_user.id)

    # Manual create
    r = authed_client.post(
        f"/api/studies/{study.id}/participants",
        json={"patient_id": "pat-1", "subject_id": "S-001", "status": "enrolled"},
    )
    assert r.status_code == 201, r.text
    p1 = r.json()
    assert p1["status"] == "enrolled"
    assert p1["enrolled_at"] is not None
    assert p1["source"] == "manual"

    # Set up a QueryRun + results to promote.
    cs = CriteriaSet(
        id=uuid.uuid4(), study_id=study.id, version=1,
        logic_json={"operator": "AND", "rules": []},
    )
    db_session.add(cs)
    db_session.commit()
    run = QueryRun(id=uuid.uuid4(), study_id=study.id, criteria_set_id=cs.id, status="complete")
    db_session.add(run)
    db_session.add(QueryResult(id=uuid.uuid4(), query_run_id=run.id, patient_id="pat-2"))
    db_session.add(QueryResult(id=uuid.uuid4(), query_run_id=run.id, patient_id="pat-3"))
    db_session.commit()

    r = authed_client.post(
        f"/api/studies/{study.id}/participants/promote",
        json={"run_id": str(run.id), "patient_ids": ["pat-2", "pat-3"], "subject_id_prefix": "T"},
    )
    assert r.status_code == 200, r.text
    promoted = r.json()
    assert len(promoted) == 2
    assert {p["patient_id"] for p in promoted} == {"pat-2", "pat-3"}
    assert all(p["source"] == "cohort_promotion" for p in promoted)
    assert all(p["subject_id"].startswith("T-") for p in promoted)

    # List
    r = authed_client.get(f"/api/studies/{study.id}/participants")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_entry_lifecycle_and_history(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    r = authed_client.post(
        "/api/edc/forms",
        json={"study_id": str(study.id), "name": "F", "fields": [
            {"key": "weight", "label": "Weight", "item_type": "decimal"},
            {"key": "notes", "label": "Notes", "item_type": "text"},
        ]},
    )
    form = r.json()
    fid = form["id"]
    field_weight = form["fields"][0]["id"]
    field_notes = form["fields"][1]["id"]

    r = authed_client.post(
        f"/api/studies/{study.id}/participants",
        json={"patient_id": "pat-1", "subject_id": "S-001"},
    )
    pid = r.json()["id"]

    r = authed_client.post(f"/api/edc/forms/{fid}/entries", json={"participant_id": pid})
    assert r.status_code == 201, r.text
    entry = r.json()
    eid = entry["id"]
    assert entry["status"] == "in_progress"

    # First write
    r = authed_client.patch(
        f"/api/edc/entries/{eid}",
        json={"values": [
            {"field_id": field_weight, "value": 70.5},
            {"field_id": field_notes, "value": "baseline ok"},
        ]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    by_field = {v["field_id"]: v for v in body["values"]}
    assert by_field[field_weight]["value"] == 70.5
    assert by_field[field_weight]["source"] == "manual"

    # Update one field with reason
    r = authed_client.patch(
        f"/api/edc/entries/{eid}",
        json={"values": [
            {"field_id": field_weight, "value": 71.2, "reason_for_change": "data entry error"},
        ]},
    )
    assert r.status_code == 200

    # History should have 3 rows: weight initial, notes initial, weight update.
    r = authed_client.get(f"/api/edc/entries/{eid}/history")
    assert r.status_code == 200
    hist = r.json()
    assert len(hist) == 3
    weight_changes = [h for h in hist if h["fieldKey"] == "weight"]
    assert any(h["reason"] == "data entry error" for h in weight_changes)


def test_fhir_pull_populates_fields(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    r = authed_client.post(
        "/api/edc/forms",
        json={"study_id": str(study.id), "name": "F", "fields": [
            {"key": "sbp", "label": "SBP", "item_type": "integer",
             "fhir_mapping_json": {"resource": "Observation", "params": {"code": "8480-6"},
                                    "extract": "valueQuantity.value"}},
            {"key": "dob", "label": "DOB", "item_type": "date",
             "fhir_mapping_json": {"resource": "Patient", "extract": "birthDate"}},
        ]},
    )
    form = r.json()
    fid = form["id"]
    field_sbp = form["fields"][0]["id"]

    r = authed_client.post(
        f"/api/studies/{study.id}/participants",
        json={"patient_id": "pat-42", "subject_id": "S-042"},
    )
    pid = r.json()["id"]

    r = authed_client.post(f"/api/edc/forms/{fid}/entries", json={"participant_id": pid})
    eid = r.json()["id"]

    fake = FakeFHIR(
        resources={
            "Observation": [
                {"resourceType": "Observation", "id": "obs-1",
                 "valueQuantity": {"value": 132, "unit": "mm[Hg]"}},
            ],
        },
        reads={
            "Patient/pat-42": {"resourceType": "Patient", "id": "pat-42", "birthDate": "1965-04-12"},
        },
    )
    _install_fake(authed_client, fake)

    r = authed_client.post(f"/api/edc/entries/{eid}/pull")
    assert r.status_code == 200, r.text
    pulled = r.json()
    assert len(pulled) == 2
    by_key = {p["field_key"]: p for p in pulled}
    assert by_key["sbp"]["value"] == 132
    assert by_key["sbp"]["source_ref"] == "Observation/obs-1"
    assert by_key["dob"]["value"] == "1965-04-12"

    # Re-fetch entry; values should now be present with source=fhir_pull.
    r = authed_client.get(f"/api/edc/entries/{eid}")
    assert r.status_code == 200
    by_field = {v["field_id"]: v for v in r.json()["values"]}
    assert by_field[field_sbp]["value"] == 132
    assert by_field[field_sbp]["source"] == "fhir_pull"


def test_sign_locks_entry(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    r = authed_client.post(
        "/api/edc/forms",
        json={"study_id": str(study.id), "name": "F", "fields": [
            {"key": "x", "label": "X", "item_type": "string"},
        ]},
    )
    fid = r.json()["id"]
    field_x = r.json()["fields"][0]["id"]
    r = authed_client.post(
        f"/api/studies/{study.id}/participants",
        json={"patient_id": "pat-1", "subject_id": "S-001"},
    )
    pid = r.json()["id"]
    r = authed_client.post(f"/api/edc/forms/{fid}/entries", json={"participant_id": pid})
    eid = r.json()["id"]

    authed_client.patch(f"/api/edc/entries/{eid}", json={"values": [{"field_id": field_x, "value": "hello"}]})

    # Cannot sign while in_progress
    r = authed_client.post(f"/api/edc/entries/{eid}/sign", json={})
    assert r.status_code == 409

    # Mark complete then sign
    r = authed_client.patch(f"/api/edc/entries/{eid}", json={"values": [], "status": "complete"})
    assert r.status_code == 200
    r = authed_client.post(f"/api/edc/entries/{eid}/sign", json={"meaning": "author", "confirmation": "I agree"})
    assert r.status_code == 201, r.text
    sig = r.json()
    assert sig["meaning"] == "author"
    assert len(sig["signature_hash"]) == 64

    # Signing should have locked the entry
    r = authed_client.get(f"/api/edc/entries/{eid}")
    assert r.json()["status"] == "locked"

    # Further updates blocked
    r = authed_client.patch(f"/api/edc/entries/{eid}", json={"values": [{"field_id": field_x, "value": "no"}]})
    assert r.status_code == 409


def test_cross_study_participant_rejected(authed_client, db_session, authed_user):
    study_a = _make_study(db_session, authed_user.id)
    study_b = _make_study(db_session, authed_user.id)
    r = authed_client.post("/api/edc/forms", json={"study_id": str(study_a.id), "name": "FA"})
    fid = r.json()["id"]
    r = authed_client.post(
        f"/api/studies/{study_b.id}/participants",
        json={"patient_id": "p", "subject_id": "S-B-001"},
    )
    pid = r.json()["id"]
    r = authed_client.post(f"/api/edc/forms/{fid}/entries", json={"participant_id": pid})
    assert r.status_code == 400


def test_unauth_blocked(client, db_session):
    r = client.get("/api/edc/forms")
    assert r.status_code == 401
