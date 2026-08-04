"""Tests for per-study sharing/RBAC."""

from __future__ import annotations

import uuid

import pytest


def _make_user(db_session, role="research_user", name="User"):
    from app.db.models import User

    u = User(
        id=uuid.uuid4(),
        ehr_user_id=f"u-{uuid.uuid4()}",
        name=name,
        email=f"{name.lower().replace(' ', '')}@example.com",
        role=role,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _client_for(client, user):
    from app.core.config import get_settings
    from app.core.security import issue_session_token

    token = issue_session_token({"sub": str(user.id), "role": user.role})
    client.cookies.clear()
    client.cookies.set(get_settings().session_cookie_name, token)
    return client


def _make_study(db_session, owner):
    from app.db.models import Study

    s = Study(name="Cohort A", owner_user_id=owner.id)
    db_session.add(s)
    db_session.commit()
    return s


# ---------------------------------------------------------------------------


def test_non_owner_cannot_see_study(client, db_session):
    owner = _make_user(db_session, name="Owner")
    other = _make_user(db_session, name="Other")
    study = _make_study(db_session, owner)

    _client_for(client, other)
    resp = client.get(f"/api/studies/{study.id}")
    assert resp.status_code == 404


def test_viewer_can_read_but_not_run(client, db_session):
    from app.db.models import StudyCollaborator

    owner = _make_user(db_session, name="Owner")
    viewer = _make_user(db_session, name="Viewer")
    study = _make_study(db_session, owner)
    db_session.add(StudyCollaborator(study_id=study.id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    _client_for(client, viewer)
    assert client.get(f"/api/studies/{study.id}").status_code == 200
    assert client.get(f"/api/studies/{study.id}/criteria-sets").status_code == 200

    # Viewer can list studies and see this one.
    listing = client.get("/api/studies").json()
    assert any(s["id"] == str(study.id) for s in listing)
    entry = next(s for s in listing if s["id"] == str(study.id))
    assert entry["myAccess"] == "viewer"

    detail = client.get(f"/api/studies/{study.id}").json()
    assert detail["myAccess"] == "viewer"

    # Viewer cannot create criteria sets.
    create = client.post(
        f"/api/studies/{study.id}/criteria-sets",
        json={"version": 1, "logic_json": {"operator": "AND", "rules": []}},
    )
    assert create.status_code == 403


def test_editor_can_create_criteria_set(client, db_session):
    from app.db.models import StudyCollaborator

    owner = _make_user(db_session, name="Owner")
    editor = _make_user(db_session, name="Editor")
    study = _make_study(db_session, owner)
    db_session.add(StudyCollaborator(study_id=study.id, user_id=editor.id, role="editor"))
    db_session.commit()

    _client_for(client, editor)
    resp = client.post(
        f"/api/studies/{study.id}/criteria-sets",
        json={"version": 1, "logic_json": {"operator": "AND", "rules": []}},
    )
    assert resp.status_code == 200, resp.text


def test_only_owner_or_admin_can_add_collaborator(client, db_session):
    owner = _make_user(db_session, name="Owner")
    editor = _make_user(db_session, name="Editor")
    study = _make_study(db_session, owner)

    from app.db.models import StudyCollaborator

    db_session.add(StudyCollaborator(study_id=study.id, user_id=editor.id, role="editor"))
    db_session.commit()

    third = _make_user(db_session, name="Third")

    # Editor cannot add a collaborator.
    _client_for(client, editor)
    resp = client.post(
        f"/api/studies/{study.id}/collaborators",
        json={"user_id": str(third.id), "role": "viewer"},
    )
    assert resp.status_code == 403

    # Owner can.
    _client_for(client, owner)
    resp = client.post(
        f"/api/studies/{study.id}/collaborators",
        json={"user_id": str(third.id), "role": "viewer"},
    )
    assert resp.status_code == 200, resp.text


def test_admin_can_access_any_study(client, db_session):
    owner = _make_user(db_session, name="Owner")
    admin = _make_user(db_session, name="Admin", role="admin")
    study = _make_study(db_session, owner)

    _client_for(client, admin)
    assert client.get(f"/api/studies/{study.id}").status_code == 200


def test_transfer_ownership(client, db_session):
    owner = _make_user(db_session, name="Owner")
    target = _make_user(db_session, name="NewOwner")
    study = _make_study(db_session, owner)

    _client_for(client, owner)
    resp = client.patch(
        f"/api/studies/{study.id}",
        json={"owner_user_id": str(target.id)},
    )
    assert resp.status_code == 200, resp.text

    # Original owner should now be locked out (no collab row).
    _client_for(client, owner)
    assert client.get(f"/api/studies/{study.id}").status_code == 404

    # Target now has access.
    _client_for(client, target)
    assert client.get(f"/api/studies/{study.id}").status_code == 200


def test_remove_collaborator(client, db_session):
    from app.db.models import StudyCollaborator

    owner = _make_user(db_session, name="Owner")
    viewer = _make_user(db_session, name="Viewer")
    study = _make_study(db_session, owner)
    db_session.add(StudyCollaborator(study_id=study.id, user_id=viewer.id, role="viewer"))
    db_session.commit()

    _client_for(client, owner)
    resp = client.delete(f"/api/studies/{study.id}/collaborators/{viewer.id}")
    assert resp.status_code == 200

    _client_for(client, viewer)
    assert client.get(f"/api/studies/{study.id}").status_code == 404


def test_user_search(client, db_session):
    user = _make_user(db_session, name="Searcher")
    study = _make_study(db_session, user)
    _make_user(db_session, name="Findable Person")
    _make_user(db_session, name="Other")

    _client_for(client, user)
    resp = client.get(f"/api/studies/_users/search?q=findable&study_id={study.id}")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert any("Findable" in u["name"] for u in items)


_ = pytest
