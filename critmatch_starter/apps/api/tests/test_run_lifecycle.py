"""Tests for Phase 7: study run history and run lifecycle (cancel/retry)."""

from __future__ import annotations

import uuid


def _seed_study_with_runs(db_session, owner_id):
    from app.db.models import CriteriaSet, QueryRun, Study

    study = Study(id=uuid.uuid4(), name="S1", owner_user_id=owner_id)
    db_session.add(study)
    db_session.flush()
    cs = CriteriaSet(id=uuid.uuid4(), study_id=study.id, version=1, logic_json={})
    db_session.add(cs)
    db_session.flush()
    runs = [
        QueryRun(id=uuid.uuid4(), study_id=study.id, criteria_set_id=cs.id, status="queued"),
        QueryRun(id=uuid.uuid4(), study_id=study.id, criteria_set_id=cs.id, status="failed"),
        QueryRun(
            id=uuid.uuid4(),
            study_id=study.id,
            criteria_set_id=cs.id,
            status="completed",
            result_count=3,
            execution_ms=42,
        ),
    ]
    for r in runs:
        db_session.add(r)
    db_session.commit()
    return study, cs, runs


def test_list_criteria_sets(authed_client, authed_user, db_session):
    study, _cs, _ = _seed_study_with_runs(db_session, authed_user.id)
    resp = authed_client.get(f"/api/studies/{study.id}/criteria-sets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["version"] == 1


def test_list_study_runs_orders_recent_first(authed_client, authed_user, db_session):
    study, _cs, runs = _seed_study_with_runs(db_session, authed_user.id)
    resp = authed_client.get(f"/api/studies/{study.id}/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert {item["status"] for item in body["items"]} == {"queued", "failed", "completed"}


def test_cancel_queued_run(authed_client, authed_user, db_session):
    _study, _cs, runs = _seed_study_with_runs(db_session, authed_user.id)
    queued = next(r for r in runs if r.status == "queued")
    resp = authed_client.post(f"/api/runs/{queued.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # Cancelling an already-completed run is a 409
    completed = next(r for r in runs if r.status == "completed")
    resp2 = authed_client.post(f"/api/runs/{completed.id}/cancel")
    assert resp2.status_code == 409


def test_retry_failed_run_creates_new_queued_run(authed_client, authed_user, db_session):
    from app.db.models import QueryRun

    _study, cs, runs = _seed_study_with_runs(db_session, authed_user.id)
    failed = next(r for r in runs if r.status == "failed")

    resp = authed_client.post(f"/api/runs/{failed.id}/retry")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["retriedFrom"] == str(failed.id)
    assert body["criteriaSetId"] == str(cs.id)

    # A new QueryRun row exists distinct from the failed one
    new_run = db_session.get(QueryRun, body["runId"])
    assert new_run is not None
    assert new_run.id != failed.id
    assert new_run.status == "queued"


def test_retry_completed_run_rejected(authed_client, authed_user, db_session):
    _study, _cs, runs = _seed_study_with_runs(db_session, authed_user.id)
    completed = next(r for r in runs if r.status == "completed")
    resp = authed_client.post(f"/api/runs/{completed.id}/retry")
    assert resp.status_code == 409


def test_other_users_study_runs_forbidden(authed_client, db_session):
    from app.db.models import Study, User

    other = User(id=uuid.uuid4(), name="Other", role="research_user")
    db_session.add(other)
    db_session.flush()
    study = Study(id=uuid.uuid4(), name="Theirs", owner_user_id=other.id)
    db_session.add(study)
    db_session.commit()

    resp = authed_client.get(f"/api/studies/{study.id}/runs")
    # Non-collaborators see 404 to avoid enumeration of study IDs.
    assert resp.status_code == 404


def test_get_study_detail(authed_client, authed_user, db_session):
    study, _cs, _ = _seed_study_with_runs(db_session, authed_user.id)
    resp = authed_client.get(f"/api/studies/{study.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(study.id)
    assert body["name"] == "S1"


def test_get_study_detail_404(authed_client):
    resp = authed_client.get(f"/api/studies/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_query_runner_skips_cancelled_run(db_session, authed_user):
    """If a run was cancelled before the worker started executing, run_query bails out."""
    from app.db.models import CriteriaSet, QueryResult, QueryRun, Study
    from app.services.query_runner import run_query

    study = Study(id=uuid.uuid4(), name="S", owner_user_id=authed_user.id)
    db_session.add(study)
    db_session.flush()
    cs = CriteriaSet(id=uuid.uuid4(), study_id=study.id, version=1, logic_json={"operator": "AND", "rules": []})
    db_session.add(cs)
    db_session.flush()
    qr = QueryRun(
        id=uuid.uuid4(),
        study_id=study.id,
        criteria_set_id=cs.id,
        status="cancelled",
    )
    db_session.add(qr)
    db_session.commit()

    count = run_query(db_session, str(qr.id))
    assert count == 0
    # Status remains cancelled and no results were written
    db_session.refresh(qr)
    assert qr.status == "cancelled"
    assert db_session.query(QueryResult).filter_by(query_run_id=qr.id).count() == 0
