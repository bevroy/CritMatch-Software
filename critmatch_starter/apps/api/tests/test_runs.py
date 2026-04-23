"""Tests for run results + signed CSV export."""

from __future__ import annotations

import os
import uuid

os.environ["EXPORT_SIGNING_KEY"] = "test-export-key"


def _seed_completed_run(db_session, owner_id):
    from app.db.models import CriteriaSet, QueryResult, QueryRun, Study

    study = Study(id=uuid.uuid4(), name="S", owner_user_id=owner_id)
    db_session.add(study)
    db_session.flush()
    cs = CriteriaSet(id=uuid.uuid4(), study_id=study.id, version=1, logic_json={})
    db_session.add(cs)
    db_session.flush()
    qr = QueryRun(
        id=uuid.uuid4(),
        study_id=study.id,
        criteria_set_id=cs.id,
        status="completed",
        result_count=2,
        execution_ms=10,
    )
    db_session.add(qr)
    db_session.add(
        QueryResult(query_run_id=qr.id, patient_id="p1", mrn_hash="h1", matched_rules_json={"rules": ["r1"]}, primary_match_reason="r1")
    )
    db_session.add(
        QueryResult(query_run_id=qr.id, patient_id="p2", mrn_hash="h2", matched_rules_json={"rules": ["r1"]}, primary_match_reason="r1")
    )
    db_session.commit()
    return qr


def test_results_listing_and_export(authed_client, authed_user, db_session):
    qr = _seed_completed_run(db_session, authed_user.id)

    listing = authed_client.get(f"/api/runs/{qr.id}/results")
    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    assert len(listing.json()["items"]) == 2

    link_resp = authed_client.post(f"/api/runs/{qr.id}/export")
    assert link_resp.status_code == 200, link_resp.text
    download_path = link_resp.json()["downloadPath"]
    assert "sig=" in download_path

    # Anonymous client can fetch with valid signature
    csv_resp = authed_client.get(download_path)
    assert csv_resp.status_code == 200
    body = csv_resp.text.splitlines()
    assert body[0] == "patient_id,mrn_hash,primary_match_reason,matched_rules"
    assert any("p1,h1,r1,r1" in line for line in body)


def test_export_link_rejects_tampered_signature(authed_client, authed_user, db_session):
    qr = _seed_completed_run(db_session, authed_user.id)
    link = authed_client.post(f"/api/runs/{qr.id}/export").json()["downloadPath"]
    tampered = link.replace("sig=", "sig=00")
    resp = authed_client.get(tampered)
    assert resp.status_code == 403
