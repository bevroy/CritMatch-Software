"""Tests for the dev-login endpoint."""

from __future__ import annotations

import os


def _reset_settings():
    from app.core import config as cfg
    cfg._settings = None
    return cfg.get_settings()


def test_dev_login_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("DEV_LOGIN_ENABLED", raising=False)
    monkeypatch.delenv("DEV_LOGIN_ALLOW_PROD", raising=False)
    _reset_settings()

    resp = client.post("/api/auth/dev-login", json={})
    assert resp.status_code == 404

    enabled = client.get("/api/auth/dev-login/enabled").json()
    assert enabled["enabled"] is False


def test_dev_login_when_enabled_creates_session(client, db_session, monkeypatch):
    monkeypatch.setenv("DEV_LOGIN_ENABLED", "1")
    monkeypatch.setenv("APP_ENV", "test")  # not production
    _reset_settings()

    enabled = client.get("/api/auth/dev-login/enabled").json()
    assert enabled["enabled"] is True

    resp = client.post("/api/auth/dev-login", json={"role": "admin", "name": "Tester"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "admin"
    assert body["patient_context"] is None

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_dev_login_blocked_in_production_without_override(client, monkeypatch):
    monkeypatch.setenv("DEV_LOGIN_ENABLED", "1")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DEV_LOGIN_ALLOW_PROD", raising=False)
    _reset_settings()

    resp = client.post("/api/auth/dev-login", json={})
    assert resp.status_code == 403


def test_dev_login_rejects_unknown_role(client, monkeypatch):
    monkeypatch.setenv("DEV_LOGIN_ENABLED", "1")
    monkeypatch.setenv("APP_ENV", "test")
    _reset_settings()

    resp = client.post("/api/auth/dev-login", json={"role": "superuser"})
    assert resp.status_code == 400


def teardown_module(_module):
    # Restore the test default so other tests aren't affected.
    os.environ.pop("DEV_LOGIN_ENABLED", None)
    os.environ.pop("DEV_LOGIN_ALLOW_PROD", None)
    os.environ["APP_ENV"] = "test"
    from app.core import config as cfg
    cfg._settings = None
