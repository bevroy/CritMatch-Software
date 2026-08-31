"""SMART access token freshness + refresh.

Mirrors the token-exchange approach ``routes/auth.py``'s ``smart_callback``
uses for the initial code exchange: discover the issuer's OAuth endpoints
from ``.well-known/smart-configuration`` and POST to its ``token_endpoint`` -
just with ``grant_type=refresh_token`` instead of ``authorization_code``.
"""

from __future__ import annotations

import time
from typing import Any

import httpx


class SmartConfigurationError(RuntimeError):
    pass


class SmartTokenRefreshError(RuntimeError):
    pass


def discover_smart_configuration(iss: str) -> dict[str, Any]:
    well_known = iss.rstrip("/") + "/.well-known/smart-configuration"
    resp = httpx.get(well_known, timeout=10, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise SmartConfigurationError(
            f"SMART configuration not available for {iss}: {resp.status_code}"
        )
    return resp.json()


def is_access_token_expired(claims: dict[str, Any], *, leeway_seconds: int = 60) -> bool:
    """True if ``claims``' access_token is expired or within ``leeway_seconds`` of expiring.

    Freshness is measured from the session's own ``iat`` (issued-at) rather than
    a separately tracked timestamp, since the session cookie is always reissued
    at the same moment the access_token is obtained or refreshed - see
    ``smart_callback()`` in routes/auth.py and ``ensure_fresh_session_claims()``
    below. Sessions with no access_token (email/dev login) or missing timing
    claims are reported as not-expired: there's nothing this module can refresh
    for them, so let the actual FHIR call surface any real failure.
    """
    if not claims.get("access_token"):
        return False
    expires_in = claims.get("expires_in")
    iat = claims.get("iat")
    if expires_in is None or iat is None:
        return False
    return time.time() >= (iat + expires_in - leeway_seconds)


def refresh_access_token(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    resp = httpx.post(
        token_endpoint,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise SmartTokenRefreshError(
            f"Token refresh failed -> {resp.status_code}: {resp.text[:200]}"
        )
    return resp.json()


def ensure_fresh_session_claims(
    claims: dict[str, Any], *, settings: Any
) -> tuple[dict[str, Any], bool]:
    """Return ``(claims, refreshed)``, refreshing an expired access_token.

    Raises ``SmartTokenRefreshError`` instead of returning stale or empty
    tokens when a refresh is needed but can't be completed (revoked/expired
    refresh_token, unreachable issuer, missing client credentials, etc.) -
    callers should treat that as a hard failure, not silently proceed.
    """
    if not is_access_token_expired(claims):
        return claims, False

    refresh_token = claims.get("refresh_token")
    fhir_base_url = claims.get("fhir_base_url")
    if not refresh_token or not fhir_base_url:
        raise SmartTokenRefreshError(
            "Access token expired and no refresh_token/fhir_base_url on file to "
            "renew it; re-launch from the EHR."
        )
    if not settings.smart_client_id or not settings.smart_client_secret:
        raise SmartTokenRefreshError(
            "SMART_CLIENT_ID/SMART_CLIENT_SECRET not configured; cannot refresh access token"
        )

    try:
        smart_config = discover_smart_configuration(fhir_base_url)
    except SmartConfigurationError as exc:
        raise SmartTokenRefreshError(str(exc)) from exc

    token_endpoint = smart_config.get("token_endpoint")
    if not token_endpoint:
        raise SmartTokenRefreshError(
            f"Issuer SMART configuration for {fhir_base_url} has no token_endpoint"
        )

    tokens = refresh_access_token(
        token_endpoint=token_endpoint,
        client_id=settings.smart_client_id,
        client_secret=settings.smart_client_secret,
        refresh_token=refresh_token,
    )
    new_access_token = tokens.get("access_token")
    if not new_access_token:
        raise SmartTokenRefreshError("Token refresh response missing access_token")

    # Drop the old iat/exp/jti - the caller re-issues the session token, which
    # assigns fresh ones, and is_access_token_expired() must measure the new
    # access_token's lifetime from that fresh iat, not the original login's.
    refreshed = {k: v for k, v in claims.items() if k not in ("iat", "exp", "jti")}
    refreshed["access_token"] = new_access_token
    # Per RFC 6749 §6, a refresh response may omit refresh_token to mean "reuse
    # the one you already had" (no rotation) rather than "there is none now".
    refreshed["refresh_token"] = tokens.get("refresh_token") or refresh_token
    refreshed["expires_in"] = tokens.get("expires_in")
    return refreshed, True


__all__ = [
    "SmartConfigurationError",
    "SmartTokenRefreshError",
    "discover_smart_configuration",
    "is_access_token_expired",
    "refresh_access_token",
    "ensure_fresh_session_claims",
]
