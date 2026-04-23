from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, Study
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.studies import CriteriaSetCreate, StudyCreate, StudyResponse
from app.services.audit_service import record as record_audit

router = APIRouter()


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


@router.post("/{study_id}/criteria-sets")
def create_criteria_set(
    study_id: str,
    payload: CriteriaSetCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    if study.owner_user_id and study.owner_user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not allowed for this study")

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
