"""Tests for first-party email login domain restrictions."""

from __future__ import annotations

import os


def _reset_settings():
    from app.core import config as cfg

    cfg._settings = None
    return cfg.get_settings()


def test_email_login_allows_approved_domain(client, monkeypatch):
    monkeypatch.setenv(
        "LOGIN_EMAIL_DOMAIN_ALLOWLIST",
        "critmatchresearch.com,elionyxhealth.com",
    )
    _reset_settings()

    resp = client.post(
        "/api/auth/login",
        json={"email": "analyst@critmatchresearch.com", "password": "Passw0rd!", "name": "Analyst"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "research_user"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "research_user"


def test_email_login_rejects_unapproved_domain(client, monkeypatch):
    monkeypatch.setenv(
        "LOGIN_EMAIL_DOMAIN_ALLOWLIST",
        "critmatchresearch.com,elionyxhealth.com",
    )
    _reset_settings()

    resp = client.post(
        "/api/auth/login",
        json={"email": "intruder@example.org", "password": "Passw0rd!", "name": "Nope"},
    )
    assert resp.status_code == 403


def test_email_login_rejects_invalid_email(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "Passw0rd!"},
    )
    assert resp.status_code == 400


def test_email_login_rejects_wrong_password(client, monkeypatch):
    monkeypatch.setenv(
        "LOGIN_EMAIL_DOMAIN_ALLOWLIST",
        "critmatchresearch.com,elionyxhealth.com",
    )
    _reset_settings()

    ok = client.post(
        "/api/auth/login",
        json={"email": "analyst@critmatchresearch.com", "password": "Passw0rd!", "name": "Analyst"},
    )
    assert ok.status_code == 200, ok.text

    bad = client.post(
        "/api/auth/login",
        json={"email": "analyst@critmatchresearch.com", "password": "wrongpass", "name": "Analyst"},
    )
    assert bad.status_code == 401


def teardown_module(_module):
    os.environ.pop("LOGIN_EMAIL_DOMAIN_ALLOWLIST", None)
    from app.core import config as cfg

    cfg._settings = None
