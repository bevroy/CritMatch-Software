from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, QueryRun, Study
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.query import QueryRunRequest
from app.services.access import require_access
from app.services.audit_service import record as record_audit

router = APIRouter()


@router.post("/run")
def run_query(
    payload: QueryRunRequest,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = db.get(Study, payload.studyId)
    require_access(study, user, db, minimum="editor")
    assert study is not None

    cs = db.get(CriteriaSet, payload.criteriaSetId)
    if cs is None or cs.study_id != study.id:
        raise HTTPException(status_code=404, detail="Criteria set not found for study")

    qr = QueryRun(
        study_id=study.id,
        criteria_set_id=cs.id,
        run_by=user.id,
        status="queued",
    )
    db.add(qr)
    db.flush()

    record_audit(
        db,
        user_id=user.id,
        action="query_run",
        object_type="query_run",
        object_id=str(qr.id),
        request=request,
        extra={"study_id": str(study.id), "criteria_set_id": str(cs.id)},
    )
    db.commit()
    db.refresh(qr)

    return {
        "runId": str(qr.id),
        "studyId": str(qr.study_id),
        "criteriaSetId": str(qr.criteria_set_id),
        "status": qr.status,
    }
