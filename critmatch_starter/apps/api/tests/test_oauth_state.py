"""Tests for the DB-backed OAuth state/PKCE store in routes/auth.py.

Replaces the old in-process ``_state_store`` dict with the ``oauth_states``
table (see app/db/models.py::OAuthState, alembic 0010_oauth_state).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from app.db.models import OAuthState
from app.routes.auth import _consume_state, _store_state

ISS = "https://fhir.sandbox.example.com"
CLIENT_ID = "critmatch-test-client"
CLIENT_SECRET = "test-client-secret"
REDIRECT_URI = "https://critmatch.example.com/auth/callback"
TOKEN_ENDPOINT = f"{ISS}/oauth2/token"
AUTHORIZE_ENDPOINT = f"{ISS}/oauth2/authorize"


def _configure_smart_env(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setenv("SMART_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("SMART_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("SMART_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setenv("SMART_ISSUER_ALLOWLIST", ISS)
    cfg._settings = None


def _fake_smart_configuration_get(url, **_kw):
    return httpx.Response(
        200,
        json={
            "authorization_endpoint": AUTHORIZE_ENDPOINT,
            "token_endpoint": TOKEN_ENDPOINT,
        },
    )


# ---------------------------------------------------------------------------
# Direct store/consume unit tests
# ---------------------------------------------------------------------------


def test_store_then_consume_state_round_trip(db_session):
    _store_state(
        db_session,
        "state-abc",
        {
            "iss": ISS,
            "token_endpoint": TOKEN_ENDPOINT,
            "jwks_uri": "https://fhir.sandbox.example.com/.well-known/jwks.json",
            "code_verifier": "verifier-xyz",
        },
    )

    result = _consume_state(db_session, "state-abc")
    assert result == {
        "iss": ISS,
        "token_endpoint": TOKEN_ENDPOINT,
        "jwks_uri": "https://fhir.sandbox.example.com/.well-known/jwks.json",
        "code_verifier": "verifier-xyz",
    }

    # One-time use: a second consume of the same state finds nothing.
    assert _consume_state(db_session, "state-abc") is None
    assert db_session.get(OAuthState, "state-abc") is None


def test_consume_unknown_state_returns_none(db_session):
    assert _consume_state(db_session, "never-issued-state") is None


def test_consume_expired_state_returns_none(db_session):
    _store_state(
        db_session,
        "state-expired",
        {
            "iss": ISS,
            "token_endpoint": TOKEN_ENDPOINT,
            "jwks_uri": None,
            "code_verifier": "verifier-xyz",
        },
    )
    # Simulate the TTL having passed by backdating the stored row, rather
    # than mocking datetime.utcnow() globally.
    row = db_session.get(OAuthState, "state-expired")
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert _consume_state(db_session, "state-expired") is None
    # Still one-time-use (removed) even though it was expired, not valid.
    assert db_session.get(OAuthState, "state-expired") is None


# ---------------------------------------------------------------------------
# HTTP-level: smart_authorize()/smart_callback() using the new store
# ---------------------------------------------------------------------------


def test_authorize_persists_state_row(client, db_session, monkeypatch):
    from app.routes import auth as auth_module

    _configure_smart_env(monkeypatch)
    monkeypatch.setattr(auth_module.httpx, "get", _fake_smart_configuration_get)

    resp = client.post("/api/auth/smart/authorize", json={"iss": ISS, "launch": "launch-1"})
    assert resp.status_code == 200, resp.text
    state = resp.json()["state"]

    row = db_session.get(OAuthState, state)
    assert row is not None
    assert row.iss == ISS
    assert row.token_endpoint == TOKEN_ENDPOINT


def test_callback_rejects_unknown_state(client, db_session, monkeypatch):
    _configure_smart_env(monkeypatch)

    resp = client.post(
        "/api/auth/smart/callback",
        json={"code": "irrelevant-code", "state": "state-nobody-ever-issued"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Unknown or expired state"


def test_callback_rejects_expired_state(client, db_session, monkeypatch):
    from app.routes import auth as auth_module

    _configure_smart_env(monkeypatch)
    monkeypatch.setattr(auth_module.httpx, "get", _fake_smart_configuration_get)

    authorize_resp = client.post(
        "/api/auth/smart/authorize", json={"iss": ISS, "launch": "launch-1"}
    )
    assert authorize_resp.status_code == 200, authorize_resp.text
    state = authorize_resp.json()["state"]

    # Backdate the row past its TTL instead of waiting/mocking global time.
    row = db_session.get(OAuthState, state)
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    callback_resp = client.post(
        "/api/auth/smart/callback",
        json={"code": "irrelevant-code", "state": state},
    )
    assert callback_resp.status_code == 400
    assert callback_resp.json()["detail"] == "Unknown or expired state"


def teardown_module(_module):
    import os

    from app.core import config as cfg

    for key in (
        "SMART_CLIENT_ID",
        "SMART_CLIENT_SECRET",
        "SMART_REDIRECT_URI",
        "SMART_ISSUER_ALLOWLIST",
    ):
        os.environ.pop(key, None)
    cfg._settings = None
