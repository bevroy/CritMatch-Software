"""FHIR connectivity probe (admin-only)."""

from __future__ import annotations

import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.db.models import User
from app.deps.auth import require_roles

router = APIRouter()


@router.get("/ping")
def ping(
    _user: Annotated[User, Depends(require_roles("admin"))],
) -> dict:
    """Hit the configured FHIR server's CapabilityStatement and report status.

    Returns a small, opinionated summary so the admin UI can show a
    one-glance health badge without leaking PHI.
    """

    settings = get_settings()
    base = settings.fhir_base_url.rstrip("/") if settings.fhir_base_url else ""
    if not base:
        return {
            "ok": False,
            "configured": False,
            "reason": "FHIR_BASE_URL not configured",
        }

    url = f"{base}/metadata"
    started = time.monotonic()
    try:
        resp = httpx.get(
            url,
            headers={"Accept": "application/fhir+json"},
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "configured": True,
            "url": base,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if resp.status_code != 200:
        return {
            "ok": False,
            "configured": True,
            "url": base,
            "status": resp.status_code,
            "elapsedMs": elapsed_ms,
            "reason": resp.text[:200],
        }

    body: dict = {}
    try:
        body = resp.json()
    except ValueError:
        return {
            "ok": False,
            "configured": True,
            "url": base,
            "elapsedMs": elapsed_ms,
            "reason": "Non-JSON response",
        }

    rest = (body.get("rest") or [{}])[0]
    resources = [r.get("type") for r in (rest.get("resource") or []) if r.get("type")]

    return {
        "ok": True,
        "configured": True,
        "url": base,
        "elapsedMs": elapsed_ms,
        "fhirVersion": body.get("fhirVersion"),
        "software": (body.get("software") or {}).get("name"),
        "publisher": body.get("publisher"),
        "resourceTypes": sorted(resources)[:50],
        "resourceCount": len(resources),
    }
