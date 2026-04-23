"""Terminology expansion service.

Strategy:

1. If ``TERMINOLOGY_SERVER_URL`` is configured we call ValueSet/$expand on
   the configured server (any FHIR R4 terminology server: tx.fhir.org,
   Ontoserver, the National Library of Medicine FHIR API, etc.). One call
   per requested target code system.
2. Otherwise we fall back to a tiny built-in synonym/code map so the UI
   has something to render in dev/test without external network calls.

The response shape is intentionally stable for the frontend.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# Map a CritMatch system shorthand to a canonical FHIR ValueSet URL or
# CodeSystem URI. Operators can override per-deployment via env.
_DEFAULT_VALUESETS = {
    "ICD10CM": "http://hl7.org/fhir/ValueSet/icd-10-cm",
    "SNOMEDCT": "http://snomed.info/sct?fhir_vs",
    "RXNORM": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "LOINC": "http://loinc.org/vs",
    "CPT": "http://www.ama-assn.org/go/cpt",
}


def _server_url() -> str:
    return (os.getenv("TERMINOLOGY_SERVER_URL") or "").rstrip("/")


def _expand_via_fhir(term: str, system_key: str) -> list[dict[str, str]]:
    base = _server_url()
    valueset = _DEFAULT_VALUESETS.get(system_key)
    if not base or not valueset:
        return []
    try:
        resp = httpx.get(
            f"{base}/ValueSet/$expand",
            params={"url": valueset, "filter": term, "count": 25},
            headers={"Accept": "application/fhir+json"},
            timeout=15,
        )
    except httpx.HTTPError:
        return []
    if resp.status_code != 200:
        return []
    body: dict[str, Any] = resp.json()
    contains = ((body.get("expansion") or {}).get("contains")) or []
    out: list[dict[str, str]] = []
    for item in contains:
        out.append(
            {
                "type": "code",
                "system": system_key,
                "code": item.get("code", ""),
                "display": item.get("display", ""),
            }
        )
    return out


_FALLBACK_NORMALISE = {
    "heart attack": "myocardial infarction",
    "high blood pressure": "essential hypertension",
    "t2dm": "type 2 diabetes mellitus",
}


def _fallback_expand(term: str, target_code_systems: list[str]) -> dict[str, Any]:
    normalized = _FALLBACK_NORMALISE.get(term.lower(), term.lower())
    expansions: list[dict[str, str]] = [
        {"type": "synonym", "display": normalized},
    ]
    if "ICD10CM" in target_code_systems and "myocardial infarction" in normalized:
        expansions.append(
            {"type": "code", "system": "ICD10CM", "code": "I21", "display": "Acute myocardial infarction"}
        )
    if "SNOMEDCT" in target_code_systems and "myocardial infarction" in normalized:
        expansions.append(
            {"type": "code", "system": "SNOMEDCT", "code": "22298006", "display": "Myocardial infarction"}
        )
    return {"normalizedTerm": normalized, "expansions": expansions}


def expand_term(text: str, target_code_systems: list[str]) -> dict[str, Any]:
    if not _server_url():
        return _fallback_expand(text, target_code_systems)

    expansions: list[dict[str, str]] = []
    for system_key in target_code_systems:
        expansions.extend(_expand_via_fhir(text, system_key))

    if not expansions:
        # Server returned nothing useful; surface the original term.
        return {"normalizedTerm": text.lower(), "expansions": []}
    return {"normalizedTerm": text.lower(), "expansions": expansions}
