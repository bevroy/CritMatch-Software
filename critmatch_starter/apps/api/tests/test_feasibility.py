"""Tests for the feasibility module."""

from __future__ import annotations

from typing import Any

import httpx


class FakeFHIR:
    """Tiny in-memory FHIR stand-in compatible with QueryExecutor."""

    def __init__(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        self._resources = resources

    def search(self, resource_type: str, params=None, *, page_limit: int = 20):
        for r in self._resources.get(resource_type, []):
            yield r

    def close(self) -> None:  # pragma: no cover - parity with real client
        pass


def _condition(patient_id: str) -> dict:
    return {
        "resourceType": "Condition",
        "subject": {"reference": f"Patient/{patient_id}"},
    }


def _patient(pid: str, birth: str = "1980-01-01") -> dict:
    return {"resourceType": "Patient", "id": pid, "birthDate": birth}


def _install_fake_fhir(client, resources):
    from app.main import app

    app.state.feasibility_fhir_client = FakeFHIR(resources)
    return client


def test_create_and_get_questionnaire(authed_client):
    payload = {
        "name": "Diabetes feasibility",
        "description": "Quick screen",
        "questions": [
            {
                "text": "Patients with E11",
                "logic_json": {
                    "operator": "AND",
                    "rules": [
                        {"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]}
                    ],
                },
            },
            {
                "text": "Adults",
                "logic_json": {
                    "operator": "AND",
                    "rules": [
                        {"id": "r2", "kind": "demographic", "field": "age", "op": ">=", "value": 18}
                    ],
                },
            },
        ],
    }
    resp = authed_client.post("/api/feasibility/questionnaires", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Diabetes feasibility"
    assert len(body["questions"]) == 2

    listing = authed_client.get("/api/feasibility/questionnaires")
    assert listing.status_code == 200
    assert any(q["id"] == body["id"] for q in listing.json())

    get_one = authed_client.get(f"/api/feasibility/questionnaires/{body['id']}")
    assert get_one.status_code == 200
    assert get_one.json()["questions"][0]["text"] == "Patients with E11"


def test_update_questionnaire_replaces_questions(authed_client):
    create = authed_client.post(
        "/api/feasibility/questionnaires",
        json={"name": "Q", "questions": [{"text": "a", "logic_json": {}}]},
    )
    qid = create.json()["id"]

    upd = authed_client.patch(
        f"/api/feasibility/questionnaires/{qid}",
        json={
            "name": "Q renamed",
            "questions": [
                {"text": "x", "logic_json": {"operator": "AND", "rules": []}},
                {"text": "y", "logic_json": {"operator": "AND", "rules": []}},
            ],
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["name"] == "Q renamed"
    assert [q["text"] for q in body["questions"]] == ["x", "y"]


def test_run_questionnaire_returns_per_question_counts(authed_client):
    payload = {
        "name": "Counts",
        "questions": [
            {
                "text": "Has E11",
                "logic_json": {
                    "operator": "AND",
                    "rules": [
                        {"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]}
                    ],
                },
            },
            {
                "text": "Adults",
                "logic_json": {
                    "operator": "AND",
                    "rules": [
                        {"id": "r2", "kind": "demographic", "field": "age", "op": ">=", "value": 18}
                    ],
                },
            },
        ],
    }
    qid = authed_client.post("/api/feasibility/questionnaires", json=payload).json()["id"]

    _install_fake_fhir(
        authed_client,
        {
            "Condition": [_condition("p1"), _condition("p2")],
            "Patient": [
                _patient("p1", "1980-01-01"),
                _patient("p2", "2020-01-01"),
                _patient("p3", "1970-01-01"),
            ],
        },
    )

    resp = authed_client.post(f"/api/feasibility/questionnaires/{qid}/run")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    counts = {r["questionText"]: r["count"] for r in body["results"]}
    assert counts["Has E11"] == 2
    assert counts["Adults"] == 2  # p1 (1980) and p3 (1970)
    # Union across both questions: p1, p2 (from condition) + p1, p3 (adults) = 3
    assert body["totalPatients"] == 3


def test_list_runs_endpoint(authed_client):
    qid = authed_client.post(
        "/api/feasibility/questionnaires",
        json={"name": "L", "questions": [{"text": "t", "logic_json": {}}]},
    ).json()["id"]

    _install_fake_fhir(authed_client, {})
    authed_client.post(f"/api/feasibility/questionnaires/{qid}/run")

    runs = authed_client.get(f"/api/feasibility/questionnaires/{qid}/runs")
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert runs.json()[0]["status"] == "completed"


def test_unauthenticated_blocked(client):
    resp = client.get("/api/feasibility/questionnaires")
    assert resp.status_code == 401


def test_other_user_cannot_see_personal_questionnaire(authed_client, db_session):
    qid = authed_client.post(
        "/api/feasibility/questionnaires",
        json={"name": "Mine", "questions": []},
    ).json()["id"]

    # Spawn a second user + auth a fresh client as them.
    import uuid as _uuid

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.core.security import issue_session_token
    from app.db.models import User
    from app.main import app

    other = User(id=_uuid.uuid4(), name="Other", role="research_user")
    db_session.add(other)
    db_session.commit()
    token = issue_session_token({"sub": str(other.id), "role": other.role})
    other_client = TestClient(app)
    other_client.cookies.set(get_settings().session_cookie_name, token)

    resp = other_client.get(f"/api/feasibility/questionnaires/{qid}")
    assert resp.status_code == 404


def test_run_questionnaire_reissues_cookie_when_access_token_refreshed(
    client, db_session, authed_user, monkeypatch
):
    import time

    from app.core.config import get_settings
    from app.core.security import issue_session_token, verify_session_token
    from app.main import app

    # Guard against another test in this session leaving a fake FHIR client
    # installed on app.state - we want the real session-claims path here.
    app.state.feasibility_fhir_client = None

    iss = "https://fhir.sandbox.example.com"
    token_endpoint = f"{iss}/oauth2/token"

    stale_session_token = issue_session_token(
        {
            "sub": str(authed_user.id),
            "role": authed_user.role,
            "access_token": "stale-access-token",
            "refresh_token": "refresh-abc",
            "expires_in": 300,
            "fhir_base_url": iss,
            "iat": int(time.time()) - 1000,  # expired well past the leeway
        }
    )
    client.cookies.set(get_settings().session_cookie_name, stale_session_token)

    def fake_fhir_get(self, url, params=None, **_kw):
        return httpx.Response(200, json={"resourceType": "Bundle", "entry": []})

    def fake_discovery_get(url, **_kw):
        return httpx.Response(200, json={"token_endpoint": token_endpoint})

    def fake_token_post(url, **_kw):
        return httpx.Response(
            200,
            json={
                "access_token": "refreshed-access-token",
                "refresh_token": "refreshed-refresh-token",
                "expires_in": 600,
            },
        )

    monkeypatch.setattr(httpx.Client, "get", fake_fhir_get)
    monkeypatch.setattr(httpx, "get", fake_discovery_get)
    monkeypatch.setattr(httpx, "post", fake_token_post)

    from app.services import feasibility_engine as feasibility_engine_module

    class _FakeSettings:
        smart_client_id = "critmatch-test-client"
        smart_client_secret = "test-client-secret"

    monkeypatch.setattr(feasibility_engine_module, "get_settings", lambda: _FakeSettings())

    qid = client.post(
        "/api/feasibility/questionnaires",
        json={"name": "Refresh check", "questions": [{"text": "t", "logic_json": {}}]},
    ).json()["id"]

    run_resp = client.post(f"/api/feasibility/questionnaires/{qid}/run")
    assert run_resp.status_code == 200, run_resp.text

    # Read the Set-Cookie from this response directly rather than the
    # client-wide cookie jar - the jar can hold both the manually-seeded
    # stale cookie (domain "") and the server-reissued one (request-host
    # domain) under the same name, which httpx.Cookies.get() treats as an
    # ambiguous conflict.
    reissued_cookie = run_resp.cookies.get(get_settings().session_cookie_name)
    assert reissued_cookie is not None
    assert reissued_cookie != stale_session_token

    refreshed_claims = verify_session_token(reissued_cookie)
    assert refreshed_claims["access_token"] == "refreshed-access-token"
    assert refreshed_claims["refresh_token"] == "refreshed-refresh-token"
    assert refreshed_claims["expires_in"] == 600
