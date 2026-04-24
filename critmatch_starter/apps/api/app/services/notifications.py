"""Notification service: create, list, mark-read."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Notification


def notify(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Notification:
    """Create a notification row. Caller is responsible for committing."""
    n = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        link=link,
        metadata_json=metadata,
    )
    db.add(n)
    db.flush()
    return n


def mark_read(db: Session, *, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user_id:
        return False
    if n.read_at is None:
        n.read_at = datetime.utcnow()
    return True


def mark_all_read(db: Session, *, user_id: uuid.UUID) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .all()
    )
    now = datetime.utcnow()
    for n in rows:
        n.read_at = now
    return len(rows)
