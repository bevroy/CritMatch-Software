"""Tests for differentiated FHIR error handling in fhir/client.py."""

from __future__ import annotations

import httpx
import pytest

from app.fhir.client import (
    FHIRClient,
    FHIRError,
    FHIRForbiddenError,
    FHIRRateLimitedError,
    FHIRUnauthorizedError,
)


def _client() -> FHIRClient:
    return FHIRClient("https://fhir.example.com", "test-access-token")


def test_read_raises_unauthorized_on_401(monkeypatch):
    def fake_get(self, url, **_kw):
        return httpx.Response(401, text="invalid_token")

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRUnauthorizedError) as exc_info:
        _client().read("Patient/123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.operation_outcome is None
    assert "401" in str(exc_info.value)


def test_read_raises_forbidden_on_403(monkeypatch):
    def fake_get(self, url, **_kw):
        return httpx.Response(403, text="insufficient_scope")

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRForbiddenError) as exc_info:
        _client().read("Patient/123")

    assert exc_info.value.status_code == 403
    assert "403" in str(exc_info.value)


def test_search_raises_rate_limited_with_numeric_retry_after(monkeypatch):
    def fake_get(self, url, params=None, **_kw):
        return httpx.Response(429, text="slow down", headers={"Retry-After": "30"})

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRRateLimitedError) as exc_info:
        list(_client().search("Patient"))

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 30


def test_search_raises_rate_limited_with_non_numeric_retry_after(monkeypatch):
    def fake_get(self, url, params=None, **_kw):
        return httpx.Response(
            429, text="slow down", headers={"Retry-After": "Fri, 31 Dec 2027 23:59:59 GMT"}
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRRateLimitedError) as exc_info:
        list(_client().search("Patient"))

    # Non-numeric Retry-After (an HTTP-date) is passed through as-is rather
    # than dropped or coerced.
    assert exc_info.value.retry_after == "Fri, 31 Dec 2027 23:59:59 GMT"


def test_search_raises_rate_limited_without_retry_after_header(monkeypatch):
    def fake_get(self, url, params=None, **_kw):
        return httpx.Response(429, text="slow down")

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRRateLimitedError) as exc_info:
        list(_client().search("Patient"))

    assert exc_info.value.retry_after is None


def test_search_parses_operation_outcome_diagnostics(monkeypatch):
    operation_outcome_body = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "processing",
                "diagnostics": "Unsupported search parameter 'code'",
            }
        ],
    }

    def fake_get(self, url, params=None, **_kw):
        return httpx.Response(400, json=operation_outcome_body)

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRError) as exc_info:
        list(_client().search("Condition"))

    exc = exc_info.value
    assert type(exc) is FHIRError  # 400 isn't one of the specific subclasses
    assert exc.status_code == 400
    assert exc.operation_outcome == {
        "issues": [
            {
                "severity": "error",
                "code": "processing",
                "diagnostics": "Unsupported search parameter 'code'",
            }
        ]
    }
    assert "Unsupported search parameter 'code'" in str(exc)


def test_operation_outcome_diagnostics_attached_on_401_too(monkeypatch):
    operation_outcome_body = {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "code": "login", "diagnostics": "Token expired"}],
    }

    def fake_get(self, url, **_kw):
        return httpx.Response(401, json=operation_outcome_body)

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRUnauthorizedError) as exc_info:
        _client().read("Patient/123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.operation_outcome["issues"][0]["diagnostics"] == "Token expired"
    assert "Token expired" in str(exc_info.value)


def test_read_generic_error_without_operation_outcome(monkeypatch):
    def fake_get(self, url, **_kw):
        return httpx.Response(500, text="internal server error")

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(FHIRError) as exc_info:
        _client().read("Patient/123")

    assert type(exc_info.value) is FHIRError
    assert exc_info.value.status_code == 500
    assert exc_info.value.operation_outcome is None
