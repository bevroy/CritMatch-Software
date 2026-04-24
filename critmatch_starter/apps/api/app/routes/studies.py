import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import CriteriaSet, QueryRun, Study, StudyCollaborator, User
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.studies import CriteriaSetCreate, StudyCreate, StudyResponse
from app.services.access import VALID_COLLAB_ROLES, access_level, require_access
from app.services.audit_service import record as record_audit

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