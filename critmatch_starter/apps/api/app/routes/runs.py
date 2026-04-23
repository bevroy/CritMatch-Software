"""Query run + results endpoints, including signed CSV export."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import QueryResult, QueryRun, Study
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.services.audit_service import record as record_audit

router = APIRouter()


def _ensure_owner(qr: QueryRun, db: Session, user) -> None:
    study = db.get(Study, qr.study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    if study.owner_user_id and study.owner_user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")


@router.get("/{run_id}")
def get_run(run_id: str, user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    qr = db.get(QueryRun, run_id)
    if qr is None:
        raise HTTPException(status_code=404, detail="Run not found")
    _ensure_owner(qr, db, user)
    return {
        "id": str(qr.id),
        "studyId": str(qr.study_id),
        "criteriaSetId": str(qr.criteria_set_id),
        "status": qr.status,
        "resultCount": qr.result_count,
        "executionMs": qr.execution_ms,
        "createdAt": qr.created_at.isoformat(),
    }


@router.get("/{run_id}/results")
def list_results(
    run_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    qr = db.get(QueryRun, run_id)
    if qr is None:
        raise HTTPException(status_code=404, detail="Run not found")
    _ensure_owner(qr, db, user)

    rows = (
        db.query(QueryResult)
        .filter(QueryResult.query_run_id == qr.id)
        .order_by(QueryResult.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "runId": str(qr.id),
        "total": qr.result_count or 0,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "patientId": r.patient_id,
                "mrnHash": r.mrn_hash,
                "matchedRules": (r.matched_rules_json or {}).get("rules", []),
                "primaryMatchReason": r.primary_match_reason,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Signed CSV export
# ---------------------------------------------------------------------------


def _sign(run_id: str, user_id: str, expires: int) -> str:
    settings = get_settings()
    if not settings.export_signing_key:
        raise HTTPException(status_code=503, detail="EXPORT_SIGNING_KEY not configured")
    msg = f"{run_id}|{user_id}|{expires}".encode()
    return hmac.new(settings.export_signing_key.encode(), msg, hashlib.sha256).hexdigest()


@router.post("/{run_id}/export")
def create_export_link(
    run_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    ttl_seconds: int = Query(default=300, ge=30, le=3600),
) -> dict:
    qr = db.get(QueryRun, run_id)
    if qr is None:
        raise HTTPException(status_code=404, detail="Run not found")
    _ensure_owner(qr, db, user)
    if qr.status != "completed":
        raise HTTPException(status_code=409, detail="Run not completed")

    expires = int(time.time()) + ttl_seconds
    sig = _sign(str(qr.id), str(user.id), expires)
    qs = urlencode({"u": str(user.id), "exp": expires, "sig": sig})
    record_audit(
        db,
        user_id=user.id,
        action="export_link_create",
        object_type="query_run",
        object_id=str(qr.id),
        request=request,
        extra={"ttl_seconds": ttl_seconds},
    )
    db.commit()
    return {
        "downloadPath": f"/api/runs/{qr.id}/export.csv?{qs}",
        "expiresAt": expires,
    }


@router.get("/{run_id}/export.csv")
def download_export(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    u: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
) -> StreamingResponse:
    if exp < int(time.time()):
        raise HTTPException(status_code=410, detail="Link expired")
    expected = _sign(run_id, u, exp)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    qr = db.get(QueryRun, run_id)
    if qr is None:
        raise HTTPException(status_code=404, detail="Run not found")

    rows = (
        db.query(QueryResult)
        .filter(QueryResult.query_run_id == qr.id)
        .order_by(QueryResult.created_at.asc())
        .all()
    )
    materialised = [
        (
            r.patient_id,
            r.mrn_hash or "",
            r.primary_match_reason or "",
            "|".join((r.matched_rules_json or {}).get("rules", [])),
        )
        for r in rows
    ]

    def _stream():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["patient_id", "mrn_hash", "primary_match_reason", "matched_rules"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in materialised:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    record_audit(
        db,
        user_id=None,
        action="export_download",
        object_type="query_run",
        object_id=str(qr.id),
        request=request,
        extra={"signed_user": u},
    )
    db.commit()

    return StreamingResponse(
        _stream(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="run-{qr.id}.csv"'},
    )
