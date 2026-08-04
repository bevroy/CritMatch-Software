import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.routes import (
    audit,
    auth,
    ctfms,
    edc,
    equity,
    feasibility,
    fhir,
    navigator,
    notifications,
    query,
    readiness,
    roie,
    runs,
    studies,
    terminology,
)
from app.sentry_setup import init_sentry

init_sentry()

settings = get_settings()
app = FastAPI(title="CritMatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# PATCHED (audit fix, high): CSRF guard for state-changing requests.
#
# The API authenticates via a cookie (see app/deps/auth.py), and
# core/config.py's own comment instructs operators to set
# SESSION_COOKIE_SAMESITE=none for exactly the topology this repo ships -
# API on Render, web app on Netlify, different origins. With
# SameSite=None; Secure, browsers attach the session cookie automatically on
# cross-site requests, and until now nothing checked where a mutating
# request actually came from - every state-changing endpoint (create study,
# add/remove collaborator, transfer ownership, sign an EDC entry, etc.) was
# CSRF-exploitable from any third-party page once the deployment followed
# its own documented cross-domain configuration.
#
# This is a backend-only fix - no frontend change needed. It rejects
# POST/PUT/PATCH/DELETE requests whose Origin header (falling back to
# Referer) doesn't match one of the configured allowed origins. Requests
# with neither header (server-to-server calls, curl, the worker process)
# are allowed through: real browsers always send Origin on cross-origin
# fetch/XHR/form submissions, so a request with no Origin/Referer at all
# didn't come from a browser context this check is meant to stop.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_host(value: str) -> str:
    return value.split("://", 1)[-1].split("/", 1)[0]


def _origin_base(value: str) -> str:
    parts = value.split("/", 3)
    return "/".join(parts[:3]) if len(parts) >= 3 else value


class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in _SAFE_METHODS:
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin:
                s = get_settings()
                allowed_hosts = {_origin_host(o) for o in s.allowed_origins}
                ok = _origin_host(origin) in allowed_hosts
                if not ok and s.allowed_origin_regex:
                    try:
                        ok = bool(re.match(s.allowed_origin_regex, _origin_base(origin)))
                    except re.error:
                        ok = False
                if not ok:
                    return JSONResponse(
                        {"detail": "Cross-origin request rejected"}, status_code=403
                    )
        return await call_next(request)


app.add_middleware(OriginCheckMiddleware)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(studies.router, prefix="/api/studies", tags=["studies"])
app.include_router(terminology.router, prefix="/api/terminology", tags=["terminology"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(fhir.router, prefix="/api/fhir", tags=["fhir"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(feasibility.router, prefix="/api/feasibility", tags=["feasibility"])
app.include_router(navigator.router, prefix="/api/navigator", tags=["navigator"])
app.include_router(equity.router, prefix="/api/equity", tags=["equity"])
app.include_router(readiness.router, prefix="/api/readiness", tags=["readiness"])
app.include_router(roie.router, prefix="/api/roie", tags=["roie"])
app.include_router(edc.router, prefix="/api/edc", tags=["edc"])
app.include_router(ctfms.router, prefix="/api/ctfms", tags=["ctfms"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe: verifies DB connectivity when configured."""

    from sqlalchemy import text

    from app.db.session import SessionLocal

    if not settings.session_secret:
        return {"status": "degraded", "reason": "SESSION_SECRET not configured"}
    if SessionLocal is None:
        return {"status": "degraded", "reason": "DATABASE_URL not configured"}
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - surface any DB error
        return {"status": "degraded", "reason": str(exc)[:200]}
    return {"status": "ready"}
