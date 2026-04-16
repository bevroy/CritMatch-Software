from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_audit_events() -> list[dict]:
    return [
        {
            "action": "query_run",
            "objectType": "study",
            "objectId": "demo-study",
            "createdAt": "2026-04-16T10:00:00",
        }
    ]
