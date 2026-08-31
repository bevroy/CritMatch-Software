"""Unit tests for the cohort query executor using a fake FHIR client."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.fhir.client import FHIRSearchTruncated
from app.services.query_runner import QueryExecutionError, QueryExecutor, _hash_mrn


class FakeFHIR:
    def __init__(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        self._resources = resources

    def search(self, resource_type: str, params=None, *, page_limit: int = 20):
        for r in self._resources.get(resource_type, []):
            yield r


class RecordingFHIR(FakeFHIR):
    """Same as FakeFHIR, but remembers every search() call's args."""

    def __init__(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        super().__init__(resources)
        self.calls: list[dict[str, Any]] = []

    def search(self, resource_type: str, params=None, *, page_limit: int = 20):
        self.calls.append(
            {"resource_type": resource_type, "params": params, "page_limit": page_limit}
        )
        yield from super().search(resource_type, params, page_limit=page_limit)


class TruncatingFHIR:
    """Simulates a FHIR server with more matches than any page_limit covers."""

    def search(self, resource_type: str, params=None, *, page_limit: int = 20):
        if False:
            yield  # pragma: no cover - marks this as a generator function
        raise FHIRSearchTruncated(f"exceeded page_limit={page_limit}")


def _condition(patient_id: str) -> dict:
    return {
        "resourceType": "Condition",
        "subject": {"reference": f"Patient/{patient_id}"},
    }


def _observation(patient_id: str, *, category_code: str | None = None) -> dict:
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    if category_code:
        resource["category"] = [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": category_code,
                    }
                ]
            }
        ]
    return resource


def _medication_request(patient_id: str) -> dict:
    return {
        "resourceType": "MedicationRequest",
        "subject": {"reference": f"Patient/{patient_id}"},
    }


def _medication_statement(patient_id: str) -> dict:
    return {
        "resourceType": "MedicationStatement",
        "subject": {"reference": f"Patient/{patient_id}"},
    }


def test_and_intersects_rule_matches():
    fhir = FakeFHIR(
        {
            "Condition": [_condition("p1"), _condition("p2")],
            "Observation": [
                {"resourceType": "Observation", "subject": {"reference": "Patient/p1"}},
            ],
        }
    )
    logic = {
        "operator": "AND",
        "rules": [
            {"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]},
            {"id": "r2", "kind": "observation", "codes": [{"code": "1234-5"}]},
        ],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert set(result.keys()) == {"p1"}
    assert set(result["p1"]) == {"r1", "r2"}


def test_medication_rule_matches_via_medication_statement_when_no_medication_request():
    fhir = FakeFHIR(
        {
            "MedicationRequest": [],
            "MedicationStatement": [_medication_statement("p1")],
        }
    )
    logic = {
        "operator": "AND",
        "rules": [{"id": "r1", "kind": "medication", "codes": [{"code": "860975"}]}],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert set(result.keys()) == {"p1"}
    assert set(result["p1"]) == {"r1"}


def test_medication_rule_merges_medication_request_and_statement_matches():
    fhir = FakeFHIR(
        {
            "MedicationRequest": [_medication_request("p1")],
            "MedicationStatement": [_medication_statement("p2")],
        }
    )
    logic = {
        "operator": "AND",
        "rules": [{"id": "r1", "kind": "medication", "codes": [{"code": "860975"}]}],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert set(result.keys()) == {"p1", "p2"}


def test_medication_rule_dedupes_patient_matched_via_both_resource_types():
    fhir = FakeFHIR(
        {
            "MedicationRequest": [_medication_request("p1")],
            "MedicationStatement": [_medication_statement("p1")],
        }
    )
    logic = {
        "operator": "AND",
        "rules": [{"id": "r1", "kind": "medication", "codes": [{"code": "860975"}]}],
    }
    result = QueryExecutor(fhir).execute(logic)
    # A patient present in both resource types matches once, not "twice".
    assert set(result.keys()) == {"p1"}
    assert result["p1"] == ["r1"]


def test_hash_mrn_raises_when_salt_missing(monkeypatch):
    monkeypatch.delenv("MRN_HASH_SALT", raising=False)
    with pytest.raises(QueryExecutionError, match="MRN_HASH_SALT"):
        _hash_mrn("patient-123")


def test_hash_mrn_succeeds_when_salt_configured(monkeypatch):
    monkeypatch.setenv("MRN_HASH_SALT", "some-salt")
    result = _hash_mrn("patient-123")
    assert isinstance(result, str)
    assert len(result) == 64  # sha256 hex digest


def test_or_unions_rule_matches():
    fhir = FakeFHIR(
        {
            "Condition": [_condition("p1")],
            "Observation": [
                {"resourceType": "Observation", "subject": {"reference": "Patient/p2"}},
            ],
        }
    )
    logic = {
        "operator": "OR",
        "rules": [
            {"id": "r1", "kind": "condition", "codes": [{"code": "E11"}]},
            {"id": "r2", "kind": "observation", "codes": [{"code": "1234-5"}]},
        ],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert set(result.keys()) == {"p1", "p2"}


def test_demographic_age_filter():
    fhir = FakeFHIR(
        {
            "Patient": [
                {"resourceType": "Patient", "id": "p1", "birthDate": "1980-01-01"},
                {"resourceType": "Patient", "id": "p2", "birthDate": "2020-01-01"},
            ]
        }
    )
    logic = {
        "operator": "AND",
        "rules": [{"id": "adult", "kind": "demographic", "field": "age", "op": ">=", "value": 18}],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert "p1" in result
    assert "p2" not in result


def test_demographic_age_query_sends_birthdate_search_param():
    fhir = RecordingFHIR(
        {"Patient": [{"resourceType": "Patient", "id": "p1", "birthDate": "1980-01-01"}]}
    )
    logic = {
        "operator": "AND",
        "rules": [{"id": "adult", "kind": "demographic", "field": "age", "op": ">=", "value": 18}],
    }
    QueryExecutor(fhir).execute(logic)

    assert len(fhir.calls) == 1
    call = fhir.calls[0]
    assert call["resource_type"] == "Patient"
    assert call["page_limit"] == 200  # the raised _DEMOGRAPHIC_PAGE_LIMIT, not FHIRClient's default 20

    today = datetime.utcnow().date()
    cutoff = today.replace(year=today.year - 18)
    assert call["params"] == {"birthdate": f"le{cutoff.isoformat()}"}


def test_demographic_gender_query_sends_gender_search_param():
    fhir = RecordingFHIR(
        {"Patient": [{"resourceType": "Patient", "id": "p1", "gender": "female"}]}
    )
    logic = {
        "operator": "AND",
        "rules": [{"id": "r1", "kind": "demographic", "field": "gender", "op": "==", "value": "female"}],
    }
    QueryExecutor(fhir).execute(logic)

    assert fhir.calls[0]["params"] == {"gender": "female"}
    assert fhir.calls[0]["page_limit"] == 200


def test_demographic_query_still_raises_when_higher_page_limit_exceeded():
    fhir = TruncatingFHIR()
    logic = {
        "operator": "AND",
        "rules": [{"id": "r1", "kind": "demographic", "field": "age", "op": "==", "value": 40}],
    }
    with pytest.raises(FHIRSearchTruncated, match="page_limit=200"):
        QueryExecutor(fhir).execute(logic)


def test_observation_rule_matches_when_category_matches():
    fhir = FakeFHIR({"Observation": [_observation("p1", category_code="vital-signs")]})
    logic = {
        "operator": "AND",
        "rules": [
            {
                "id": "r1",
                "kind": "observation",
                "codes": [{"code": "8480-6"}],
                "category": "vital-signs",
            }
        ],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert set(result.keys()) == {"p1"}


def test_observation_rule_rejects_code_match_in_wrong_category():
    fhir = FakeFHIR({"Observation": [_observation("p1", category_code="social-history")]})
    logic = {
        "operator": "AND",
        "rules": [
            {
                "id": "r1",
                "kind": "observation",
                "codes": [{"code": "8480-6"}],
                "category": "vital-signs",
            }
        ],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert result == {}


def test_observation_rule_without_category_matches_on_code_alone():
    fhir = FakeFHIR({"Observation": [_observation("p1", category_code="social-history")]})
    logic = {
        "operator": "AND",
        "rules": [{"id": "r1", "kind": "observation", "codes": [{"code": "8480-6"}]}],
    }
    result = QueryExecutor(fhir).execute(logic)
    assert set(result.keys()) == {"p1"}
