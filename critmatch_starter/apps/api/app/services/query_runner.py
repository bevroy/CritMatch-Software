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
   UPDATE: the demographic branch now also pushes whatever it can down to
   the server as real FHIR search params (``birthdate=le/lt/ge/gt...`` for
   ``age`` comparisons, ``gender=`` for an exact ``gender`` match - see
   ``_demographic_search_params()``) instead of always fetching the entire
   compartment, and uses a higher ``page_limit`` (``_DEMOGRAPHIC_PAGE_LIMIT``)
   for whatever can't be narrowed server-side (e.g. ``==``/``!=`` on age).
   ``_evaluate_demographic()`` still re-checks every resource returned, so an
   inexact or missing server-side mapping only costs extra fetched pages, not
   a correctness bug - and ``FHIRSearchTruncated`` still fires, unchanged, if
   even the raised limit isn't enough.
2. ``medication`` was documented in ``CriteriaSet``'s own schema
   (condition | observation | medication | demographic) but had no branch
   in ``_patients_matching()`` - it fell through to ``return set()``. Under
   AND logic that silently zeroed the *entire* result for any criteria set
   containing a medication rule, while ``QueryRun.status`` still read
   "completed". Added a branch searching ``MedicationRequest`` by code,
   mirroring the ``condition``/``observation`` pattern.
   UPDATE: some EHRs (including some Epic/Cerner configurations) populate
   active medications primarily via ``MedicationStatement`` rather than
   ``MedicationRequest`` - originally flagged here as a known gap rather
   than guessed at, since which resource type a given FHIR server actually
   populates is deployment-specific. The ``medication`` branch now searches
   both resource types and unions the matched patient ids, so a criteria
   set matches regardless of which resource type the source EHR uses.
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
   UPDATE: ``observation`` rules also matched on ``code`` alone with no
   check on ``Observation.category``, so a code that coincidentally also
   appears on an unrelated-category Observation (e.g. a survey/imaging
   resource reusing the same LOINC code as a vital-signs one) could produce
   a false match. Rules may now set an optional ``category`` - either a bare
   US Core category code (``"vital-signs"``, ``"laboratory"``,
   ``"social-history"``, etc, assumed to be in
   ``http://terminology.hl7.org/CodeSystem/observation-category``) or an
   explicit ``{"system", "code"}`` mapping - and a candidate Observation must
   carry that coding in ``category`` to count. When a rule doesn't specify a
   category, this deliberately does NOT guess one: falls back to the
   original code-only behavior, since inventing a category filter could
   wrongly exclude otherwise-valid matches.

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

# Demographic Patient searches can't always be narrowed server-side (e.g. an
# exact age match, or a FHIR server that ignores unrecognized params), so this
# path gets a higher bound than FHIRClient.search()'s default page_limit=20 -
# still bounded, and FHIRSearchTruncated still fires if even this is exceeded.
_DEMOGRAPHIC_PAGE_LIMIT = 200


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
    # PATCHED (audit fix): fail closed instead of silently hashing with an
    # empty salt - matches the SESSION_SECRET/EXPORT_SIGNING_KEY pattern used
    # elsewhere in this codebase. An unsalted sha256 of a patient id is
    # guessable for small id spaces, so refuse rather than produce a
    # weakly-hashed mrn_hash.
    salt = os.getenv("MRN_HASH_SALT")
    if not salt:
        raise QueryExecutionError("MRN_HASH_SALT not configured; refusing to hash patient identifiers")
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


_OBSERVATION_CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category"


def _normalize_expected_category(category: Any) -> tuple[str | None, str] | None:
    """Return ``(system_or_None, code)`` for a rule's expected observation
    category, or ``None`` if the rule didn't specify one.

    Accepts either a bare code string (assumed to be in the standard US Core
    ``observation-category`` system) or an explicit ``{"system", "code"}``
    mapping for callers that need a non-standard category system.
    """
    if not category:
        return None
    if isinstance(category, str):
        return (_OBSERVATION_CATEGORY_SYSTEM, category)
    if isinstance(category, dict):
        code = category.get("code")
        if not code:
            return None
        return (category.get("system") or None, code)
    return None


def _observation_has_category(resource: dict[str, Any], expected: tuple[str | None, str]) -> bool:
    """True if ``resource["category"]`` contains a coding matching ``expected``."""
    expected_system, expected_code = expected
    for category in resource.get("category", []) or []:
        for coding in category.get("coding", []) or []:
            if coding.get("code") != expected_code:
                continue
            if expected_system is None or coding.get("system") == expected_system:
                return True
    return False


def _demographic_search_params(rule: dict[str, Any]) -> dict[str, str]:
    """Best-effort real FHIR search params to narrow a demographic Patient
    search server-side, instead of always fetching the whole compartment.

    Purely an optimization: the caller still re-checks every resource
    returned via ``_evaluate_demographic()``, so a rule shape this can't
    map (e.g. an exact age match, or an unrecognized ``field``) just falls
    back to fetching more broadly - never a correctness bug.
    """
    field = rule.get("field")
    op = rule.get("op", "==")
    value = rule.get("value")

    if field == "gender" and op == "==" and value:
        return {"gender": str(value)}

    if field == "age":
        # age <op> N <=> birthDate <inverted-op> (today - N years); e.g.
        # "age >= 18" means born on or before 18 years ago, i.e. birthdate<=cutoff.
        prefix = {">=": "le", ">": "lt", "<=": "ge", "<": "gt"}.get(op)
        if prefix is None:
            return {}
        try:
            age_years = int(value)
        except (TypeError, ValueError):
            return {}
        today = datetime.utcnow().date()
        try:
            cutoff = today.replace(year=today.year - age_years)
        except ValueError:
            # Feb 29 birthday with no Feb 29 in the cutoff year.
            cutoff = today.replace(month=2, day=28, year=today.year - age_years)
        return {"birthdate": f"{prefix}{cutoff.isoformat()}"}

    return {}


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
            # PATCHED (audit fix): searches both MedicationRequest and
            # MedicationStatement - see module docstring. Matches are merged
            # by adding to the same patient-id set, so a patient represented
            # in both resource types is naturally deduplicated (not a double
            # count), and a patient found via either resource type matches.
            value = _coding_param(rule.get("codes", []))
            if not value:
                return set()
            ids = set()
            for resource_type in ("MedicationRequest", "MedicationStatement"):
                for resource in self.fhir.search(resource_type, {"code": value}):
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
            expected_category = _normalize_expected_category(rule.get("category"))
            ids = set()
            for resource in self.fhir.search("Observation", {"code": value}):
                if expected_category is not None and not _observation_has_category(
                    resource, expected_category
                ):
                    # PATCHED (audit fix): the rule specified which category
                    # it expects (e.g. vital-signs) and this Observation's
                    # code matched but its category didn't - a coincidental
                    # cross-category code collision, not a real match.
                    continue
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
        search_params = _demographic_search_params(rule)
        ids = set()
        for resource in self.fhir.search(
            "Patient", search_params, page_limit=_DEMOGRAPHIC_PAGE_LIMIT
        ):
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
