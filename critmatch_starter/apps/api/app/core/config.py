"""Centralised runtime configuration.

All environment variables are read here so the rest of the codebase can
import typed settings instead of sprinkling ``os.getenv`` calls.

PATCHED (audit fix): added ``dev_login_secret`` (optional, backward
compatible - see routes/auth.py) and ``allow_unverified_smart_id_token``
(replaces an ``is_production``-only check in routes/auth.py's
smart_callback - see that file for the full rationale).
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
    # Optional CSV of additional origins (e.g. Netlify preview deploys).
    extra_allowed_origins: list[str] = field(
        default_factory=lambda: _split_csv(os.getenv("ALLOWED_ORIGINS", ""))
    )
    # Optional regex for dynamic origins (e.g. r"https://.*--critmatch-software\.netlify\.app").
    allowed_origin_regex: str = field(
        default_factory=lambda: os.getenv("ALLOWED_ORIGIN_REGEX", "")
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
    # Allowed email domains for first-party email login and SMART users
    # whose id_token contains an email claim.
    login_email_domain_allowlist: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv(
                "LOGIN_EMAIL_DOMAIN_ALLOWLIST",
                "critmatchresearch.com,elionyxhealth.com",
            )
        )
    )

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
    # PATCHED (audit fix): optional shared secret required by /dev-login
    # when set. Empty by default - no behavior change unless an operator
    # opts in.
    dev_login_secret: str = field(
        default_factory=lambda: os.getenv("DEV_LOGIN_SECRET", "")
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def allow_unverified_smart_id_token(self) -> bool:
        """PATCHED (audit fix): explicit allowlist of environments that may
        accept a SMART id_token whose signature couldn't be verified
        (issuer JWKS unreachable), instead of the previous
        production-vs-everything-else check. Any APP_ENV value not in this
        set - most importantly "staging"/"qa"-style environments that often
        share real SMART credentials with production - now requires real
        signature verification.
        """
        return self.app_env.lower() in {"local", "development", "dev", "test"}

    @property
    def allowed_origins(self) -> list[str]:
        origins: list[str] = []
        if self.frontend_base_url:
            origins.append(self.frontend_base_url)
        for o in self.extra_allowed_origins:
            cleaned = o.rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
        if not origins:
            origins = ["http://localhost:3000"]
        return origins


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
