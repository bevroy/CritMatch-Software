"""FHIR pulls for EDC fields.

Each field can carry a ``fhir_mapping_json`` describing how to retrieve
its value from the EMR for a given participant. The shape is intentionally
small:

    {
      "resource": "Observation",
      "params":   {"code": "http://loinc.org|8480-6"},
      "extract":  "valueQuantity.value",
      "sort":     "-date",
      "unit":     "mm[Hg]"            # optional metadata
    }

``extract`` is a tiny dotted-path evaluator (no FHIRPath dependency); it
supports ``a.b.c`` and ``[N]`` indexing (e.g. ``component[0].valueQuantity.value``).

For Patient demographics we accept ``{"resource": "Patient", "extract": "..."}``
without ``params`` and read by id.

PATCHED (audit fix, high): the ``unit`` mapping key was documented above but
never actually read - ``pull_field_value`` extracted the raw numeric value
and stored it as-is with no check against the unit actually present on the
source Quantity. If a FHIR server records a value in a different unit than
the study expects (mg/dL vs mmol/L, kg vs lb, etc.), the number would be
pulled and persisted silently wrong. There's no safe generic fix - unit
conversion needs a real per-unit-pair table, not a guess - so this now
fails closed: when a mapping declares an expected unit and the source
Quantity's own unit/code disagrees, the pull errors out instead of silently
storing a wrongly-scaled number. Mappings with no declared unit, or sources
with no unit field to compare against, are unaffected.
"""

from __future__ import annotations

import re
from typing import Any

from app.fhir.client import FHIRClient


_INDEX = re.compile(r"\[(\d+)\]")


def _extract(obj: Any, path: str) -> Any:
    if not path:
        return obj
    cur: Any = obj
    for segment in path.split("."):
        if cur is None:
            return None
        # Handle indexed segments like "component[0]"
        m = _INDEX.search(segment)
        if m:
            key = segment[: m.start()]
            idx = int(m.group(1))
            if key:
                cur = cur.get(key) if isinstance(cur, dict) else None
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            cur = cur.get(segment) if isinstance(cur, dict) else None
    return cur


def pull_field_value(
    client: FHIRClient,
    patient_id: str,
    mapping: dict[str, Any],
) -> tuple[Any, str | None]:
    """Return ``(value, source_ref)`` for a single field.

    Raises ``ValueError`` if the mapping is malformed, or (PATCHED) if the
    mapping declares an expected unit that disagrees with the source
    Quantity's own unit. Returns ``(None, None)`` when the EMR has no
    matching resource.
    """

    resource = (mapping or {}).get("resource")
    if not resource:
        raise ValueError("fhir_mapping_json.resource is required")
    extract = mapping.get("extract") or ""
    params: dict[str, Any] = dict(mapping.get("params") or {})

    if resource == "Patient":
        try:
            res = client.read(f"Patient/{patient_id}")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Patient read failed: {exc}") from exc
        return _extract(res, extract), f"Patient/{patient_id}"

    # Most resources are searched against the participant's Patient.
    params.setdefault("subject", f"Patient/{patient_id}")
    if "sort" in mapping:
        params.setdefault("_sort", mapping["sort"])
    params.setdefault("_count", "1")

    chosen: dict[str, Any] | None = None
    # PATCHED (audit fix): explicit on_limit="truncate" - this call already
    # scopes the search tightly (_count=1, page_limit=1) and only wants a
    # best-effort single most-recent value, not an exhaustive result set, so
    # the new FHIRSearchTruncated-by-default behavior in fhir/client.py
    # would be the wrong choice here. See that module's docstring.
    for entry in client.search(resource, params, page_limit=1, on_limit="truncate"):
        chosen = entry
        break
    if chosen is None:
        return None, None
    src_ref = f"{resource}/{chosen.get('id', '')}".rstrip("/")

    value = _extract(chosen, extract)

    expected_unit = mapping.get("unit")
    if expected_unit and extract.endswith("valueQuantity.value"):
        qty_path = extract.rsplit(".value", 1)[0]
        quantity_obj = _extract(chosen, qty_path)
        actual_unit = None
        if isinstance(quantity_obj, dict):
            actual_unit = quantity_obj.get("unit") or quantity_obj.get("code")
        if actual_unit and actual_unit != expected_unit:
            raise ValueError(
                f"Unit mismatch pulling {resource}: field mapping expects '{expected_unit}', "
                f"but the source Quantity has unit '{actual_unit}'. Refusing to guess a "
                "conversion - update the field mapping's expected unit, or convert at the "
                "source system, before this field can be pulled automatically."
            )

    return value, src_ref


def pull_all_for_entry(
    client: FHIRClient,
    patient_id: str,
    fields: list[tuple[str, str, dict[str, Any] | None]],
) -> list[dict[str, Any]]:
    """Pull values for every field with a mapping.

    ``fields`` is a list of ``(field_id, field_key, mapping)`` tuples.
    Returns one dict per field with keys ``field_id``, ``field_key``,
    ``value``, ``source_ref``, ``error``.
    """

    out: list[dict[str, Any]] = []
    for field_id, field_key, mapping in fields:
        if not mapping:
            continue
        try:
            value, src_ref = pull_field_value(client, patient_id, mapping)
            out.append(
                {
                    "field_id": field_id,
                    "field_key": field_key,
                    "value": value,
                    "source_ref": src_ref,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "field_id": field_id,
                    "field_key": field_key,
                    "value": None,
                    "source_ref": None,
                    "error": str(exc),
                }
            )
    return out
