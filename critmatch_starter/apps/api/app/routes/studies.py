from uuid import uuid4

from fastapi import APIRouter

from app.schemas.studies import CriteriaSetCreate, StudyCreate, StudyResponse

router = APIRouter()

FAKE_STUDIES: list[dict] = []
FAKE_CRITERIA: dict[str, list[dict]] = {}


@router.post("", response_model=StudyResponse)
def create_study(payload: StudyCreate) -> dict:
    study = {
        "id": str(uuid4()),
        "name": payload.name,
        "description": payload.description,
        "status": "active",
    }
    FAKE_STUDIES.append(study)
    return study


@router.get("")
def list_studies() -> list[dict]:
    return FAKE_STUDIES


@router.post("/{study_id}/criteria-sets")
def create_criteria_set(study_id: str, payload: CriteriaSetCreate) -> dict:
    FAKE_CRITERIA.setdefault(study_id, []).append(payload.model_dump())
    return {"study_id": study_id, "saved": True, "version": payload.version}
