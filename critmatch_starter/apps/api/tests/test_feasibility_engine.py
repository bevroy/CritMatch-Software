"""Unit tests for run_feasibility()'s session-claims-based FHIRClient construction.

These call the engine directly (no HTTP route, no ``fhir_client`` override) so
we exercise the actual branch in ``feasibility_engine.run_feasibility`` that
builds a real ``FHIRClient`` from ``session_claims`` - mirroring how
``test_query_runner.py`` unit-tests the executor directly.
"""

from __future__ import annotations

import time
import uuid

import httpx
import pytest

from app.db.models import FeasibilityQuestion, FeasibilityQuestionnaire, FeasibilityRun
from app.services import feasibility_engine as feasibility_engine_module
from app.services.feasibility_engine import FeasibilityExecutionError, run_feasibility

ISS = "https://fhir.sandbox.example.com"


class _FakeSettings:
    smart_client_id = "critmatch-test-client"
    smart_client_secret = "test-client-secret"


def _questionnaire_with_run(db_session, user_id):
    fq = FeasibilityQuestionnaire(id=uuid.uuid4(), name="Q", created_by=user_id)
    db_session.add(fq)
    db_session.flush()
    db_session.add(
        FeasibilityQuestion(
            questionnaire_id=fq.id,
            position=0,
            text="Has E11",
            logic_json={
                "operator": "AND",
                "rules": [{"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]}],
            },
        )
    )
    fr = FeasibilityRun(id=uuid.uuid4(), questionnaire_id=fq.id, run_by=user_id, status="queued")
    db_session.add(fr)
    db_session.commit()
    return fr


def test_run_feasibility_uses_session_claims_for_fhir_client(db_session, authed_user, monkeypatch):
    fr = _questionnaire_with_run(db_session, authed_user.id)

    seen_requests: list[dict] = []

    def fake_get(self, url, params=None, **_kw):
        seen_requests.append(
            {
                "base_url": str(self.base_url),
                "authorization": self.headers.get("authorization"),
                "url": url,
            }
        )
        return httpx.Response(200, json={"resourceType": "Bundle", "entry": []})

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    session_claims = {
        "access_token": "session-access-token-xyz",
        "fhir_base_url": "https://fhir.sandbox.example.com",
    }

    total = run_feasibility(db_session, str(fr.id), session_claims=session_claims)

    assert total == 0
    assert seen_requests, "expected run_feasibility to issue a FHIR search request"
    assert seen_requests[0]["base_url"] == "https://fhir.sandbox.example.com"
    assert seen_requests[0]["authorization"] == "Bearer session-access-token-xyz"
    assert seen_requests[0]["url"] == "/Condition"


def test_run_feasibility_without_session_claims_fails_closed(db_session, authed_user):
    fr = _questionnaire_with_run(db_session, authed_user.id)

    with pytest.raises(FeasibilityExecutionError, match="FHIR base URL required"):
        run_feasibility(db_session, str(fr.id), session_claims=None)

    db_session.refresh(fr)
    assert fr.status == "failed"
    assert "FHIR base URL required" in fr.error_message


def test_run_feasibility_missing_fhir_base_url_fails_closed(db_session, authed_user):
    fr = _questionnaire_with_run(db_session, authed_user.id)

    # access_token present but no fhir_base_url - must not silently fall back
    # to an empty/None base URL.
    with pytest.raises(FeasibilityExecutionError, match="FHIR base URL required"):
        run_feasibility(
            db_session,
            str(fr.id),
            session_claims={"access_token": "session-access-token-xyz"},
        )

    db_session.refresh(fr)
    assert fr.status == "failed"


def test_run_feasibility_refreshes_expired_access_token_in_place(db_session, authed_user, monkeypatch):
    fr = _questionnaire_with_run(db_session, authed_user.id)

    fhir_requests: list[dict] = []

    def fake_fhir_get(self, url, params=None, **_kw):
        fhir_requests.append({"authorization": self.headers.get("authorization"), "url": url})
        return httpx.Response(200, json={"resourceType": "Bundle", "entry": []})

    monkeypatch.setattr(httpx.Client, "get", fake_fhir_get)

    def fake_discovery_get(url, **_kw):
        assert url == f"{ISS}/.well-known/smart-configuration"
        return httpx.Response(200, json={"token_endpoint": f"{ISS}/oauth2/token"})

    def fake_token_post(url, **_kw):
        assert url == f"{ISS}/oauth2/token"
        return httpx.Response(
            200,
            json={
                "access_token": "refreshed-access-token",
                "refresh_token": "refreshed-refresh-token",
                "expires_in": 600,
            },
        )

    monkeypatch.setattr(httpx, "get", fake_discovery_get)
    monkeypatch.setattr(httpx, "post", fake_token_post)
    monkeypatch.setattr(feasibility_engine_module, "get_settings", lambda: _FakeSettings())

    session_claims = {
        "access_token": "stale-access-token",
        "refresh_token": "refresh-abc",
        "expires_in": 300,
        "fhir_base_url": ISS,
        "iat": int(time.time()) - 1000,  # expired well past the leeway
    }

    total = run_feasibility(db_session, str(fr.id), session_claims=session_claims)

    assert total == 0
    assert fhir_requests, "expected run_feasibility to search FHIR using the refreshed token"
    assert fhir_requests[0]["authorization"] == "Bearer refreshed-access-token"

    # session_claims mutated in place so the caller (the route) can persist it.
    assert session_claims["access_token"] == "refreshed-access-token"
    assert session_claims["refresh_token"] == "refreshed-refresh-token"
    assert session_claims["expires_in"] == 600

