"""Tests for the cohort-diff endpoint (Phase 8c)."""

from __future__ import annotations

import uuid


def _seed_two_runs(db_session, owner_id, *, base_pids, compare_pids):
    from app.db.models import CriteriaSet, QueryResult, QueryRun, Study

    study = Study(id=uuid.uuid4(), name="DiffStudy", owner_user_id=owner_id)
    db_session.add(study)
    db_session.flush()
    cs = CriteriaSet(id=uuid.uuid4(), study_id=study.id, version=1, logic_json={})
    db_session.add(cs)
    db_session.flush()

    def _make(pids):
        qr = QueryRun(
            id=uuid.uuid4(),
            study_id=study.id,
            criteria_set_id=cs.id,
            status="completed",
            result_count=len(pids),
            execution_ms=10,
        )
        db_session.add(qr)
        db_session.flush()
        for pid in pids:
            db_session.add(QueryResult(query_run_id=qr.id, patient_id=pid))
        return qr

    base = _make(base_pids)
    compare = _make(compare_pids)
    db_session.commit()
    return study, base, compare


def test_diff_runs_returns_added_removed_unchanged(authed_client, authed_user, db_session):
    _study, base, compare = _seed_two_runs(
        db_session,
        authed_user.id,
        base_pids=["p1", "p2", "p3"],
        compare_pids=["p2", "p3", "p4", "p5"],
    )

    resp = authed_client.get(f"/api/runs/{base.id}/diff/{compare.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["baseTotal"] == 3
    assert body["compareTotal"] == 4
    assert body["addedCount"] == 2
    assert body["removedCount"] == 1
    assert body["unchangedCount"] == 2
    assert set(body["added"]) == {"p4", "p5"}
    assert set(body["removed"]) == {"p1"}


def test_diff_rejects_runs_from_different_studies(authed_client, authed_user, db_session):
    _s1, base, _c = _seed_two_runs(
        db_session, authed_user.id, base_pids=["p1"], compare_pids=["p2"],
    )
    _s2, _b2, compare2 = _seed_two_runs(
        db_session, authed_user.id, base_pids=["pa"], compare_pids=["pb"],
    )
    resp = authed_client.get(f"/api/runs/{base.id}/diff/{compare2.id}")
    assert resp.status_code == 400


def test_diff_rejects_incomplete_runs(authed_client, authed_user, db_session):
    from app.db.models import CriteriaSet, QueryRun, Study

    study = Study(id=uuid.uuid4(), name="X", owner_user_id=authed_user.id)
    db_session.add(study)
    db_session.flush()
    cs = CriteriaSet(id=uuid.uuid4(), study_id=study.id, version=1, logic_json={})
    db_session.add(cs)
    db_session.flush()
    queued = QueryRun(id=uuid.uuid4(), study_id=study.id, criteria_set_id=cs.id, status="queued")
    completed = QueryRun(
        id=uuid.uuid4(),
        study_id=study.id,
        criteria_set_id=cs.id,
        status="completed",
        result_count=0,
    )
    db_session.add_all([queued, completed])
    db_session.commit()

    resp = authed_client.get(f"/api/runs/{queued.id}/diff/{completed.id}")
    assert resp.status_code == 409


def test_diff_404_for_unknown_run(authed_client):
    resp = authed_client.get(f"/api/runs/{uuid.uuid4()}/diff/{uuid.uuid4()}")
    assert resp.status_code == 404
