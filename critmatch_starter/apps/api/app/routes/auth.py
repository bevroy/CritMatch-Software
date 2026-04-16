from fastapi import APIRouter

router = APIRouter()


@router.post("/smart/launch")
def smart_launch() -> dict:
    return {
        "sessionCreated": True,
        "message": "SMART launch placeholder",
        "user": {"ehrUserId": "demo-user", "role": "research_user"},
    }
