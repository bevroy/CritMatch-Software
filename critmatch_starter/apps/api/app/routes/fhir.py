"""FHIR connectivity probe (admin-only), plus SMART launch verification."""

from __future__ import annotations

import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.config import get_settings
from app.core.security import issue_session_token
from app.db.models import User
from app.deps.auth import get_current_user, require_roles
from app.fhir.client import FHIRClient, FHIRError
from app.routes.auth import set_session_cookie
from app.services.smart_token import SmartTokenRefreshError, ensure_fresh_session_claims

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


@router.get("/launch-context")
def launch_context(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Verify a live SMART launch session against an Epic/Cerner sandbox.

    Unlike ``ping()`` above (which checks connectivity to the
    system-configured ``FHIR_BASE_URL`` with no patient context), this uses
    the *launch's own* access token and FHIR server - both persisted on the
    session cookie by ``routes/auth.py::smart_callback`` - to read the
    launched patient plus a few active Condition entries. That's proof the
    end-to-end SMART launch actually authenticates real FHIR reads, not just
    that the OAuth handshake completed.

    Reads only Patient and Condition - both already covered by
    SMART_REQUESTED_SCOPE in routes/auth.py - rather than requesting any
    additional scope just for this verification endpoint.

    Built for sandbox verification, not the cohort-matching flow (which
    reads via a separately configured system-level FHIR_BASE_URL/token).
    """

    settings = get_settings()
    claims = getattr(request.state, "session_claims", {}) or {}
    patient_id = claims.get("patient")
    if not patient_id:
        raise HTTPException(
            status_code=400,
            detail="No patient context on this session - launch from an EHR with a patient selected",
        )
    if not claims.get("access_token") or not claims.get("fhir_base_url"):
        raise HTTPException(
            status_code=400,
            detail="No FHIR access token on this session - this session wasn't established via SMART launch",
        )

    try:
        claims, refreshed = ensure_fresh_session_claims(claims, settings=settings)
    except SmartTokenRefreshError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if refreshed:
        set_session_cookie(
            response,
            settings,
            issue_session_token({"sub": str(user.id), "role": user.role, **claims}),
        )

    client = FHIRClient(claims["fhir_base_url"], claims["access_token"])
    try:
        patient = client.read(f"Patient/{patient_id}")
        conditions = list(
            client.search(
                "Condition",
                {"patient": patient_id},
                page_limit=1,
                on_limit="truncate",
            )
        )
    except FHIRError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"FHIR read failed ({type(exc).__name__}): {exc}",
        ) from exc
    finally:
        client.close()

    name = (patient.get("name") or [{}])[0]
    display_name = (
        " ".join([*(name.get("given") or []), name.get("family") or ""]).strip()
        or patient.get("id")
    )

    def _condition_summary(c: dict) -> dict:
        code = c.get("code") or {}
        coding = (code.get("coding") or [{}])[0]
        clinical_status = (
            ((c.get("clinicalStatus") or {}).get("coding") or [{}])[0].get("code")
        )
        return {
            "name": coding.get("display") or code.get("text"),
            "clinical_status": clinical_status,
        }

    return {
        "iss": claims.get("fhir_base_url"),
        "patient_id": patient_id,
        "patient_name": display_name,
        "birth_date": patient.get("birthDate"),
        "gender": patient.get("gender"),
        "condition_count": len(conditions),
        "conditions": [_condition_summary(c) for c in conditions],
    }
