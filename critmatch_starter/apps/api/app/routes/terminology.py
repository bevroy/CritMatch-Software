from fastapi import APIRouter

from app.schemas.terminology import TerminologyExpandRequest, TerminologyExpandResponse
from app.services.terminology_service import expand_term

router = APIRouter()


@router.post("/expand", response_model=TerminologyExpandResponse)
def expand(payload: TerminologyExpandRequest) -> TerminologyExpandResponse:
    result = expand_term(payload.text, payload.targetCodeSystems)
    return TerminologyExpandResponse(**result)
