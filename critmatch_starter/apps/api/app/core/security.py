"""Session token signing/verification and SMART id_token validation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings


class SessionError(Exception):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def issue_session_token(payload: dict[str, Any]) -> str:
    """Issue a compact, signed (HS256) session token.

    We deliberately implement a small JWS-style structure rather than pulling
    in another dependency for sessions; the SMART id_token verification
    already requires PyJWT.
    """

    settings = get_settings()
    if not settings.session_secret:
        raise SessionError("SESSION_SECRET not configured")

    now = int(time.time())
    body = {
        "iat": now,
        "exp": now + settings.session_ttl_seconds,
        "jti": secrets.token_urlsafe(16),
        **payload,
    }
    header = {"alg": "HS256", "typ": "CMS"}
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(body, separators=(",", ":")).encode())
    )
    signature = hmac.new(
        settings.session_secret.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    return signing_input + "." + _b64url(signature)


def verify_session_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.session_secret:
        raise SessionError("SESSION_SECRET not configured")

    try:
        signing_input, signature_b64 = token.rsplit(".", 1)
    except ValueError as exc:
        raise SessionError("Malformed session token") from exc

    expected = hmac.new(
        settings.session_secret.encode(),
        signing_input.encode(),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
        raise SessionError("Bad signature")

    try:
        _, body_b64 = signing_input.split(".", 1)
        body = json.loads(_b64url_decode(body_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise SessionError("Malformed session token") from exc

    if int(body.get("exp", 0)) < int(time.time()):
        raise SessionError("Session expired")
    return body


# ---------------------------------------------------------------------------
# SMART id_token verification
# ---------------------------------------------------------------------------


_jwks_cache: dict[str, PyJWKClient] = {}


def _jwks_client(jwks_uri: str) -> PyJWKClient:
    client = _jwks_cache.get(jwks_uri)
    if client is None:
        client = PyJWKClient(jwks_uri, cache_keys=True)
        _jwks_cache[jwks_uri] = client
    return client


def verify_smart_id_token(
    id_token: str,
    *,
    audience: str,
    issuer: str | None,
    jwks_uri: str | None,
) -> dict[str, Any]:
    """Verify a SMART/OIDC id_token.

    If a ``jwks_uri`` is supplied we perform full signature verification.
    When the issuer's JWKS endpoint isn't available we still verify the
    structural claims but mark the result as unverified (callers may refuse
    to honour it in production).
    """

    if jwks_uri:
        signing_key = _jwks_client(jwks_uri).get_signing_key_from_jwt(id_token).key
        decoded = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "aud"]},
        )
        decoded["_signature_verified"] = True
        return decoded

    # Best-effort structural validation when JWKS is unknown. Production
    # deployments MUST configure jwks_uri.
    decoded = jwt.decode(
        id_token,
        options={"verify_signature": False, "require": ["exp", "iat", "aud"]},
        audience=audience,
    )
    if issuer and decoded.get("iss") != issuer:
        raise jwt.InvalidIssuerError("Issuer mismatch")
    decoded["_signature_verified"] = False
    return decoded


# ---------------------------------------------------------------------------
# OAuth state / PKCE helpers
# ---------------------------------------------------------------------------


def generate_state() -> str:
    return secrets.token_urlsafe(24)


def generate_pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for PKCE S256."""

    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = _b64url(digest)
    return verifier, challenge
