from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, QueryRun, Study
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.studies import CriteriaSetCreate, StudyCreate, StudyResponse
from app.services.audit_service import record as record_audit

router = APIRouter()


def _ensure_study_access(db: Session, study_id: str, user) -> Study:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    if study.owner_user_id and study.owner_user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not allowed for this study")
    return study


@router.post("", response_model=StudyResponse)
def create_study(
    payload: StudyCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Study:
    study = Study(name=payload.name, description=payload.description, owner_user_id=user.id)
    db.add(study)
    db.flush()
    record_audit(
        db,
        user_id=user.id,
        action="study_create",
        object_type="study",
        object_id=str(study.id),
        request=request,
    )
    db.commit()
    db.refresh(study)
    return study


@router.get("", response_model=list[StudyResponse])
def list_studies(user: CurrentUser, db: Session = Depends(get_db)) -> list[Study]:
    query = db.query(Study)
    if user.role != "admin":
        query = query.filter(Study.owner_user_id == user.id)
    return list(query.order_by(Study.created_at.desc()).all())


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Study:
    return _ensure_study_access(db, study_id, user)


@router.post("/{study_id}/criteria-sets")
def create_criteria_set(
    study_id: str,
    payload: CriteriaSetCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _ensure_study_access(db, study_id, user)

    cs = CriteriaSet(
        study_id=study.id,
        version=payload.version,
        logic_json=payload.logic_json,
        created_by=user.id,
    )
    db.add(cs)
    db.flush()
    record_audit(
        db,
        user_id=user.id,
        action="criteria_set_create",
        object_type="criteria_set",
        object_id=str(cs.id),
        request=request,
        extra={"study_id": str(study.id), "version": payload.version},
    )
    db.commit()
    return {
        "id": str(cs.id),
        "study_id": str(study.id),
        "saved": True,
        "version": payload.version,
    }


@router.get("/{study_id}/criteria-sets")
def list_criteria_sets(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[dict]:
    study = _ensure_study_access(db, study_id, user)
    rows = (
        db.query(CriteriaSet)
        .filter(CriteriaSet.study_id == study.id)
        .order_by(CriteriaSet.version.desc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "studyId": str(r.study_id),
            "version": r.version,
            "logicJson": r.logic_json,
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/{study_id}/runs")
def list_study_runs(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    study = _ensure_study_access(db, study_id, user)
    base = db.query(QueryRun).filter(QueryRun.study_id == study.id)
    total = base.count()
    rows = (
        base.order_by(QueryRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "studyId": str(study.id),
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": str(r.id),
                "criteriaSetId": str(r.criteria_set_id),
                "status": r.status,
                "resultCount": r.result_count,
                "executionMs": r.execution_ms,
                "createdAt": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
