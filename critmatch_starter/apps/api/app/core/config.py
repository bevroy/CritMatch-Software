"""Centralised runtime configuration.

All environment variables are read here so the rest of the codebase can
import typed settings instead of sprinkling ``os.getenv`` calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))

    # Frontend / CORS
    frontend_base_url: str = field(
        default_factory=lambda: (os.getenv("FRONTEND_BASE_URL") or "").rstrip("/")
    )

    # Database
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Session signing
    session_secret: str = field(default_factory=lambda: os.getenv("SESSION_SECRET", ""))
    session_cookie_name: str = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_NAME", "critmatch_session")
    )
    session_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 8)))
    )
    # "lax" works for same-site deployments. For a Netlify frontend talking to a
    # Render API on a different domain, set this to "none" (and the cookie will
    # be marked Secure automatically).
    session_cookie_samesite: str = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()
    )

    # SMART on FHIR
    smart_client_id: str = field(default_factory=lambda: os.getenv("SMART_CLIENT_ID", ""))
    smart_client_secret: str = field(
        default_factory=lambda: os.getenv("SMART_CLIENT_SECRET", "")
    )
    smart_issuer_allowlist: list[str] = field(
        default_factory=lambda: _split_csv(os.getenv("SMART_ISSUER_ALLOWLIST", ""))
    )
    smart_redirect_uri: str = field(default_factory=lambda: os.getenv("SMART_REDIRECT_URI", ""))
    fhir_base_url: str = field(default_factory=lambda: os.getenv("FHIR_BASE_URL", ""))

    # Export signing
    export_signing_key: str = field(
        default_factory=lambda: os.getenv("EXPORT_SIGNING_KEY", "")
    )

    # Dev-only: mint a local session without a real EHR. Off by default and
    # ignored in production unless DEV_LOGIN_ALLOW_PROD=1 is also set.
    dev_login_enabled: bool = field(
        default_factory=lambda: os.getenv("DEV_LOGIN_ENABLED", "0") in {"1", "true", "True"}
    )
    dev_login_allow_prod: bool = field(
        default_factory=lambda: os.getenv("DEV_LOGIN_ALLOW_PROD", "0") in {"1", "true", "True"}
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def allowed_origins(self) -> list[str]:
        if self.frontend_base_url:
            return [self.frontend_base_url]
        return ["http://localhost:3000"]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
