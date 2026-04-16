from uuid import uuid4

from fastapi import APIRouter

from app.schemas.query import QueryRunRequest

router = APIRouter()


@router.post("/run")
def run_query(payload: QueryRunRequest) -> dict:
    return {
        "runId": str(uuid4()),
        "studyId": payload.studyId,
        "criteriaSetId": payload.criteriaSetId,
        "status": "completed",
        "resultCount": 2,
        "results": [
            {
                "patientId": "patient-001",
                "matchReason": "Matched diagnosis: myocardial infarction",
                "age": 67,
                "sex": "female",
                "site": "Cardiology Clinic",
            },
            {
                "patientId": "patient-002",
                "matchReason": "Matched diagnosis: myocardial infarction",
                "age": 58,
                "sex": "male",
                "site": "General Medicine",
            },
        ],
    }
