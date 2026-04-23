from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.db.session import get_db
from app.deps.auth import require_roles

router = APIRouter()


@router.get("", dependencies=[Depends(require_roles("admin", "auditor"))])
def list_audit_events(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {
            "userId": str(r.user_id) if r.user_id else None,
            "action": r.action,
            "objectType": r.object_type,
            "objectId": r.object_id,
            "metadata": r.metadata_json,
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]
