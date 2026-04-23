from fastapi import APIRouter, Depends

from app.deps.auth import CurrentUser
from app.schemas.terminology import TerminologyExpandRequest, TerminologyExpandResponse
from app.services.terminology_service import expand_term

router = APIRouter()


@router.post("/expand", response_model=TerminologyExpandResponse)
def expand(payload: TerminologyExpandRequest, _user: CurrentUser) -> TerminologyExpandResponse:
    result = expand_term(payload.text, payload.targetCodeSystems)
    return TerminologyExpandResponse(**result)
