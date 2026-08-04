"""Cohort query executor.

Criteria logic is stored in ``criteria_sets.logic_json`` using this shape::

    {
      "operator": "AND",          # AND | OR
      "rules": [
        {
          "id": "rule-1",
          "kind": "condition",     # condition | observation | medication | demographic
          "label": "Type 2 diabetes",
          "codes": [
            {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11"}
          ]
        },
        {
          "id": "rule-2",
          "kind": "demographic",
          "field": "age",
          "op": ">=",
          "value": 18
        }
      ]
    }

The executor walks the rules, queries the FHIR server, and records every
matched patient + the rules that matched.

PATCHED (audit fix) - three correctness bugs fixed here, all silent before
this patch:

1. The ``demographic`` branch called ``self.fhir.search("Patient", {})``
   with zero filters - the entire Patient compartment. Combined with
   ``FHIRClient.search()``'s ``page_limit=20`` cap, any criteria set with an
   age/gender rule (nearly all of them) could silently see only the first
   <=20 pages of patients. ``fhir/client.py`` now raises
   ``FHIRSearchTruncated`` by default when that cap is hit instead of
   silently stopping, and this module intentionally does NOT catch that
   exception - it's meant to propagate up through ``execute()`` into
   ``run_query()``'s existing generic exception handler, which already
   marks the run ``failed`` and records the error. A failed run is a far
   better outcome than a silently wrong "completed" one for a product whose
   purpose is producing correct match/count numbers.
2. ``medication`` was documented in ``CriteriaSet``'s own schema
   (condition | observation | medication | demographic) but had no branch
   in ``_patients_matching()`` - it fell through to ``return set()``. Under
   AND logic that silently zeroed the *entire* result for any criteria set
   containing a medication rule, while ``QueryRun.status`` still read
   "completed". Added a branch searching ``MedicationRequest`` by code,
   mirroring the ``condition``/``observation`` pattern. Note: this assumes
   active medications are represented as ``MedicationRequest`` on the
   target FHIR server: if a given EHR primarily uses ``MedicationStatement``
   instead, this branch will need a second search against that resource
   type too - flagged here rather than guessed, since which resource type a
   given FHIR server actually populates is deployment-specific.
3. ``observation`` rules matched on code presence only - any patient with a
   matching-coded Observation on file counted as a match regardless of its
   value, so "HbA1c > 7" actually matched anyone who'd ever had an HbA1c
   drawn. Now reads the same ``op``/``value`` fields the ``demographic``
   branch already supports and compares against ``valueQuantity.value``
   when both are present, falling back to code-presence matching (the
   original behavior) only when a rule genuinely doesn't specify a
   threshold - e.g. "has a diagnosis-relevant lab on file at all" is a
   legitimate criterion shape too, so that fallback is kept, just no longer
   the *only* option.

Also added: an explicit error for any ``kind`` outside the four documented
values, instead of the previous silent ``return set()`` (which, under AND
logic, would have zeroed the whole result with no indication why - the same
failure shape as bug #2, just for a typo'd or future/unsupported kind
rather than a known-missing one).
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, QueryResult, QueryRun
from app.fhir.client import FHIRClient

_KNOWN_RULE_KINDS = {"condition", "observation", "medication", "demographic"}


def _current_status(db: Session, run_id) -> str | None:
    """Read just the current status without disturbing the in-memory instance."""
    return db.query(QueryRun.status).filter(QueryRun.id == run_id).scalar()


class QueryExecutionError(RuntimeError):
    pass


def _coding_param(codes: Iterable[dict[str, str]]) -> str:
    """Build a FHIR token search value: ``system|code,system|code``."""

    parts = []
    for c in codes:
        system = c.get("system", "")
        code = c.get("code", "")
        if not code:
            continue
        parts.append(f"{system}|{code}" if system else code)
    return ",".join(parts)


def _hash_mrn(patient_id: str) -> str:
    salt = os.getenv("MRN_HASH_SALT", "")
    return hashlib.sha256((salt + ":" + patient_id).encode()).hexdigest()


def _evaluate_demographic(rule: dict[str, Any], patient: dict[str, Any]) -> bool:
    field = rule.get("field")
    op = rule.get("op", "==")
    value = rule.get("value")
    if field == "age":
        birth = patient.get("birthDate")
        if not birth:
            return False
        try:
            born = date.fromisoformat(birth[:10])
        except ValueError:
            return False
        # PATCHED (audit fix, low severity): use a UTC-anchored date rather
        # than the server's local date, so age calculation doesn't depend on
        # server timezone configuration.
        today = datetime.utcnow().date()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return _compare(age, op, value)
    if field == "gender":
        return _compare(patient.get("gender"), op, value)
    return False


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if actual is None:
        return False
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    try:
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
    except TypeError:
        return False
    return False


def _patient_id_from_subject(reference: str | None) -> str | None:
    if not reference:
        return None
    # "Patient/123" or "urn:uuid:..." or full URL ".../Patient/123"
    if "Patient/" in reference:
        return reference.split("Patient/", 1)[1].split("?")[0]
    return None


class QueryExecutor:
    def __init__(self, fhir: FHIRClient) -> None:
        self.fhir = fhir

    def execute(self, logic: dict[str, Any]) -> dict[str, list[str]]:
        """Return ``{patient_id: [matched_rule_ids]}``."""

        operator = (logic.get("operator") or "AND").upper()
        rules = logic.get("rules", []) or []
        if not rules:
            return {}

        per_rule: dict[str, set[str]] = {}
        labels: dict[str, str] = {}
        for rule in rules:
            rule_id = rule.get("id") or rule.get("label") or "rule"
            labels[rule_id] = rule.get("label") or rule_id
            per_rule[rule_id] = self._patients_matching(rule)

        if operator == "AND":
            matched_ids = set.intersection(*per_rule.values()) if per_rule else set()
        else:
            matched_ids = set().union(*per_rule.values()) if per_rule else set()

        out: dict[str, list[str]] = defaultdict(list)
        for pid in matched_ids:
            for rule_id, patients in per_rule.items():
                if pid in patients:
                    out[pid].append(rule_id)
        return dict(out)

    # ------------------------------------------------------------------
    def _patients_matching(self, rule: dict[str, Any]) -> set[str]:
        kind = rule.get("kind")

        if kind not in _KNOWN_RULE_KINDS:
            # PATCHED (audit fix): previously fell through to `return set()`
            # for any unrecognized kind, which - under AND logic - silently
            # zeroed the entire criteria set's result with no indication why.
            # Fail loud instead; this propagates up to run_query()'s
            # existing exception handler, which marks the run "failed".
            raise QueryExecutionError(
                f"Unknown rule kind {kind!r}; expected one of {sorted(_KNOWN_RULE_KINDS)}"
            )

        if kind == "condition":
            value = _coding_param(rule.get("codes", []))
            if not value:
                return set()
            ids: set[str] = set()
            for resource in self.fhir.search("Condition", {"code": value}):
                pid = _patient_id_from_subject((resource.get("subject") or {}).get("reference"))
                if pid:
                    ids.add(pid)
            return ids

        if kind == "medication":
            # PATCHED (audit fix): previously unimplemented - see module
            # docstring for the MedicationRequest-vs-MedicationStatement
            # caveat.
            value = _coding_param(rule.get("codes", []))
            if not value:
                return set()
            ids = set()
            for resource in self.fhir.search("MedicationRequest", {"code": value}):
                pid = _patient_id_from_subject((resource.get("subject") or {}).get("reference"))
                if pid:
                    ids.add(pid)
            return ids

        if kind == "observation":
            value = _coding_param(rule.get("codes", []))
            if not value:
                return set()
            op = rule.get("op")
            threshold = rule.get("value")
            ids = set()
            for resource in self.fhir.search("Observation", {"code": value}):
                pid = _patient_id_from_subject((resource.get("subject") or {}).get("reference"))
                if not pid:
                    continue
                if op is None or threshold is None:
                    # PATCHED (audit fix): no threshold specified on this
                    # rule - presence of a matching-coded observation is the
                    # criterion (e.g. "has an HbA1c result on file"). This
                    # is a legitimate rule shape, kept as a fallback.
                    ids.add(pid)
                    continue
                # PATCHED (audit fix): compare the actual result value
                # against the rule's threshold instead of matching on code
                # presence alone.
                obs_value = (resource.get("valueQuantity") or {}).get("value")
                if obs_value is not None and _compare(obs_value, op, threshold):
                    ids.add(pid)
            return ids

        # kind == "demographic"
        ids = set()
        for resource in self.fhir.search("Patient", {}):
            pid = resource.get("id")
            if pid and _evaluate_demographic(rule, resource):
                ids.add(pid)
        return ids


def run_query(db: Session, run_id: str, *, fhir_client: FHIRClient | None = None) -> int:
    """Execute the given query run, persist results, return match count."""

    qr = db.get(QueryRun, run_id)
    if qr is None:
        raise QueryExecutionError(f"QueryRun {run_id} not found")

    if qr.status == "cancelled":
        # User cancelled between claim and execution; do not run.
        return 0

    cs = db.get(CriteriaSet, qr.criteria_set_id)
    if cs is None:
        raise QueryExecutionError("CriteriaSet missing for run")

    qr.status = "running"
    db.commit()

    started = time.monotonic()
    try:
        client = fhir_client
        owns_client = False
        if client is None:
            client = FHIRClient(os.getenv("FHIR_BASE_URL", ""), os.getenv("FHIR_ACCESS_TOKEN"))
            owns_client = True
        try:
            matches = QueryExecutor(client).execute(cs.logic_json or {})

            # Restrict to patients seen by the study's PI / Sub-Investigators,
            # if any are configured. None means "no restriction".
            from app.services.investigators import (
                allowed_patient_ids,
                list_practitioner_refs,
            )

            practitioner_refs = list_practitioner_refs(db, qr.study_id)
            allowed = allowed_patient_ids(client, practitioner_refs)
            if allowed is not None:
                matches = {pid: rules for pid, rules in matches.items() if pid in allowed}
        finally:
            if owns_client:
                client.close()

        # Wipe any prior results then write fresh
        db.query(QueryResult).filter(QueryResult.query_run_id == qr.id).delete()
        for patient_id, rule_ids in matches.items():
            db.add(
                QueryResult(
                    query_run_id=qr.id,
                    patient_id=patient_id,
                    mrn_hash=_hash_mrn(patient_id),
                    matched_rules_json={"rules": rule_ids},
                    primary_match_reason=rule_ids[0] if rule_ids else None,
                )
            )
        qr.result_count = len(matches)
        qr.execution_ms = int((time.monotonic() - started) * 1000)
        # Respect a cancel that arrived mid-execution.
        if _current_status(db, qr.id) != "cancelled":
            qr.status = "completed"
        db.commit()
        return len(matches)
    except Exception as exc:  # noqa: BLE001 - record failure then re-raise
        qr.execution_ms = int((time.monotonic() - started) * 1000)
        if _current_status(db, qr.id) != "cancelled":
            qr.status = "failed"
        db.commit()
        raise QueryExecutionError(str(exc)) from exc


__all__ = ["QueryExecutor", "QueryExecutionError", "run_query"]
