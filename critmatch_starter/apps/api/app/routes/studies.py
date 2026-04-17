from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, Study
from app.db.session import get_db
from app.schemas.studies import CriteriaSetCreate, StudyCreate, StudyResponse

router = APIRouter()


@router.post("", response_model=StudyResponse)
def create_study(payload: StudyCreate, db: Session = Depends(get_db)) -> Study:
    study = Study(name=payload.name, description=payload.description)
    db.add(study)
    db.commit()
    db.refresh(study)
    return study


@router.get("", response_model=list[StudyResponse])
def list_studies(db: Session = Depends(get_db)) -> list[Study]:
    return list(db.query(Study).order_by(Study.created_at.desc()).all())


@router.post("/{study_id}/criteria-sets")
def create_criteria_set(study_id: str, payload: CriteriaSetCreate, db: Session = Depends(get_db)) -> dict:
    cs = CriteriaSet(
        study_id=study_id,
        version=payload.version,
        logic_json=payload.logic_json,
        created_by=payload.created_by,
    )
    db.add(cs)
    db.commit()
    return {"study_id": study_id, "saved": True, "version": payload.version}
