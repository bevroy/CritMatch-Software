"""Tests for filtered audit log endpoint (Phase 8b)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta


def _make_admin_client(client, db_session):
    from app.core.config import get_settings
    from app.core.security import issue_session_token
    from app.db.models import User

    admin = User(id=uuid.uuid4(), name="Admin", role="admin")
    db_session.add(admin)
    db_session.commit()

    token = issue_session_token({"sub": str(admin.id), "role": "admin"})
    client.cookies.set(get_settings().session_cookie_name, token)
    return client, admin


def _seed_audit(db_session, owner_id):
    from app.db.models import AuditLog

    rows = [
        AuditLog(user_id=owner_id, action="study_create", object_type="study", object_id="s1"),
        AuditLog(user_id=owner_id, action="query_run", object_type="query_run", object_id="r1"),
        AuditLog(user_id=owner_id, action="export_download", object_type="query_run", object_id="r1"),
        AuditLog(user_id=owner_id, action="query_run_cancel", object_type="query_run", object_id="r1"),
    ]
    for r in rows:
        db_session.add(r)
    db_session.commit()
    return rows


def test_audit_requires_admin_or_auditor(authed_client, authed_user, db_session):
    _seed_audit(db_session, authed_user.id)
    resp = authed_client.get("/api/audit")
    assert resp.status_code == 403


def test_audit_returns_paged_payload(client, db_session):
    admin_client, admin = _make_admin_client(client, db_session)
    _seed_audit(db_session, admin.id)

    resp = admin_client.get("/api/audit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert body["limit"] == 100
    assert len(body["items"]) == 4


def test_audit_filters_by_action_and_object(client, db_session):
    admin_client, admin = _make_admin_client(client, db_session)
    _seed_audit(db_session, admin.id)

    resp = admin_client.get("/api/audit", params={"action": "query_run_cancel"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "query_run_cancel"

    resp = admin_client.get("/api/audit", params={"objectType": "query_run", "objectId": "r1"})
    body = resp.json()
    assert body["total"] == 3
    assert {i["action"] for i in body["items"]} == {"query_run", "export_download", "query_run_cancel"}


def test_audit_invalid_since_returns_400(client, db_session):
    admin_client, _admin = _make_admin_client(client, db_session)
    resp = admin_client.get("/api/audit", params={"since": "not-a-date"})
    assert resp.status_code == 400


def test_audit_filters_by_time_window(client, db_session):
    from app.db.models import AuditLog

    admin_client, admin = _make_admin_client(client, db_session)
    old = AuditLog(
        user_id=admin.id,
        action="study_create",
        object_type="study",
        object_id="old",
        created_at=datetime.utcnow() - timedelta(days=5),
    )
    new = AuditLog(
        user_id=admin.id,
        action="study_create",
        object_type="study",
        object_id="new",
    )
    db_session.add_all([old, new])
    db_session.commit()

    cutoff = (datetime.utcnow() - timedelta(days=1)).isoformat()
    resp = admin_client.get("/api/audit", params={"since": cutoff})
    body = resp.json()
    object_ids = {i["objectId"] for i in body["items"]}
    assert "new" in object_ids
    assert "old" not in object_ids
