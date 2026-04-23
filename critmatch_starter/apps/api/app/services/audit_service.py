"""Audit log helper used by mutation routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record(
    db: Session,
    *,
    user_id: UUID | None,
    action: str,
    object_type: str,
    object_id: str | None = None,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
) -> AuditLog:
    metadata: dict[str, Any] = dict(extra or {})
    if request is not None:
        client = request.client.host if request.client else None
        metadata.setdefault("ip", client)
        metadata.setdefault("user_agent", request.headers.get("user-agent"))
        metadata.setdefault("request_id", request.headers.get("x-request-id"))
    log = AuditLog(
        user_id=user_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        metadata_json=metadata or None,
    )
    db.add(log)
    return log
