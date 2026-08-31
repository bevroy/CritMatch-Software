"""Unit tests for the SMART access token freshness/refresh helpers."""

from __future__ import annotations

import time

import httpx
import pytest

from app.services import smart_token as smart_token_module
from app.services.smart_token import (
    SmartConfigurationError,
    SmartTokenRefreshError,
    discover_smart_configuration,
    ensure_fresh_session_claims,
    is_access_token_expired,
    refresh_access_token,
)

ISS = "https://fhir.sandbox.example.com"
TOKEN_ENDPOINT = f"{ISS}/oauth2/token"


class FakeSettings:
    smart_client_id = "critmatch-test-client"
    smart_client_secret = "test-client-secret"


def _fresh_claims(**overrides) -> dict:
    claims = {
        "access_token": "old-access-token",
        "refresh_token": "refresh-abc",
        "expires_in": 300,
        "fhir_base_url": ISS,
        "iat": int(time.time()),
    }
    claims.update(overrides)
    return claims


def _no_network(monkeypatch):
    """Fail loudly if code under test makes an unexpected HTTP call."""

    def boom(*_a, **_kw):
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(smart_token_module.httpx, "get", boom)
    monkeypatch.setattr(smart_token_module.httpx, "post", boom)


# ---------------------------------------------------------------------------
# is_access_token_expired
# ---------------------------------------------------------------------------


def test_is_access_token_expired_fresh():
    claims = _fresh_claims(iat=int(time.time()))
    assert is_access_token_expired(claims) is False


def test_is_access_token_expired_expired():
    claims = _fresh_claims(iat=int(time.time()) - 1000)
    assert is_access_token_expired(claims) is True


def test_is_access_token_expired_near_expiry_within_leeway():
    # expires_in=300, issued 250s ago -> 50s left, inside the default 60s leeway.
    claims = _fresh_claims(iat=int(time.time()) - 250)
    assert is_access_token_expired(claims) is True


def test_is_access_token_expired_missing_access_token():
    assert is_access_token_expired({}) is False


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


def test_refresh_access_token_returns_new_tokens(monkeypatch):
    sent = {}

    def fake_post(url, **kw):
        sent["url"] = url
        sent["data"] = kw.get("data")
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 600,
            },
        )

    monkeypatch.setattr(smart_token_module.httpx, "post", fake_post)

    tokens = refresh_access_token(
        token_endpoint=TOKEN_ENDPOINT,
        client_id="cid",
        client_secret="secret",
        refresh_token="refresh-abc",
    )

    assert tokens["access_token"] == "new-access-token"
    assert tokens["refresh_token"] == "new-refresh-token"
    assert tokens["expires_in"] == 600
    assert sent["url"] == TOKEN_ENDPOINT
    assert sent["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-abc",
        "client_id": "cid",
        "client_secret": "secret",
    }


def test_refresh_access_token_raises_on_error_status(monkeypatch):
    def fake_post(url, **_kw):
        return httpx.Response(400, json={"error": "invalid_grant"})

    monkeypatch.setattr(smart_token_module.httpx, "post", fake_post)

    with pytest.raises(SmartTokenRefreshError, match="400"):
        refresh_access_token(
            token_endpoint=TOKEN_ENDPOINT,
            client_id="cid",
            client_secret="secret",
            refresh_token="revoked-refresh-token",
        )


# ---------------------------------------------------------------------------
# discover_smart_configuration
# ---------------------------------------------------------------------------


def test_discover_smart_configuration_raises_on_error(monkeypatch):
    def fake_get(url, **_kw):
        return httpx.Response(500)

    monkeypatch.setattr(smart_token_module.httpx, "get", fake_get)
    with pytest.raises(SmartConfigurationError):
        discover_smart_configuration(ISS)


# ---------------------------------------------------------------------------
# ensure_fresh_session_claims
# ---------------------------------------------------------------------------


def test_ensure_fresh_session_claims_noop_when_not_expired(monkeypatch):
    _no_network(monkeypatch)
    claims = _fresh_claims()
    result, refreshed = ensure_fresh_session_claims(claims, settings=FakeSettings())
    assert refreshed is False
    assert result is claims


def test_ensure_fresh_session_claims_raises_when_refresh_token_missing(monkeypatch):
    _no_network(monkeypatch)
    claims = _fresh_claims(iat=int(time.time()) - 1000, refresh_token=None)
    with pytest.raises(SmartTokenRefreshError, match="refresh_token"):
        ensure_fresh_session_claims(claims, settings=FakeSettings())


def test_ensure_fresh_session_claims_raises_when_fhir_base_url_missing(monkeypatch):
    _no_network(monkeypatch)
    claims = _fresh_claims(iat=int(time.time()) - 1000, fhir_base_url=None)
    with pytest.raises(SmartTokenRefreshError, match="refresh_token"):
        ensure_fresh_session_claims(claims, settings=FakeSettings())


def test_ensure_fresh_session_claims_raises_when_client_credentials_missing(monkeypatch):
    _no_network(monkeypatch)
    claims = _fresh_claims(iat=int(time.time()) - 1000)

    class NoCreds:
        smart_client_id = ""
        smart_client_secret = ""

    with pytest.raises(SmartTokenRefreshError, match="SMART_CLIENT_ID"):
        ensure_fresh_session_claims(claims, settings=NoCreds())


def test_ensure_fresh_session_claims_raises_when_smart_configuration_unavailable(monkeypatch):
    claims = _fresh_claims(iat=int(time.time()) - 1000)

    def fake_get(url, **_kw):
        return httpx.Response(503, text="down for maintenance")

    monkeypatch.setattr(smart_token_module.httpx, "get", fake_get)

    with pytest.raises(SmartTokenRefreshError, match="SMART configuration"):
        ensure_fresh_session_claims(claims, settings=FakeSettings())


def test_ensure_fresh_session_claims_raises_when_refresh_post_fails(monkeypatch):
    claims = _fresh_claims(iat=int(time.time()) - 1000)

    def fake_get(url, **_kw):
        return httpx.Response(200, json={"token_endpoint": TOKEN_ENDPOINT})

    def fake_post(url, **_kw):
        return httpx.Response(400, json={"error": "invalid_grant"})

    monkeypatch.setattr(smart_token_module.httpx, "get", fake_get)
    monkeypatch.setattr(smart_token_module.httpx, "post", fake_post)

    with pytest.raises(SmartTokenRefreshError, match="Token refresh failed"):
        ensure_fresh_session_claims(claims, settings=FakeSettings())


def test_ensure_fresh_session_claims_refreshes_successfully(monkeypatch):
    claims = _fresh_claims(iat=int(time.time()) - 1000, exp=999, jti="old-jti")

    def fake_get(url, **_kw):
        assert url == f"{ISS}/.well-known/smart-configuration"
        return httpx.Response(200, json={"token_endpoint": TOKEN_ENDPOINT})

    def fake_post(url, **_kw):
        assert url == TOKEN_ENDPOINT
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 600,
            },
        )

    monkeypatch.setattr(smart_token_module.httpx, "get", fake_get)
    monkeypatch.setattr(smart_token_module.httpx, "post", fake_post)

    result, refreshed = ensure_fresh_session_claims(claims, settings=FakeSettings())

    assert refreshed is True
    assert result["access_token"] == "new-access-token"
    assert result["refresh_token"] == "new-refresh-token"
    assert result["expires_in"] == 600
    assert result["fhir_base_url"] == ISS
    assert "iat" not in result
    assert "exp" not in result
    assert "jti" not in result


def test_ensure_fresh_session_claims_keeps_old_refresh_token_when_not_rotated(monkeypatch):
    claims = _fresh_claims(iat=int(time.time()) - 1000)

    def fake_get(url, **_kw):
        return httpx.Response(200, json={"token_endpoint": TOKEN_ENDPOINT})

    def fake_post(url, **_kw):
        # No refresh_token in the response - server chose not to rotate it.
        return httpx.Response(200, json={"access_token": "new-access-token", "expires_in": 600})

    monkeypatch.setattr(smart_token_module.httpx, "get", fake_get)
    monkeypatch.setattr(smart_token_module.httpx, "post", fake_post)

    result, refreshed = ensure_fresh_session_claims(claims, settings=FakeSettings())
    assert refreshed is True
    assert result["refresh_token"] == "refresh-abc"
