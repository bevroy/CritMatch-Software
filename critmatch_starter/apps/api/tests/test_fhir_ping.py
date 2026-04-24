"""Tests for the FHIR connectivity probe."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest


def _make_admin(client, db_session):
    from app.core.config import get_settings
    from app.core.security import issue_session_token
    from app.db.models import User

    user = User(
        id=uuid.uuid4(),
        ehr_user_id=f"admin-{uuid.uuid4()}",
        name="Admin",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    token = issue_session_token({"sub": str(user.id), "role": "admin"})
    client.cookies.set(get_settings().session_cookie_name, token)
    return client


def test_fhir_ping_requires_auth(client):
    resp = client.get("/api/fhir/ping")
    assert resp.status_code == 401


def test_fhir_ping_requires_admin(authed_client):
    resp = authed_client.get("/api/fhir/ping")
    assert resp.status_code == 403


def test_fhir_ping_unconfigured(client, db_session, monkeypatch):
    from app.core import config as cfg

    monkeypatch.setenv("FHIR_BASE_URL", "")
    cfg._settings = None

    _make_admin(client, db_session)
    resp = client.get("/api/fhir/ping")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["configured"] is False


def test_fhir_ping_success(client, db_session, monkeypatch):
    from app.core import config as cfg
    from app.routes import fhir as fhir_module

    monkeypatch.setenv("FHIR_BASE_URL", "https://fhir.example.com")
    cfg._settings = None

    capability = {
        "fhirVersion": "4.0.1",
        "software": {"name": "TestServer"},
        "publisher": "ACME",
        "rest": [
            {
                "resource": [
                    {"type": "Patient"},
                    {"type": "Condition"},
                    {"type": "Observation"},
                ]
            }
        ],
    }

    def fake_get(url, **_kw):
        assert url == "https://fhir.example.com/metadata"
        return httpx.Response(200, content=json.dumps(capability).encode(), headers={"content-type": "application/fhir+json"})

    monkeypatch.setattr(fhir_module.httpx, "get", fake_get)

    _make_admin(client, db_session)
    resp = client.get("/api/fhir/ping")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["fhirVersion"] == "4.0.1"
    assert body["software"] == "TestServer"
    assert "Patient" in body["resourceTypes"]
    assert body["resourceCount"] == 3


def test_fhir_ping_network_failure(client, db_session, monkeypatch):
    from app.core import config as cfg
    from app.routes import fhir as fhir_module

    monkeypatch.setenv("FHIR_BASE_URL", "https://fhir.example.com")
    cfg._settings = None

    def boom(*_a, **_kw):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(fhir_module.httpx, "get", boom)

    _make_admin(client, db_session)
    resp = client.get("/api/fhir/ping")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "ConnectError" in body["reason"]


def teardown_module(_module):
    import os

    from app.core import config as cfg

    os.environ.pop("FHIR_BASE_URL", None)
    cfg._settings = None


# Reference pytest so the import isn't unused if the module is re-loaded.
_ = pytest
