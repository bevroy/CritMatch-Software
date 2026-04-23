"""Sentry initialisation with PHI scrubbing.

We aggressively scrub request bodies, headers and cookies because this
service handles PHI. Anything tagged as sensitive is removed before the
event leaves the process.
"""

from __future__ import annotations

import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.utils import BadDsn


_SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-smart-launch",
}

_SENSITIVE_KEY_HINTS = (
    "patient",
    "mrn",
    "ssn",
    "dob",
    "birth",
    "name",
    "email",
    "phone",
    "address",
    "token",
    "secret",
    "id_token",
    "access_token",
    "refresh_token",
)


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            key_l = str(k).lower()
            if any(hint in key_l for hint in _SENSITIVE_KEY_HINTS):
                cleaned[k] = "[scrubbed]"
            else:
                cleaned[k] = _scrub(v)
        return cleaned
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        request["headers"] = {
            k: ("[scrubbed]" if k.lower() in _SENSITIVE_HEADER_NAMES else v)
            for k, v in headers.items()
        }
    if "cookies" in request:
        request["cookies"] = "[scrubbed]"
    if "data" in request:
        request["data"] = _scrub(request["data"])
    if "query_string" in request:
        # Query strings may carry codes/tokens
        request["query_string"] = "[scrubbed]"
    event["request"] = request

    extra = event.get("extra")
    if isinstance(extra, dict):
        event["extra"] = _scrub(extra)
    return event


def init_sentry() -> None:
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.getenv("APP_ENV", "development"),
            release=os.getenv("GIT_SHA") or os.getenv("RENDER_GIT_COMMIT"),
            send_default_pii=False,
            before_send=_before_send,
            integrations=[FastApiIntegration()],
        )
    except BadDsn:
        return
