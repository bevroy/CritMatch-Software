import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AuditLog, User
from app.db.session import get_db

router = APIRouter()

_SMART_CLIENT_ID = os.getenv("SMART_CLIENT_ID", "")
_SMART_CLIENT_SECRET = os.getenv("SMART_CLIENT_SECRET", "")
_FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "")
_ISSUER_ALLOWLIST = [
    s.strip() for s in os.getenv("SMART_ISSUER_ALLOWLIST", "").split(",") if s.strip()
]


class SmartLaunchRequest(BaseModel):
    code: str
    redirect_uri: str
    token_endpoint: str
    iss: str | None = None


@router.post("/smart/launch")
def smart_launch(payload: SmartLaunchRequest, db: Session = Depends(get_db)) -> dict:
    if not _SMART_CLIENT_ID or not _SMART_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="SMART credentials not configured")

    if _ISSUER_ALLOWLIST and payload.iss and payload.iss not in _ISSUER_ALLOWLIST:
        raise HTTPException(status_code=403, detail="Issuer not in allowlist")

    # Exchange the authorization code for an access token
    token_resp = httpx.post(
        payload.token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": payload.code,
            "redirect_uri": payload.redirect_uri,
            "client_id": _SMART_CLIENT_ID,
            "client_secret": _SMART_CLIENT_SECRET,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if token_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Token exchange failed")

    token_data = token_resp.json()
    patient_id = token_data.get("patient")
    ehr_user_id = token_data.get("id_token") or token_data.get("sub", "unknown")

    # Upsert user record
    user = db.query(User).filter(User.ehr_user_id == str(ehr_user_id)).first()
    if not user:
        user = User(ehr_user_id=str(ehr_user_id), name="EHR User")
        db.add(user)
        db.flush()

    audit = AuditLog(
        user_id=user.id,
        action="smart_launch",
        object_type="session",
        object_id=patient_id or "no-patient-context",
    )
    db.add(audit)
    db.commit()

    return {
        "sessionCreated": True,
        "user": {"id": str(user.id), "ehrUserId": user.ehr_user_id, "role": user.role},
        "patientContext": patient_id,
    }
