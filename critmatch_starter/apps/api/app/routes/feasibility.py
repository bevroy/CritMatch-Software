"""Feasibility module HTTP routes.

Exposes CRUD for feasibility questionnaires and synchronous run execution.
Runs are executed in-line (not via the worker queue) because feasibility is
typically an interactive workflow with a small number of questions; if a
questionnaire grows large enough to need async execution, the existing
worker pattern in :mod:`app.services.query_runner` can be mirrored.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import (
    FeasibilityQuestion,
    FeasibilityQuestionnaire,
    FeasibilityResult,
    FeasibilityRun,
    Study,
)
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.fhir.client import FHIRClient
from app.schemas.feasibility import (
    FeasibilityQuestionInput,
    FeasibilityQuestionResponse,
    FeasibilityQuestionnaireCreate,
    FeasibilityQuestionnaireResponse,
    FeasibilityQuestionnaireSummary,
    FeasibilityQuestionnaireUpdate,
    FeasibilityResultItem,
    FeasibilityRunResponse,
)
from app.services.access import require_access
from app.services.audit_service import record as record_audit
from app.services.feasibility_engine import (
    FeasibilityExecutionError,
    run_feasibility,
)

router = APIRouter()


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}") from exc


def _study_or_403(db: Session, study_id: Optional[str], user, *, minimum: str) -> Optional[Study]:
    if not study_id:
        return None
    sid = _parse_uuid(study_id, "studyId")
    study = db.get(Study, sid)
    require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    return study


def _load_questionnaire(
    db: Session, questionnaire_id: str, user, *, minimum: str = "viewer"
) -> FeasibilityQuestionnaire:
    qid = _parse_uuid(questionnaire_id, "questionnaireId")
    fq = db.get(FeasibilityQuestionnaire, qid)
    if fq is None:
        raise HTTPException(status_code=404, detail="Questionnaire not found")

    # If a study is attached, gate access through study collaborators; otherwise
    # only the creator (or admin) may touch a personal questionnaire.
    if fq.study_id:
        study = db.get(Study, fq.study_id)
        require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    else:
        is_admin = getattr(user, "role", None) == "admin"
        is_owner = fq.created_by == user.id
        if not (is_admin or is_owner):
            raise HTTPException(status_code=404, detail="Questionnaire not found")
    return fq


def _serialize_question(q: FeasibilityQuestion) -> FeasibilityQuestionResponse:
    return FeasibilityQuestionResponse(
        id=str(q.id),
        position=q.position,
        text=q.text,
        logicJson=q.logic_json,
    )


def _serialize_questionnaire(fq: FeasibilityQuestionnaire) -> FeasibilityQuestionnaireResponse:
    return FeasibilityQuestionnaireResponse(
        id=str(fq.id),
        name=fq.name,
        description=fq.description,
        studyId=str(fq.study_id) if fq.study_id else None,
        createdBy=str(fq.created_by) if fq.created_by else None,
        createdAt=fq.created_at.isoformat(),
        updatedAt=fq.updated_at.isoformat(),
        questions=[_serialize_question(q) for q in sorted(fq.questions, key=lambda x: x.position)],
    )


def _replace_questions(
    db: Session,
    questionnaire: FeasibilityQuestionnaire,
    inputs: list[FeasibilityQuestionInput],
) -> None:
    db.query(FeasibilityQuestion).filter(
        FeasibilityQuestion.questionnaire_id == questionnaire.id
    ).delete()
    db.flush()
    for index, item in enumerate(inputs):
        db.add(
            FeasibilityQuestion(
                questionnaire_id=questionnaire.id,
                position=item.position if item.position is not None else index,
                text=item.text,
                logic_json=item.logic_json or {},
            )
        )


# ---------------------------------------------------------------------------
# Questionnaires
# ---------------------------------------------------------------------------


@router.get("/questionnaires", response_model=list[FeasibilityQuestionnaireSummary])
def list_questionnaires(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = None,  # noqa: N803 - camelCase query
) -> list[FeasibilityQuestionnaireSummary]:
    q = db.query(FeasibilityQuestionnaire)
    if studyId:
        sid = _parse_uuid(studyId, "studyId")
        # Ensure caller has at least viewer access to that study before listing.
        study = db.get(Study, sid)
        require_access(study, user, db, minimum="viewer")  # type: ignore[arg-type]
        q = q.filter(FeasibilityQuestionnaire.study_id == sid)
    elif user.role != "admin":
        # Without a study filter, only show questionnaires the user created.
        q = q.filter(FeasibilityQuestionnaire.created_by == user.id)

    rows = q.order_by(FeasibilityQuestionnaire.updated_at.desc()).all()
    return [
        FeasibilityQuestionnaireSummary(
            id=str(fq.id),
            name=fq.name,
            description=fq.description,
            studyId=str(fq.study_id) if fq.study_id else None,
            questionCount=len(fq.questions),
            updatedAt=fq.updated_at.isoformat(),
        )
        for fq in rows
    ]


@router.post("/questionnaires", response_model=FeasibilityQuestionnaireResponse)
def create_questionnaire(
    payload: FeasibilityQuestionnaireCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FeasibilityQuestionnaireResponse:
    study = _study_or_403(db, payload.studyId, user, minimum="editor")

    fq = FeasibilityQuestionnaire(
        study_id=study.id if study else None,
        name=payload.name,
        description=payload.description,
        created_by=user.id,
    )
    db.add(fq)
    db.flush()
    if payload.questions:
        _replace_questions(db, fq, payload.questions)

    record_audit(
        db,
        user_id=user.id,
        action="feasibility_questionnaire_create",
        object_type="feasibility_questionnaire",
        object_id=str(fq.id),
        request=request,
        extra={"study_id": str(fq.study_id) if fq.study_id else None},
    )
    db.commit()
    db.refresh(fq)
    return _serialize_questionnaire(fq)


@router.get(
    "/questionnaires/{questionnaire_id}",
    response_model=FeasibilityQuestionnaireResponse,
)
def get_questionnaire(
    questionnaire_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FeasibilityQuestionnaireResponse:
    fq = _load_questionnaire(db, questionnaire_id, user)
    return _serialize_questionnaire(fq)


@router.patch(
    "/questionnaires/{questionnaire_id}",
    response_model=FeasibilityQuestionnaireResponse,
)
def update_questionnaire(
    questionnaire_id: str,
    payload: FeasibilityQuestionnaireUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FeasibilityQuestionnaireResponse:
    fq = _load_questionnaire(db, questionnaire_id, user, minimum="editor")

    if payload.studyId is not None:
        study = _study_or_403(db, payload.studyId or None, user, minimum="editor")
        fq.study_id = study.id if study else None
    if payload.name is not None:
        fq.name = payload.name
    if payload.description is not None:
        fq.description = payload.description
    if payload.questions is not None:
        _replace_questions(db, fq, payload.questions)

    record_audit(
        db,
        user_id=user.id,
        action="feasibility_questionnaire_update",
        object_type="feasibility_questionnaire",
        object_id=str(fq.id),
        request=request,
    )
    db.commit()
    db.refresh(fq)
    return _serialize_questionnaire(fq)


@router.delete("/questionnaires/{questionnaire_id}")
def delete_questionnaire(
    questionnaire_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    fq = _load_questionnaire(db, questionnaire_id, user, minimum="editor")
    fq_id = fq.id
    db.delete(fq)
    record_audit(
        db,
        user_id=user.id,
        action="feasibility_questionnaire_delete",
        object_type="feasibility_questionnaire",
        object_id=str(fq_id),
        request=request,
    )
    db.commit()
    return {"id": str(fq_id), "deleted": True}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def _serialize_run(
    fr: FeasibilityRun,
    results: list[FeasibilityResult],
    questions_by_id: dict[uuid.UUID, FeasibilityQuestion],
) -> FeasibilityRunResponse:
    items: list[FeasibilityResultItem] = []
    for r in results:
        question = questions_by_id.get(r.question_id)
        items.append(
            FeasibilityResultItem(
                questionId=str(r.question_id),
                questionText=question.text if question else "",
                count=r.count,
                detail=r.detail_json,
            )
        )
    return FeasibilityRunResponse(
        id=str(fr.id),
        questionnaireId=str(fr.questionnaire_id),
        status=fr.status,
        totalPatients=fr.total_patients,
        executionMs=fr.execution_ms,
        errorMessage=fr.error_message,
        createdAt=fr.created_at.isoformat(),
        results=items,
    )


@router.post(
    "/questionnaires/{questionnaire_id}/run",
    response_model=FeasibilityRunResponse,
)
def run_questionnaire(
    questionnaire_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FeasibilityRunResponse:
    fq = _load_questionnaire(db, questionnaire_id, user, minimum="editor")

    fr = FeasibilityRun(
        questionnaire_id=fq.id,
        run_by=user.id,
        status="queued",
    )
    db.add(fr)
    db.flush()

    record_audit(
        db,
        user_id=user.id,
        action="feasibility_run",
        object_type="feasibility_run",
        object_id=str(fr.id),
        request=request,
        extra={"questionnaire_id": str(fq.id)},
    )
    db.commit()

    # Execute synchronously. ``run_feasibility`` builds its own FHIRClient from
    # env vars; tests inject a fake via dependency override on this route.
    try:
        run_feasibility(db, str(fr.id), fhir_client=_get_fhir_client_override(request))
    except FeasibilityExecutionError:
        # Status + error_message already persisted by the engine.
        db.refresh(fr)

    db.refresh(fr)
    results = (
        db.query(FeasibilityResult)
        .filter(FeasibilityResult.run_id == fr.id)
        .all()
    )
    questions_by_id = {q.id: q for q in fq.questions}
    return _serialize_run(fr, results, questions_by_id)


@router.get("/runs/{run_id}", response_model=FeasibilityRunResponse)
def get_run(
    run_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FeasibilityRunResponse:
    rid = _parse_uuid(run_id, "runId")
    fr = db.get(FeasibilityRun, rid)
    if fr is None:
        raise HTTPException(status_code=404, detail="Run not found")
    fq = _load_questionnaire(db, str(fr.questionnaire_id), user)
    results = (
        db.query(FeasibilityResult)
        .filter(FeasibilityResult.run_id == fr.id)
        .all()
    )
    questions_by_id = {q.id: q for q in fq.questions}
    return _serialize_run(fr, results, questions_by_id)


@router.get(
    "/questionnaires/{questionnaire_id}/runs",
    response_model=list[FeasibilityRunResponse],
)
def list_runs(
    questionnaire_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = 25,
) -> list[FeasibilityRunResponse]:
    fq = _load_questionnaire(db, questionnaire_id, user)
    rows = (
        db.query(FeasibilityRun)
        .filter(FeasibilityRun.questionnaire_id == fq.id)
        .order_by(FeasibilityRun.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    questions_by_id = {q.id: q for q in fq.questions}
    out: list[FeasibilityRunResponse] = []
    for fr in rows:
        results = (
            db.query(FeasibilityResult)
            .filter(FeasibilityResult.run_id == fr.id)
            .all()
        )
        out.append(_serialize_run(fr, results, questions_by_id))
    return out


# ---------------------------------------------------------------------------
# Test seam: routes can override the FHIR client by setting
# ``request.app.state.feasibility_fhir_client``.
# ---------------------------------------------------------------------------


def _get_fhir_client_override(request: Request) -> FHIRClient | None:
    return getattr(request.app.state, "feasibility_fhir_client", None)
