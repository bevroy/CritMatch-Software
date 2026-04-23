def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_protected_routes_require_auth(client):
    for path in ("/api/studies", "/api/audit"):
        resp = client.get(path)
        assert resp.status_code == 401, path


def test_create_and_list_study(authed_client):
    resp = authed_client.post("/api/studies", json={"name": "Diabetes cohort"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Diabetes cohort"

    listing = authed_client.get("/api/studies")
    assert listing.status_code == 200
    assert any(s["name"] == "Diabetes cohort" for s in listing.json())


def test_audit_requires_admin_role(authed_client):
    resp = authed_client.get("/api/audit")
    assert resp.status_code == 403


def test_query_run_rejects_unknown_study(authed_client):
    resp = authed_client.post(
        "/api/query/run",
        json={"studyId": "00000000-0000-0000-0000-000000000000",
              "criteriaSetId": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code in (404, 422)
