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

PATCHED (audit fix, critical): ``smart_authorize()`` used to only reject an
issuer when the allowlist was BOTH configured AND didn't contain it -
``if settings.smart_issuer_allowlist and payload.iss not in ...`` - so an
unset/empty ``SMART_ISSUER_ALLOWLIST`` (which is ``sync: false`` in
render.yaml, i.e. nothing forces an operator to set it) made the check a
no-op. ``payload.iss`` was then fully attacker-controlled, and the server
made an unrestricted ``httpx.get`` to ``{iss}/.well-known/smart-configuration``
(SSRF) whose response's ``token_endpoint`` was later POSTed the app's own
``SMART_CLIENT_SECRET`` in ``smart_callback()``. An attacker supplying their
own ``iss`` and completing their own code/state round trip could make the
API leak its SMART client secret to a server they control. Now fails closed:
an empty allowlist rejects every issuer instead of allowing all of them.
"""

from __future__ import annotations

import time
import uuid
import base64
import hashlib
import hmac
import secrets
from email.utils import parseaddr
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


class EmailLoginRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


def _normalize_email(value: str) -> str:
    _name, email = parseaddr((value or "").strip())
    return email.strip().lower()


def _is_allowed_email(email: str, settings) -> bool:
    if not email:
        return False
    allowed = {d.strip().lower() for d in settings.login_email_domain_allowlist if d.strip()}
    if not allowed:
        return False
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1]
    return domain in allowed


def _issue_session_cookie(response: Response, settings, user: User, claims: dict[str, Any]) -> None:
    session_token = issue_session_token(
        {
            "sub": str(user.id),
            "role": user.role,
            **claims,
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


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iter_s, salt_b64, hash_b64 = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


@router.post("/login", response_model=SessionResponse)
def email_login(
    payload: EmailLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    """First-party email login.

    This flow is intentionally simple for CritMatch's operator-managed
    deployments: only users with an allowed email domain may sign in.
    """

    settings = get_settings()
    email = _normalize_email(payload.email)
    password = (payload.password or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not _is_allowed_email(email, settings):
        raise HTTPException(
            status_code=403,
            detail="Email domain not allowed. Access is limited to approved organizational domains.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        display_name = (payload.name or "").strip() or email.split("@", 1)[0]
        user = User(
            id=uuid.uuid4(),
            ehr_user_id=f"email:{email}",
            name=display_name,
            email=email,
            role="research_user",
            password_hash=_hash_password(password),
        )
        db.add(user)
        db.flush()
    elif not user.email:
        user.email = email
    if user.password_hash:
        if not _verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
    else:
        # Backward compatibility for existing first-party accounts created
        # before password support was introduced.
        if (user.ehr_user_id or "").startswith("email:"):
            user.password_hash = _hash_password(password)
        else:
            raise HTTPException(
                status_code=403,
                detail="Password login is not enabled for this account. Use SMART launch sign-in.",
            )

    record_audit(
        db,
        user_id=user.id,
        action="email_login",
        object_type="session",
        object_id=str(user.id),
        request=request,
        extra={"email_domain": email.rsplit("@", 1)[1]},
    )
    db.commit()

    _issue_session_cookie(
        response,
        settings,
        user,
        {
            "iss": "email-login",
            "patient": None,
            "fhirUser": None,
            "scope": "email-login",
            "_signature_verified": True,
        },
    )
    return SessionResponse(
        user_id=str(user.id),
        role=user.role,
        patient_context=None,
        signature_verified=True,
    )


@router.post("/smart/authorize", response_model=AuthorizeResponse)
def smart_authorize(payload: AuthorizeRequest) -> AuthorizeResponse:
    settings = get_settings()
    if not settings.smart_client_id:
        raise HTTPException(status_code=503, detail="SMART_CLIENT_ID not configured")
    if not settings.smart_redirect_uri:
        raise HTTPException(status_code=503, detail="SMART_REDIRECT_URI not configured")

    # PATCHED (audit fix, critical): fail closed. An empty allowlist now
    # rejects every issuer instead of skipping the check entirely - see
    # module docstring. If you're hitting this in development against a
    # sandbox FHIR server, add it explicitly to SMART_ISSUER_ALLOWLIST (see
    # .env.example) rather than leaving the var unset.
    if not settings.smart_issuer_allowlist:
        raise HTTPException(
            status_code=503,
            detail="SMART_ISSUER_ALLOWLIST not configured; refusing to accept any issuer",
        )
    if payload.iss not in settings.smart_issuer_allowlist:
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

    # PATCHED (audit fix, medium): previously only refused an unverified
    # id_token when settings.is_production was true - so any deployment
    # whose APP_ENV was neither "production"/"prod" nor "development"/"dev"/
    # "local"/"test" (e.g. a "staging" or "qa" environment sharing real
    # SMART_CLIENT_ID/SECRET) would silently accept a structurally-valid but
    # signature-unverified id_token. Now gated on the explicit allowlist in
    # Settings.allow_unverified_smart_id_token instead of an is-it-production
    # check, so anything not explicitly recognized as a local/dev/test
    # environment requires real signature verification.
    if not settings.allow_unverified_smart_id_token and not id_claims.get("_signature_verified"):
        raise HTTPException(
            status_code=502,
            detail="Issuer JWKS unavailable; refusing to trust unsigned id_token outside local/dev/test",
        )

    ehr_user_id = str(id_claims.get("sub") or id_claims.get("fhirUser") or "unknown")
    fhir_user = id_claims.get("fhirUser")
    patient_id = tokens.get("patient")
    id_email = _normalize_email(str(id_claims.get("email") or ""))
    if not _is_allowed_email(id_email, settings):
        raise HTTPException(
            status_code=403,
            detail="Login denied: only approved organizational email domains may access CritMatch",
        )

    user = db.query(User).filter(User.ehr_user_id == ehr_user_id).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            ehr_user_id=ehr_user_id,
            name=id_claims.get("name") or "EHR User",
            email=id_email,
        )
        db.add(user)
        db.flush()
    elif id_email and user.email != id_email:
        user.email = id_email

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

    _issue_session_cookie(
        response,
        settings,
        user,
        {
            "iss": state_data["iss"],
            "patient": patient_id,
            "fhirUser": fhir_user,
            "scope": tokens.get("scope"),
            "_signature_verified": bool(id_claims.get("_signature_verified")),
        },
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
    # PATCHED (audit fix, medium, backward compatible): optional shared
    # secret. If DEV_LOGIN_SECRET is unset (the default), behavior is
    # unchanged. If an operator sets it, this endpoint additionally
    # requires the caller to know it - cheap extra friction against the
    # "DEV_LOGIN_ENABLED and DEV_LOGIN_ALLOW_PROD both left on by accident"
    # scenario flagged in the audit, without changing the default.
    token: str | None = Field(default=None)


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
    if settings.dev_login_secret:
        import secrets as _secrets

        if not payload.token or not _secrets.compare_digest(payload.token, settings.dev_login_secret):
            raise HTTPException(status_code=403, detail="Invalid dev login token")
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

        _issue_session_cookie(
            response,
            settings,
            user,
            {
                "iss": "dev",
                "patient": None,
                "fhirUser": None,
                "scope": "dev",
                "_signature_verified": True,
            },
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
