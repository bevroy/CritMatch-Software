from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import audit, auth, query, studies, terminology
from app.sentry_setup import init_sentry

init_sentry()

app = FastAPI(title="CritMatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(studies.router, prefix="/api/studies", tags=["studies"])
app.include_router(terminology.router, prefix="/api/terminology", tags=["terminology"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
