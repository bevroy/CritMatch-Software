"""Unit tests for the cohort query executor using a fake FHIR client."""

from __future__ import annotations

from typing import Any

from app.services.query_runner import QueryExecutor


class FakeFHIR:
    def __init__(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        self._resources = resources

    def search(self, resource_type: str, params=None, *, page_limit: int = 20):
        for r in self._resources.get(resource_type, []):
            yield r


def _condition(patient_id: str) -> dict:
    return {
        "resourceType": "Condition",
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
