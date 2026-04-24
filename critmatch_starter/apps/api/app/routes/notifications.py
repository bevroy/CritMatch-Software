import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import Notification
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.services import notifications as notif_service

router = APIRouter()


def _serialize(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "readAt": n.read_at.isoformat() + "Z" if n.read_at else None,
        "createdAt": n.created_at.isoformat() + "Z",
        "metadata": n.metadata_json,
    }


@router.get("")
def list_notifications(
    user: CurrentUser,
    db: Session = Depends(get_db),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    total = q.count()
    rows = q.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )
    return {
        "items": [_serialize(n) for n in rows],
        "total": total,
        "unread": unread,
        "limit": limit,
        "offset": offset,
    }


@router.get("/unread-count")
def unread_count(user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    n = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )
    return {"unread": n}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    try:
        nid = uuid.UUID(notification_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Notification not found") from e
    if not notif_service.mark_read(db, user_id=user.id, notification_id=nid):
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    n = notif_service.mark_all_read(db, user_id=user.id)
    db.commit()
    return {"ok": True, "marked": n}
