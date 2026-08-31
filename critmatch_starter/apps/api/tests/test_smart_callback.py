"""Tests for SMART callback token persistence in the session cookie."""

from __future__ import annotations

import time

import httpx
import jwt

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


def _make_id_token() -> str:
    now = int(time.time())
    claims = {
        "iss": ISS,
        "aud": CLIENT_ID,
        "sub": "epic-practitioner-1",
        "fhirUser": "Practitioner/epic-practitioner-1",
        "email": "researcher@critmatchresearch.com",
        "name": "Dr. Researcher",
        "iat": now,
        "exp": now + 300,
    }
    # Signature is never checked: the fake smart-configuration below omits
    # jwks_uri, so smart_callback() takes the unverified structural-validation
    # branch (allowed because APP_ENV=test).
    return jwt.encode(claims, "unused-signing-key", algorithm="HS256")


def _fake_smart_configuration_get(url, **_kw):
    assert url == f"{ISS}/.well-known/smart-configuration"
    return httpx.Response(
        200,
        json={
            "authorization_endpoint": AUTHORIZE_ENDPOINT,
            "token_endpoint": TOKEN_ENDPOINT,
        },
    )


def test_smart_callback_persists_tokens_and_fhir_base_url(client, db_session, monkeypatch):
    from app.core import config as cfg
    from app.core.security import verify_session_token
    from app.routes import auth as auth_module

    _configure_smart_env(monkeypatch)
    monkeypatch.setattr(auth_module.httpx, "get", _fake_smart_configuration_get)

    authorize_resp = client.post(
        "/api/auth/smart/authorize",
        json={"iss": ISS, "launch": "launch-xyz"},
    )
    assert authorize_resp.status_code == 200, authorize_resp.text
    state = authorize_resp.json()["state"]

    token_response_body = {
        "access_token": "epic-access-token-abc123",
        "refresh_token": "epic-refresh-token-def456",
        "expires_in": 300,
        "scope": "openid fhirUser launch patient/*.read offline_access",
        "patient": "patient-789",
        "id_token": _make_id_token(),
    }

    def fake_post(url, **_kw):
        assert url == TOKEN_ENDPOINT
        return httpx.Response(200, json=token_response_body)

    monkeypatch.setattr(auth_module.httpx, "post", fake_post)

    callback_resp = client.post(
        "/api/auth/smart/callback",
        json={"code": "test-auth-code", "state": state},
    )
    assert callback_resp.status_code == 200, callback_resp.text
    assert callback_resp.json()["patient_context"] == "patient-789"

    # The cookie is httpOnly - inspect it the same way the app does, by
    # verifying/decoding it, rather than the (impossible) JS-read approach.
    session_cookie = client.cookies.get(cfg.get_settings().session_cookie_name)
    assert session_cookie is not None
    claims = verify_session_token(session_cookie)
    assert claims["access_token"] == "epic-access-token-abc123"
    assert claims["refresh_token"] == "epic-refresh-token-def456"
    assert claims["expires_in"] == 300
    assert claims["fhir_base_url"] == ISS

    # A follow-up authenticated request on the same session still succeeds,
    # proving the cookie carrying the new claims remains a valid session.
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["patient_context"] == "patient-789"


def test_smart_authorize_ignores_client_supplied_scope(client, db_session, monkeypatch):
    from app.routes import auth as auth_module
    from urllib.parse import parse_qs, urlparse

    _configure_smart_env(monkeypatch)
    monkeypatch.setattr(auth_module.httpx, "get", _fake_smart_configuration_get)

    resp = client.post(
        "/api/auth/smart/authorize",
        json={
            "iss": ISS,
            # A client asking for something broader than what the server
            # actually requests - e.g. a compromised/modified frontend.
            "scope": "openid fhirUser launch patient/*.* system/*.read",
        },
    )
    assert resp.status_code == 200, resp.text

    authorize_url = resp.json()["authorize_url"]
    requested_scope = parse_qs(urlparse(authorize_url).query)["scope"][0]

    assert requested_scope == auth_module.SMART_REQUESTED_SCOPE
    assert "patient/*.*" not in requested_scope
    assert "system/*.read" not in requested_scope


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
