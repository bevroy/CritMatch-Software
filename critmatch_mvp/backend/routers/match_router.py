from fastapi import APIRouter
from backend.schemas.match import MatchRequest, MatchResponse
from backend.services.matching_engine import match_patients

router = APIRouter(tags=['matching'])


@router.post('/match', response_model=MatchResponse)
def match_trial(payload: MatchRequest) -> MatchResponse:
    return match_patients(payload)


@router.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'CritMatch'}
