"""Centralised study-level access control.

Roles in scope:

- ``admin``         – application admin, full access to every study.
- ``owner``         – user listed as ``Study.owner_user_id``; full access.
- ``editor``        – ``StudyCollaborator.role == 'editor'``; can run/cancel/retry
                      and modify criteria sets.
- ``viewer``        – ``StudyCollaborator.role == 'viewer'``; read-only.
- ``research_user`` (no relation) – no access.

This module is the single source of truth so routes don't drift.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Study, StudyCollaborator, User

AccessLevel = Literal["none", "viewer", "editor", "owner", "admin"]
_LEVEL_ORDER: dict[AccessLevel, int] = {
    "none": 0,
    "viewer": 1,
    "editor": 2,
    "owner": 3,
    "admin": 4,
}

VALID_COLLAB_ROLES = {"viewer", "editor"}


def _level(study: Study, user: User, db: Session) -> AccessLevel:
    if user.role == "admin":
        return "admin"
    if study.owner_user_id and study.owner_user_id == user.id:
        return "owner"
    collab = (
        db.query(StudyCollaborator)
        .filter(
            StudyCollaborator.study_id == study.id,
            StudyCollaborator.user_id == user.id,
        )
        .first()
    )
    if collab is None:
        return "none"
    if collab.role == "editor":
        return "editor"
    return "viewer"


def access_level(study: Study, user: User, db: Session) -> AccessLevel:
    """Best-effort access level (no exception)."""
    return _level(study, user, db)


def require_access(
    study: Study | None,
    user: User,
    db: Session,
    *,
    minimum: AccessLevel = "viewer",
) -> AccessLevel:
    """Raise 404/403 unless the caller meets the required level."""
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    level = _level(study, user, db)
    if _LEVEL_ORDER[level] < _LEVEL_ORDER[minimum]:
        # Hide existence from non-viewers to avoid enumeration
        if level == "none" and minimum != "viewer":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
        if level == "none":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient access")
    return level


__all__ = [
    "AccessLevel",
    "VALID_COLLAB_ROLES",
    "access_level",
    "require_access",
]
