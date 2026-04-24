"""SMART on FHIR launch endpoints.

The launch follows the standard SMART App Launch flow:

1. The EHR redirects the browser to the frontend with ``iss`` and ``launch``.
2. The frontend asks ``POST /api/auth/smart/authorize`` for an authorisation URL.
   We discover the EHR's OAuth endpoints from
   ``${iss}/.well-known/smart-configuration``, generate state + PKCE, and return
   the URL to redirect the user agent to.
3. After consent the EHR redirects back to the frontend, which forwards the
   ``code`` + ``state`` to ``POST /api/auth/smart/callback``.
4. We verify state + exchange the code for tokens, validate the id_token,
   upsert the user and issue a signed session cookie.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    generate_pkce_pair,
    generate_state,
    issue_session_token,
    verify_smart_id_token,
)
from app.db.models import User
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.services.audit_service import record as record_audit

router = APIRouter()


# In-memory state store. For multi-instance deployments swap for Redis or DB.
_state_store: dict[str, dict[str, Any]] = {}
_STATE_TTL_SECONDS = 600


def _store_state(state: str, payload: dict[str, Any]) -> None:
    payload["_expires"] = time.time() + _STATE_TTL_SECONDS
    _state_store[state] = payload
    now = time.time()
    expired = [k for k, v in _state_store.items() if v.get("_expires", 0) < now]
    for k in expired:
        _state_store.pop(k, None)


def _consume_state(state: str) -> dict[str, Any] | None:
    payload = _state_store.pop(state, None)
    if not payload or payload.get("_expires", 0) < time.time():
        return None
    return payload


def _smart_configuration(iss: str) -> dict[str, Any]:
    well_known = iss.rstrip("/") + "/.well-known/smart-configuration"
    resp = httpx.get(well_known, timeout=10, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="SMART configuration not available")
    return resp.json()


class AuthorizeRequest(BaseModel):
    iss: str = Field(..., description="The FHIR server issuer URL provided by the EHR launch")
    launch: str | None = Field(None, description="Opaque launch token from the EHR")
    scope: str = Field(
        default="openid fhirUser launch patient/*.read offline_access",
        description="OAuth scopes to request",
    )


class AuthorizeResponse(BaseModel):
    authorize_url: str
    state: str


class CallbackRequest(BaseModel):
    code: str
    state: str


class SessionResponse(BaseModel):
    user_id: str
    role: str
    patient_context: str | None = None
    signature_verified: bool


@router.post("/smart/authorize", response_model=AuthorizeResponse)
def smart_authorize(payload: AuthorizeRequest) -> AuthorizeResponse:
    settings = get_settings()
    if not settings.smart_client_id:
        raise HTTPException(status_code=503, detail="SMART_CLIENT_ID not configured")
    if not settings.smart_redirect_uri:
        raise HTTPException(status_code=503, detail="SMART_REDIRECT_URI not configured")

    if settings.smart_issuer_allowlist and payload.iss not in settings.smart_issuer_allowlist:
        raise HTTPException(status_code=403, detail="Issuer not in allowlist")

    smart_config = _smart_configuration(payload.iss)
    authorization_endpoint = smart_config.get("authorization_endpoint")
    token_endpoint = smart_config.get("token_endpoint")
    jwks_uri = smart_config.get("jwks_uri")
    if not authorization_endpoint or not token_endpoint:
        raise HTTPException(status_code=502, detail="Issuer SMART configuration incomplete")

    state = generate_state()
    verifier, challenge = generate_pkce_pair()
    _store_state(
        state,
        {
            "iss": payload.iss,
            "token_endpoint": token_endpoint,
            "jwks_uri": jwks_uri,
            "code_verifier": verifier,
        },
    )

    params = {
        "response_type": "code",
        "client_id": settings.smart_client_id,
        "redirect_uri": settings.smart_redirect_uri,
        "scope": payload.scope,
        "state": state,
        "aud": payload.iss,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if payload.launch:
        params["launch"] = payload.launch

    url = httpx.URL(authorization_endpoint).copy_merge_params(params)
    return AuthorizeResponse(authorize_url=str(url), state=state)


@router.post("/smart/callback", response_model=SessionResponse)
def smart_callback(
    payload: CallbackRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    settings = get_settings()
    if not settings.smart_client_id or not settings.smart_client_secret:
        raise HTTPException(status_code=503, detail="SMART credentials not configured")

    state_data = _consume_state(payload.state)
    if not state_data:
        raise HTTPException(status_code=400, detail="Unknown or expired state")

    token_resp = httpx.post(
        state_data["token_endpoint"],
        data={
            "grant_type": "authorization_code",
            "code": payload.code,
            "redirect_uri": settings.smart_redirect_uri,
            "client_id": settings.smart_client_id,
            "client_secret": settings.smart_client_secret,
            "code_verifier": state_data["code_verifier"],
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Token exchange failed")
    tokens = token_resp.json()

    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=502, detail="id_token missing from token response")

    try:
        id_claims = verify_smart_id_token(
            id_token,
            audience=settings.smart_client_id,
            issuer=state_data["iss"],
            jwks_uri=state_data.get("jwks_uri"),
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"id_token verification failed: {exc}") from exc

    if settings.is_production and not id_claims.get("_signature_verified"):
        raise HTTPException(
            status_code=502,
            detail="Issuer JWKS unavailable; refusing to trust unsigned id_token in production",
        )

    ehr_user_id = str(id_claims.get("sub") or id_claims.get("fhirUser") or "unknown")
    fhir_user = id_claims.get("fhirUser")
    patient_id = tokens.get("patient")

    user = db.query(User).filter(User.ehr_user_id == ehr_user_id).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            ehr_user_id=ehr_user_id,
            name=id_claims.get("name") or "EHR User",
            email=id_claims.get("email"),
        )
        db.add(user)
        db.flush()

    record_audit(
        db,
        user_id=user.id,
        action="smart_launch",
        object_type="session",
        object_id=patient_id,
        request=request,
        extra={
            "iss": state_data["iss"],
            "fhirUser": fhir_user,
            "signature_verified": id_claims.get("_signature_verified", False),
        },
    )
    db.commit()

    session_token = issue_session_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": state_data["iss"],
            "patient": patient_id,
            "fhirUser": fhir_user,
            "scope": tokens.get("scope"),
        }
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.is_production or settings.session_cookie_samesite == "none",
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )

    return SessionResponse(
        user_id=str(user.id),
        role=user.role,
        patient_context=patient_id,
        signature_verified=bool(id_claims.get("_signature_verified")),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=SessionResponse)
def me(request: Request, user: CurrentUser) -> SessionResponse:
    claims = getattr(request.state, "session_claims", {}) or {}
    return SessionResponse(
        user_id=str(user.id),
        role=user.role,
        patient_context=claims.get("patient"),
        signature_verified=bool(claims.get("_signature_verified", True)),
    )


# ---------------------------------------------------------------------------
# Dev login (non-production convenience)
# ---------------------------------------------------------------------------


class DevLoginRequest(BaseModel):
    name: str = Field(default="Dev User")
    role: str = Field(default="research_user")


@router.post("/dev-login", response_model=SessionResponse)
def dev_login(
    payload: DevLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    settings = get_settings()
    if not settings.dev_login_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if settings.is_production and not settings.dev_login_allow_prod:
        raise HTTPException(status_code=403, detail="Dev login disabled in production")
    if payload.role not in {"research_user", "admin", "auditor"}:
        raise HTTPException(status_code=400, detail="Unsupported role")

    ehr_user_id = f"dev:{payload.role}:{payload.name}"
    try:
        user = db.query(User).filter(User.ehr_user_id == ehr_user_id).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                ehr_user_id=ehr_user_id,
                name=payload.name,
                role=payload.role,
            )
            db.add(user)
            db.flush()
        else:
            user.role = payload.role

        record_audit(
            db,
            user_id=user.id,
            action="dev_login",
            object_type="session",
            object_id=str(user.id),
            request=request,
            extra={"role": payload.role, "app_env": settings.app_env},
        )
        db.commit()

        session_token = issue_session_token(
            {
                "sub": str(user.id),
                "role": user.role,
                "iss": "dev",
                "patient": None,
                "fhirUser": None,
                "scope": "dev",
            }
        )
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_token,
            httponly=True,
            secure=settings.is_production or settings.session_cookie_samesite == "none",
            samesite=settings.session_cookie_samesite,
            max_age=settings.session_ttl_seconds,
            path="/",
        )

        return SessionResponse(
            user_id=str(user.id),
            role=user.role,
            patient_context=None,
            signature_verified=True,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surface configuration errors
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"dev_login failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/dev-login/enabled")
def dev_login_enabled() -> dict:
    settings = get_settings()
    available = settings.dev_login_enabled and (
        not settings.is_production or settings.dev_login_allow_prod
    )
    return {"enabled": bool(available)}
