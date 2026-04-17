from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import AuditLog, QueryRun
from app.db.session import get_db
from app.schemas.query import QueryRunRequest

router = APIRouter()


@router.post("/run")
def run_query(payload: QueryRunRequest, db: Session = Depends(get_db)) -> dict:
    qr = QueryRun(
        study_id=payload.studyId,
        criteria_set_id=payload.criteriaSetId,
        status="queued",
    )
    db.add(qr)
    db.flush()

    audit = AuditLog(
        action="query_run",
        object_type="study",
        object_id=str(payload.studyId),
    )
    db.add(audit)
    db.commit()
    db.refresh(qr)

    return {
        "runId": str(qr.id),
        "studyId": str(qr.study_id),
        "criteriaSetId": str(qr.criteria_set_id),
        "status": qr.status,
    }
