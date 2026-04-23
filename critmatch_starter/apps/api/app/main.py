from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes import audit, auth, query, studies, terminology
from app.sentry_setup import init_sentry

init_sentry()

settings = get_settings()
app = FastAPI(title="CritMatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(studies.router, prefix="/api/studies", tags=["studies"])
app.include_router(terminology.router, prefix="/api/terminology", tags=["terminology"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe: verifies DB connectivity when configured."""

    from sqlalchemy import text

    from app.db.session import SessionLocal

    if SessionLocal is None:
        return {"status": "degraded", "reason": "DATABASE_URL not configured"}
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - surface any DB error
        return {"status": "degraded", "reason": str(exc)[:200]}
    return {"status": "ready"}
