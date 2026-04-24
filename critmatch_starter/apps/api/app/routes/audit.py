from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.db.session import get_db
from app.deps.auth import require_roles

router = APIRouter()


@router.get("", dependencies=[Depends(require_roles("admin", "auditor"))])
def list_audit_events(
    db: Session = Depends(get_db),
    action: str | None = Query(default=None),
    object_type: str | None = Query(default=None, alias="objectType"),
    object_id: str | None = Query(default=None, alias="objectId"),
    user_id: str | None = Query(default=None, alias="userId"),
    since: str | None = Query(default=None, description="ISO-8601 lower bound on createdAt"),
    until: str | None = Query(default=None, description="ISO-8601 upper bound on createdAt"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if object_type:
        q = q.filter(AuditLog.object_type == object_type)
    if object_id:
        q = q.filter(AuditLog.object_id == object_id)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    def _parse_ts(value: str, field: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {field}: {exc}") from exc

    if since:
        q = q.filter(AuditLog.created_at >= _parse_ts(since, "since"))
    if until:
        q = q.filter(AuditLog.created_at <= _parse_ts(until, "until"))

    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "userId": str(r.user_id) if r.user_id else None,
                "action": r.action,
                "objectType": r.object_type,
                "objectId": r.object_id,
                "metadata": r.metadata_json,
                "createdAt": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
