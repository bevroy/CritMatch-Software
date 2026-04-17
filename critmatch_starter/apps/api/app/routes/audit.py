from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.db.session import get_db

router = APIRouter()


@router.get("")
def list_audit_events(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {
            "action": r.action,
            "objectType": r.object_type,
            "objectId": r.object_id,
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]
