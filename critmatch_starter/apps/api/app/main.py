from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes import (
    audit,
    auth,
    ctfms,
    edc,
    feasibility,
    fhir,
    notifications,
    query,
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

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(studies.router, prefix="/api/studies", tags=["studies"])
app.include_router(terminology.router, prefix="/api/terminology", tags=["terminology"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(fhir.router, prefix="/api/fhir", tags=["fhir"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(feasibility.router, prefix="/api/feasibility", tags=["feasibility"])
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
