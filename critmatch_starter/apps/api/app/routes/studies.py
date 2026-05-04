import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, QueryRun, Study, StudyCollaborator, StudyInvestigator, User
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.studies import CriteriaSetCreate, StudyCreate, StudyResponse
from app.services.access import VALID_COLLAB_ROLES, access_level, require_access
from app.services.audit_service import record as record_audit
from app.services.notifications import notify

router = APIRouter()


def _load_study(db: Session, study_id: str) -> Study | None:
    try:
        sid = uuid.UUID(study_id)
    except ValueError:
        return None
    return db.get(Study, sid)


def _study_for(db: Session, study_id: str, user, *, minimum: str = "viewer") -> Study:
    study = _load_study(db, study_id)
    require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    assert study is not None
    return study


@router.post("", response_model=StudyResponse)
def create_study(
    payload: StudyCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> StudyResponse:
    study = Study(name=payload.name, description=payload.description, owner_user_id=user.id)
    db.add(study)
    db.flush()
    record_audit(
        db,
        user_id=user.id,
        action="study_create",
        object_type="study",
        object_id=str(study.id),
        request=request,
    )
    db.commit()
    db.refresh(study)
    return StudyResponse(
        id=str(study.id),
        name=study.name,
        description=study.description,
        status=study.status,
        myAccess="owner" if user.role != "admin" else "admin",
    )


@router.get("", response_model=list[StudyResponse])
def list_studies(user: CurrentUser, db: Session = Depends(get_db)) -> list[StudyResponse]:
    query = db.query(Study)
    collab_roles: dict[uuid.UUID, str] = {}
    if user.role != "admin":
        collab_rows = db.query(StudyCollaborator).filter(StudyCollaborator.user_id == user.id).all()
        collab_roles = {row.study_id: row.role for row in collab_rows}
        query = query.filter(
            or_(Study.owner_user_id == user.id, Study.id.in_(list(collab_roles.keys())))
        )
    studies = query.order_by(Study.created_at.desc()).all()

    def _level(s: Study) -> str:
        if user.role == "admin":
            return "admin"
        if s.owner_user_id == user.id:
            return "owner"
        return collab_roles.get(s.id, "viewer")

    return [
        StudyResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            status=s.status,
            myAccess=_level(s),
        )
        for s in studies
    ]


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> StudyResponse:
    study = _study_for(db, study_id, user)
    return StudyResponse(
        id=str(study.id),
        name=study.name,
        description=study.description,
        status=study.status,
        myAccess=access_level(study, user, db),
    )


@router.post("/{study_id}/criteria-sets")
def create_criteria_set(
    study_id: str,
    payload: CriteriaSetCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user, minimum="editor")

    cs = CriteriaSet(
        study_id=study.id,
        version=payload.version,
        logic_json=payload.logic_json,
        created_by=user.id,
    )
    db.add(cs)
    db.flush()
    record_audit(
        db,
        user_id=user.id,
        action="criteria_set_create",
        object_type="criteria_set",
        object_id=str(cs.id),
        request=request,
        extra={"study_id": str(study.id), "version": payload.version},
    )
    db.commit()
    return {
        "id": str(cs.id),
        "study_id": str(study.id),
        "saved": True,
        "version": payload.version,
    }


@router.get("/{study_id}/criteria-sets")
def list_criteria_sets(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[dict]:
    study = _study_for(db, study_id, user)
    rows = (
        db.query(CriteriaSet)
        .filter(CriteriaSet.study_id == study.id)
        .order_by(CriteriaSet.version.desc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "studyId": str(r.study_id),
            "version": r.version,
            "logicJson": r.logic_json,
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/{study_id}/runs")
def list_study_runs(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    study = _study_for(db, study_id, user)
    base = db.query(QueryRun).filter(QueryRun.study_id == study.id)
    total = base.count()
    rows = (
        base.order_by(QueryRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "studyId": str(study.id),
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": str(r.id),
                "criteriaSetId": str(r.criteria_set_id),
                "status": r.status,
                "resultCount": r.result_count,
                "executionMs": r.execution_ms,
                "createdAt": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Sharing: collaborators + ownership transfer
# ---------------------------------------------------------------------------


class CollaboratorCreate(BaseModel):
    user_id: str
    role: str = "viewer"


class StudyTransferRequest(BaseModel):
    owner_user_id: str


def _resolve_user(db: Session, user_id: str) -> User:
    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user id") from exc
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{study_id}/collaborators")
def list_collaborators(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user)
    rows = (
        db.query(StudyCollaborator)
        .filter(StudyCollaborator.study_id == study.id)
        .all()
    )
    owner = db.get(User, study.owner_user_id) if study.owner_user_id else None
    my_level = access_level(study, user, db)
    return {
        "studyId": str(study.id),
        "owner": (
            {
                "userId": str(owner.id),
                "name": owner.name,
                "email": owner.email,
            }
            if owner
            else None
        ),
        "myAccess": my_level,
        "items": [
            {
                "userId": str(r.user_id),
                "role": r.role,
                "name": (r.user.name if r.user else None),
                "email": (r.user.email if r.user else None),
                "createdAt": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/{study_id}/collaborators")
def add_collaborator(
    study_id: str,
    payload: CollaboratorCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user, minimum="owner")
    if payload.role not in VALID_COLLAB_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {sorted(VALID_COLLAB_ROLES)}")
    target = _resolve_user(db, payload.user_id)
    if study.owner_user_id == target.id:
        raise HTTPException(status_code=400, detail="User is already the owner")

    existing = (
        db.query(StudyCollaborator)
        .filter(
            StudyCollaborator.study_id == study.id,
            StudyCollaborator.user_id == target.id,
        )
        .first()
    )
    if existing:
        existing.role = payload.role
        action = "study_collaborator_update"
        collab = existing
    else:
        collab = StudyCollaborator(
            study_id=study.id, user_id=target.id, role=payload.role
        )
        db.add(collab)
        db.flush()
        action = "study_collaborator_add"

    record_audit(
        db,
        user_id=user.id,
        action=action,
        object_type="study",
        object_id=str(study.id),
        request=request,
        extra={"target_user_id": str(target.id), "role": payload.role},
    )
    if target.id != user.id:
        notify(
            db,
            user_id=target.id,
            kind="study_shared" if action == "study_collaborator_add" else "study_role_changed",
            title=(
                f"You were added to “{study.name}” as {payload.role}"
                if action == "study_collaborator_add"
                else f"Your role on “{study.name}” is now {payload.role}"
            ),
            body=f"Shared by {user.name}.",
            link=f"/studies/{study.id}",
            metadata={"studyId": str(study.id), "role": payload.role, "actorUserId": str(user.id)},
        )
    db.commit()
    return {
        "studyId": str(study.id),
        "userId": str(target.id),
        "role": collab.role,
    }


@router.delete("/{study_id}/collaborators/{user_id}")
def remove_collaborator(
    study_id: str,
    user_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user, minimum="owner")
    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user id") from exc
    collab = (
        db.query(StudyCollaborator)
        .filter(
            StudyCollaborator.study_id == study.id,
            StudyCollaborator.user_id == uid,
        )
        .first()
    )
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    db.delete(collab)
    record_audit(
        db,
        user_id=user.id,
        action="study_collaborator_remove",
        object_type="study",
        object_id=str(study.id),
        request=request,
        extra={"target_user_id": str(uid)},
    )
    db.commit()
    return {"studyId": str(study.id), "userId": str(uid), "removed": True}


@router.patch("/{study_id}", response_model=StudyResponse)
def transfer_ownership(
    study_id: str,
    payload: StudyTransferRequest,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Study:
    """Reassign study ownership. Requires admin or current owner."""
    study = _study_for(db, study_id, user, minimum="owner")
    new_owner = _resolve_user(db, payload.owner_user_id)
    if study.owner_user_id == new_owner.id:
        return study

    previous = study.owner_user_id
    study.owner_user_id = new_owner.id

    # If the new owner was a collaborator, remove that row to avoid duplication.
    db.query(StudyCollaborator).filter(
        StudyCollaborator.study_id == study.id,
        StudyCollaborator.user_id == new_owner.id,
    ).delete()

    record_audit(
        db,
        user_id=user.id,
        action="study_transfer",
        object_type="study",
        object_id=str(study.id),
        request=request,
        extra={
            "from_user_id": str(previous) if previous else None,
            "to_user_id": str(new_owner.id),
        },
    )
    if new_owner.id != user.id:
        notify(
            db,
            user_id=new_owner.id,
            kind="study_ownership_transferred",
            title=f"You are now the owner of “{study.name}”",
            body=f"Transferred by {user.name}.",
            link=f"/studies/{study.id}",
            metadata={"studyId": str(study.id), "actorUserId": str(user.id)},
        )
    db.commit()
    db.refresh(study)
    return study


# ---------------------------------------------------------------------------
# User search (admin-only) – useful for the sharing UI
# ---------------------------------------------------------------------------


@router.get("/_users/search")
def search_users(
    user: CurrentUser,
    db: Session = Depends(get_db),
    q: str = Query(default="", min_length=0, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """Return users matching the given query.

    Accessible to anyone signed in so an owner can grant access. Returns the
    minimum identifying info needed to populate a picker.
    """
    base = db.query(User)
    if q:
        like = f"%{q}%"
        base = base.filter(
            or_(User.name.ilike(like), User.email.ilike(like), User.ehr_user_id.ilike(like))
        )
    rows = base.order_by(User.name.asc()).limit(limit).all()
    return [
        {
            "id": str(u.id),
            "name": u.name,
            "email": u.email,
            "role": u.role,
        }
        for u in rows
    ]

# ---------------------------------------------------------------------------
# Investigators (PI / Sub-I)
# ---------------------------------------------------------------------------


_VALID_INVESTIGATOR_ROLES = {"principal_investigator", "sub_investigator"}


class InvestigatorCreate(BaseModel):
    practitioner_id: str
    name: str | None = None
    npi: str | None = None
    role: str = "sub_investigator"


class InvestigatorUpdate(BaseModel):
    name: str | None = None
    npi: str | None = None
    role: str | None = None


@router.get("/{study_id}/investigators")
def list_investigators(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user)
    rows = (
        db.query(StudyInvestigator)
        .filter(StudyInvestigator.study_id == study.id)
        .order_by(StudyInvestigator.created_at.asc())
        .all()
    )
    return {
        "studyId": str(study.id),
        "items": [
            {
                "id": str(r.id),
                "practitionerId": r.practitioner_id,
                "name": r.name,
                "npi": r.npi,
                "role": r.role,
                "createdAt": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/{study_id}/investigators")
def add_investigator(
    study_id: str,
    payload: InvestigatorCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user, minimum="editor")
    if payload.role not in _VALID_INVESTIGATOR_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of {sorted(_VALID_INVESTIGATOR_ROLES)}",
        )
    if not payload.practitioner_id.strip():
        raise HTTPException(status_code=400, detail="practitioner_id required")

    existing = (
        db.query(StudyInvestigator)
        .filter(
            StudyInvestigator.study_id == study.id,
            StudyInvestigator.practitioner_id == payload.practitioner_id,
        )
        .first()
    )
    if existing:
        existing.role = payload.role
        if payload.name is not None:
            existing.name = payload.name
        if payload.npi is not None:
            existing.npi = payload.npi
        action = "study_investigator_update"
        inv = existing
    else:
        inv = StudyInvestigator(
            study_id=study.id,
            practitioner_id=payload.practitioner_id,
            name=payload.name,
            npi=payload.npi,
            role=payload.role,
        )
        db.add(inv)
        db.flush()
        action = "study_investigator_add"

    record_audit(
        db,
        user_id=user.id,
        action=action,
        object_type="study",
        object_id=str(study.id),
        request=request,
        extra={"practitioner_id": payload.practitioner_id, "role": payload.role},
    )
    db.commit()
    return {
        "id": str(inv.id),
        "studyId": str(study.id),
        "practitionerId": inv.practitioner_id,
        "name": inv.name,
        "npi": inv.npi,
        "role": inv.role,
    }


@router.patch("/{study_id}/investigators/{investigator_id}")
def update_investigator(
    study_id: str,
    investigator_id: str,
    payload: InvestigatorUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user, minimum="editor")
    try:
        inv_uuid = uuid.UUID(investigator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid investigator id") from exc
    inv = db.get(StudyInvestigator, inv_uuid)
    if inv is None or inv.study_id != study.id:
        raise HTTPException(status_code=404, detail="Investigator not found")

    if payload.role is not None:
        if payload.role not in _VALID_INVESTIGATOR_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Role must be one of {sorted(_VALID_INVESTIGATOR_ROLES)}",
            )
        inv.role = payload.role
    if payload.name is not None:
        inv.name = payload.name
    if payload.npi is not None:
        inv.npi = payload.npi

    record_audit(
        db,
        user_id=user.id,
        action="study_investigator_update",
        object_type="study",
        object_id=str(study.id),
        request=request,
        extra={"investigator_id": str(inv.id)},
    )
    db.commit()
    return {
        "id": str(inv.id),
        "studyId": str(study.id),
        "practitionerId": inv.practitioner_id,
        "name": inv.name,
        "npi": inv.npi,
        "role": inv.role,
    }


@router.delete("/{study_id}/investigators/{investigator_id}")
def remove_investigator(
    study_id: str,
    investigator_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    study = _study_for(db, study_id, user, minimum="editor")
    try:
        inv_uuid = uuid.UUID(investigator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid investigator id") from exc
    inv = db.get(StudyInvestigator, inv_uuid)
    if inv is None or inv.study_id != study.id:
        raise HTTPException(status_code=404, detail="Investigator not found")
    db.delete(inv)
    record_audit(
        db,
        user_id=user.id,
        action="study_investigator_remove",
        object_type="study",
        object_id=str(study.id),
        request=request,
        extra={"investigator_id": str(inv_uuid)},
    )
    db.commit()
    return {"id": str(inv_uuid), "removed": True}


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------
from datetime import datetime as _dt

from app.db.models import StudyParticipant as _SP
from app.schemas.edc import (
    ParticipantCreate as _PCreate,
    ParticipantPromote as _PPromote,
    ParticipantResponse as _PResp,
    ParticipantUpdate as _PUpdate,
)


def _serialize_p(p: _SP) -> _PResp:
    return _PResp(
        id=str(p.id),
        study_id=str(p.study_id),
        patient_id=p.patient_id,
        subject_id=p.subject_id,
        status=p.status,
        source=p.source,
        source_run_id=str(p.source_run_id) if p.source_run_id else None,
        enrolled_at=p.enrolled_at,
        notes=p.notes,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/{study_id}/participants")
def list_participants(
    study_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[_PResp]:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="viewer")
    rows = (
        db.query(_SP)
        .filter(_SP.study_id == sid)
        .order_by(_SP.subject_id.asc())
        .all()
    )
    return [_serialize_p(p) for p in rows]


@router.post("/{study_id}/participants", response_model=_PResp, status_code=201)
def create_participant(
    study_id: str,
    payload: _PCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> _PResp:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="editor")
    now = _dt.utcnow()
    p = _SP(
        id=uuid.uuid4(),
        study_id=sid,
        patient_id=payload.patient_id,
        subject_id=payload.subject_id,
        status=payload.status,
        source="manual",
        notes=payload.notes,
        enrolled_at=now if payload.status == "enrolled" else None,
        enrolled_by=user.id if payload.status == "enrolled" else None,
    )
    db.add(p)
    record_audit(
        db,
        user_id=user.id,
        action="participant_create",
        object_type="study_participant",
        object_id=str(p.id),
        request=request,
        extra={"study_id": study_id, "subject_id": payload.subject_id, "patient_id": payload.patient_id},
    )
    db.commit()
    db.refresh(p)
    return _serialize_p(p)


@router.post("/{study_id}/participants/promote", response_model=list[_PResp])
def promote_participants(
    study_id: str,
    payload: _PPromote,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[_PResp]:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="editor")

    run = db.get(QueryRun, payload.run_id)
    if run is None or run.study_id != sid:
        raise HTTPException(status_code=404, detail="Run not found")

    prefix = (payload.subject_id_prefix or "P").rstrip("-") + "-"
    # Existing subject_ids to avoid collisions / duplicates.
    existing = {
        p.patient_id: p
        for p in db.query(_SP).filter(_SP.study_id == sid).all()
    }
    next_n = 1 + len(existing)

    out: list[_SP] = []
    for pid in payload.patient_ids:
        if pid in existing:
            out.append(existing[pid])
            continue
        subject_id = f"{prefix}{next_n:03d}"
        next_n += 1
        p = _SP(
            id=uuid.uuid4(),
            study_id=sid,
            patient_id=pid,
            subject_id=subject_id,
            status="screening",
            source="cohort_promotion",
            source_run_id=payload.run_id,
        )
        db.add(p)
        out.append(p)

    record_audit(
        db,
        user_id=user.id,
        action="participant_promote",
        object_type="study_participant",
        object_id=str(payload.run_id),
        request=request,
        extra={"study_id": study_id, "count": len(out), "run_id": str(payload.run_id)},
    )
    db.commit()
    for p in out:
        db.refresh(p)
    return [_serialize_p(p) for p in out]


@router.patch("/{study_id}/participants/{participant_id}", response_model=_PResp)
def update_participant(
    study_id: str,
    participant_id: str,
    payload: _PUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> _PResp:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="editor")
    p = db.get(_SP, uuid.UUID(participant_id))
    if p is None or p.study_id != sid:
        raise HTTPException(status_code=404, detail="Participant not found")
    if payload.subject_id is not None:
        p.subject_id = payload.subject_id
    if payload.status is not None:
        if payload.status == "enrolled" and p.status != "enrolled":
            p.enrolled_at = _dt.utcnow()
            p.enrolled_by = user.id
        p.status = payload.status
    if payload.notes is not None:
        p.notes = payload.notes
    record_audit(
        db,
        user_id=user.id,
        action="participant_update",
        object_type="study_participant",
        object_id=str(p.id),
        request=request,
    )
    db.commit()
    db.refresh(p)
    return _serialize_p(p)


@router.delete("/{study_id}/participants/{participant_id}")
def delete_participant(
    study_id: str,
    participant_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    sid = uuid.UUID(study_id)
    study = db.get(Study, sid)
    require_access(study, user, db, minimum="editor")
    p = db.get(_SP, uuid.UUID(participant_id))
    if p is None or p.study_id != sid:
        raise HTTPException(status_code=404, detail="Participant not found")
    pid = str(p.id)
    db.delete(p)
    record_audit(
        db,
        user_id=user.id,
        action="participant_delete",
        object_type="study_participant",
        object_id=pid,
        request=request,
    )
    db.commit()
    return {"id": pid, "deleted": True}
