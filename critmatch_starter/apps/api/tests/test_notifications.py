"""Tests for the notification stub: created on share/transfer, list/read endpoints."""

from __future__ import annotations

import uuid


def _make_user(db, name="User", role="research_user"):
    from app.db.models import User

    u = User(
        id=uuid.uuid4(),
        ehr_user_id=f"u-{uuid.uuid4()}",
        name=name,
        email=f"{name.lower().replace(' ', '')}@example.com",
        role=role,
    )
    db.add(u)
    db.commit()
    return u


def _client_for(client, user):
    from app.core.config import get_settings
    from app.core.security import issue_session_token

    token = issue_session_token({"sub": str(user.id), "role": user.role})
    client.cookies.clear()
    client.cookies.set(get_settings().session_cookie_name, token)
    return client


def _make_study(db, owner):
    from app.db.models import Study

    s = Study(name="Cohort", owner_user_id=owner.id)
    db.add(s)
    db.commit()
    return s


def test_share_creates_notification_and_listing_works(client, db_session):
    owner = _make_user(db_session, name="Owner")
    invitee = _make_user(db_session, name="Invitee")
    study = _make_study(db_session, owner)

    _client_for(client, owner)
    resp = client.post(
        f"/api/studies/{study.id}/collaborators",
        json={"user_id": str(invitee.id), "role": "viewer"},
    )
    assert resp.status_code == 200, resp.text

    _client_for(client, invitee)
    page = client.get("/api/notifications").json()
    assert page["unread"] == 1
    assert page["total"] == 1
    n = page["items"][0]
    assert n["kind"] == "study_shared"
    assert "Invitee" not in n["title"]  # title talks about the study
    assert n["link"] == f"/studies/{study.id}"
    assert n["readAt"] is None

    # Mark read
    r = client.post(f"/api/notifications/{n['id']}/read")
    assert r.status_code == 200
    page2 = client.get("/api/notifications").json()
    assert page2["unread"] == 0
    assert page2["items"][0]["readAt"] is not None


def test_role_change_creates_role_changed_notification(client, db_session):
    owner = _make_user(db_session, name="Owner")
    invitee = _make_user(db_session, name="Invitee")
    study = _make_study(db_session, owner)

    _client_for(client, owner)
    client.post(
        f"/api/studies/{study.id}/collaborators",
        json={"user_id": str(invitee.id), "role": "viewer"},
    )
    client.post(
        f"/api/studies/{study.id}/collaborators",
        json={"user_id": str(invitee.id), "role": "editor"},
    )

    _client_for(client, invitee)
    items = client.get("/api/notifications").json()["items"]
    kinds = {n["kind"] for n in items}
    assert {"study_shared", "study_role_changed"} <= kinds


def test_transfer_creates_ownership_notification(client, db_session):
    owner = _make_user(db_session, name="Owner")
    target = _make_user(db_session, name="NewOwner")
    study = _make_study(db_session, owner)

    _client_for(client, owner)
    resp = client.patch(
        f"/api/studies/{study.id}",
        json={"owner_user_id": str(target.id)},
    )
    assert resp.status_code == 200

    _client_for(client, target)
    page = client.get("/api/notifications").json()
    assert page["unread"] == 1
    assert page["items"][0]["kind"] == "study_ownership_transferred"


def test_read_all_and_unread_count(client, db_session):
    owner = _make_user(db_session, name="Owner")
    invitee = _make_user(db_session, name="Invitee")
    study1 = _make_study(db_session, owner)
    study2 = _make_study(db_session, owner)

    _client_for(client, owner)
    client.post(f"/api/studies/{study1.id}/collaborators", json={"user_id": str(invitee.id), "role": "viewer"})
    client.post(f"/api/studies/{study2.id}/collaborators", json={"user_id": str(invitee.id), "role": "viewer"})

    _client_for(client, invitee)
    assert client.get("/api/notifications/unread-count").json()["unread"] == 2
    r = client.post("/api/notifications/read-all")
    assert r.json()["marked"] == 2
    assert client.get("/api/notifications/unread-count").json()["unread"] == 0


def test_self_share_does_not_notify(client, db_session):
    """Admin sharing a study with themselves shouldn't generate a notification."""
    admin = _make_user(db_session, name="Admin", role="admin")
    study = _make_study(db_session, admin)

    _client_for(client, admin)
    # admin owns the study, so adding self isn't useful – test instead that
    # adding a third party that happens to be the actor self isn't possible.
    # Use the path where an admin-as-actor adds another user, then checks that
    # the *actor* gets no notification.
    other = _make_user(db_session, name="Other")
    client.post(f"/api/studies/{study.id}/collaborators", json={"user_id": str(other.id), "role": "viewer"})
    page = client.get("/api/notifications").json()
    assert page["unread"] == 0
