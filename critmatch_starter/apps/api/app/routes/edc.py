"""EDC module HTTP routes.

Endpoints
---------

Forms
- GET    /api/edc/forms?studyId=...
- POST   /api/edc/forms
- GET    /api/edc/forms/{form_id}
- PATCH  /api/edc/forms/{form_id}
- DELETE /api/edc/forms/{form_id}

Participants (mounted under /api/studies/{study_id}/participants)
- GET    /api/studies/{study_id}/participants
- POST   /api/studies/{study_id}/participants
- POST   /api/studies/{study_id}/participants/promote
- PATCH  /api/studies/{study_id}/participants/{participant_id}
- DELETE /api/studies/{study_id}/participants/{participant_id}

Entries
- GET    /api/edc/forms/{form_id}/entries
- POST   /api/edc/forms/{form_id}/entries  {participant_id}
- GET    /api/edc/entries/{entry_id}
- PATCH  /api/edc/entries/{entry_id}
- POST   /api/edc/entries/{entry_id}/pull
- POST   /api/edc/entries/{entry_id}/sign
- GET    /api/edc/entries/{entry_id}/history
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    EdcEntry,
    EdcEntryField,
    EdcEntryFieldHistory,
    EdcField,
    EdcForm,
    EdcSignature,
    QueryRun,
    Study,
    StudyParticipant,
    User,
)
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.fhir.client import FHIRClient
from app.schemas.edc import (
    EdcFieldInput,
    EdcFieldResponse,
    EdcFormCreate,
    EdcFormResponse,
    EdcFormSummary,
    EdcFormUpdate,
    EntryFieldResponse,
    EntryHistoryItem,
    EntryResponse,
    EntryUpdate,
    FhirPullResult,
    ParticipantCreate,
    ParticipantPromote,
    ParticipantResponse,
    ParticipantUpdate,
    SignatureCreate,
    SignatureResponse,
)
from app.services.access import require_access
from app.services.audit_service import record as record_audit
from app.services.edc_fhir import pull_all_for_entry, pull_field_value

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}") from exc


def _study_or_404(db: Session, study_id: str, user: User, *, minimum: str = "viewer") -> Study:
    sid = _parse_uuid(study_id, "studyId")
    study = db.get(Study, sid)
    require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    assert study is not None
    return study


def _load_form(db: Session, form_id: str, user: User, *, minimum: str = "viewer") -> EdcForm:
    fid = _parse_uuid(form_id, "formId")
    form = db.get(EdcForm, fid)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    study = db.get(Study, form.study_id)
    require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    return form


def _load_participant(
    db: Session, participant_id: str, user: User, *, minimum: str = "viewer"
) -> StudyParticipant:
    pid = _parse_uuid(participant_id, "participantId")
    p = db.get(StudyParticipant, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    study = db.get(Study, p.study_id)
    require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    return p


def _load_entry(db: Session, entry_id: str, user: User, *, minimum: str = "viewer") -> EdcEntry:
    eid = _parse_uuid(entry_id, "entryId")
    entry = db.get(EdcEntry, eid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    form = db.get(EdcForm, entry.form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    study = db.get(Study, form.study_id)
    require_access(study, user, db, minimum=minimum)  # type: ignore[arg-type]
    return entry


def _serialize_field(f: EdcField) -> EdcFieldResponse:
    return EdcFieldResponse.model_validate(f, from_attributes=True)


def _serialize_form(form: EdcForm) -> EdcFormResponse:
    return EdcFormResponse(
        id=str(form.id),
        study_id=str(form.study_id),
        name=form.name,
        description=form.description,
        version=form.version,
        status=form.status,
        created_by=str(form.created_by) if form.created_by else None,
        created_at=form.created_at,
        updated_at=form.updated_at,
        fields=[_serialize_field(f) for f in form.fields],
    )


def _serialize_participant(p: StudyParticipant) -> ParticipantResponse:
    return ParticipantResponse(
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


def _serialize_signature(s: EdcSignature) -> SignatureResponse:
    return SignatureResponse(
        id=str(s.id),
        user_id=str(s.user_id),
        meaning=s.meaning,
        signature_hash=s.signature_hash,
        signed_at=s.signed_at,
    )


def _serialize_entry(entry: EdcEntry) -> EntryResponse:
    return EntryResponse(
        id=str(entry.id),
        form_id=str(entry.form_id),
        participant_id=str(entry.participant_id),
        status=entry.status,
        completed_at=entry.completed_at,
        locked_at=entry.locked_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        values=[
            EntryFieldResponse(
                field_id=str(v.field_id),
                value=(v.value_json or {}).get("value"),
                source=v.source,
                fhir_source_ref=v.fhir_source_ref,
                updated_at=v.updated_at,
            )
            for v in entry.field_values
        ],
        signatures=[_serialize_signature(s) for s in entry.signatures],
    )


def _get_fhir_client_override(request: Request) -> FHIRClient | None:
    """Test seam - tests can stash a fake on ``app.state.edc_fhir_client``."""
    return getattr(request.app.state, "edc_fhir_client", None)


def _build_fhir_client(request: Request) -> FHIRClient:
    override = _get_fhir_client_override(request)
    if override is not None:
        return override  # type: ignore[return-value]
    settings = get_settings()
    if not settings.fhir_base_url:
        raise HTTPException(status_code=503, detail="FHIR_BASE_URL not configured")
    return FHIRClient(settings.fhir_base_url)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


@router.get("/forms")
def list_forms(
    user: CurrentUser,
    db: Session = Depends(get_db),
    studyId: Optional[str] = Query(None),
) -> list[EdcFormSummary]:
    q = db.query(EdcForm)
    if studyId:
        sid = _parse_uuid(studyId, "studyId")
        # Verify access; lists from inaccessible studies look empty.
        study = db.get(Study, sid)
        require_access(study, user, db, minimum="viewer")  # type: ignore[arg-type]
        q = q.filter(EdcForm.study_id == sid)
    forms = q.order_by(EdcForm.updated_at.desc()).all()
    out: list[EdcFormSummary] = []
    for f in forms:
        # Skip forms the user can't see.
        try:
            study = db.get(Study, f.study_id)
            require_access(study, user, db, minimum="viewer")  # type: ignore[arg-type]
        except HTTPException:
            continue
        out.append(
            EdcFormSummary(
                id=str(f.id),
                study_id=str(f.study_id),
                name=f.name,
                description=f.description,
                version=f.version,
                status=f.status,
                fieldCount=len(f.fields),
                updated_at=f.updated_at,
            )
        )
    return out


@router.post("/forms", response_model=EdcFormResponse, status_code=201)
def create_form(
    payload: EdcFormCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> EdcFormResponse:
    study = _study_or_404(db, str(payload.study_id), user, minimum="editor")
    form = EdcForm(
        id=uuid.uuid4(),
        study_id=study.id,
        name=payload.name,
        description=payload.description,
        version=1,
        status="draft",
        created_by=user.id,
    )
    db.add(form)
    db.flush()
    for i, f in enumerate(payload.fields):
        db.add(_make_field(form.id, f, i))
    record_audit(
        db,
        user_id=user.id,
        action="edc_form_create",
        object_type="edc_form",
        object_id=str(form.id),
        request=request,
        extra={"name": form.name, "study_id": str(study.id)},
    )
    db.commit()
    db.refresh(form)
    return _serialize_form(form)


@router.get("/forms/{form_id}", response_model=EdcFormResponse)
def get_form(
    form_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> EdcFormResponse:
    return _serialize_form(_load_form(db, form_id, user))


@router.patch("/forms/{form_id}", response_model=EdcFormResponse)
def update_form(
    form_id: str,
    payload: EdcFormUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> EdcFormResponse:
    form = _load_form(db, form_id, user, minimum="editor")
    if form.status == "locked":
        raise HTTPException(status_code=409, detail="Form is locked")
    if payload.name is not None:
        form.name = payload.name
    if payload.description is not None:
        form.description = payload.description
    if payload.status is not None:
        form.status = payload.status
    if payload.fields is not None:
        # Replace field list. Existing entries keep their values via field_id;
        # if a field is removed, EdcEntryField rows cascade-delete.
        for existing in list(form.fields):
            db.delete(existing)
        db.flush()
        for i, f in enumerate(payload.fields):
            db.add(_make_field(form.id, f, i))
        form.version += 1
    record_audit(
        db,
        user_id=user.id,
        action="edc_form_update",
        object_type="edc_form",
        object_id=str(form.id),
        request=request,
    )
    db.commit()
    db.refresh(form)
    return _serialize_form(form)


@router.delete("/forms/{form_id}")
def delete_form(
    form_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    form = _load_form(db, form_id, user, minimum="editor")
    fid = str(form.id)
    db.delete(form)
    record_audit(
        db,
        user_id=user.id,
        action="edc_form_delete",
        object_type="edc_form",
        object_id=fid,
        request=request,
    )
    db.commit()
    return {"id": fid, "deleted": True}


def _make_field(form_id: uuid.UUID, payload: EdcFieldInput, position: int) -> EdcField:
    return EdcField(
        id=uuid.uuid4(),
        form_id=form_id,
        position=payload.position if payload.position is not None else position,
        key=payload.key,
        label=payload.label,
        item_type=payload.item_type,
        required=payload.required,
        options_json=payload.options_json,
        fhir_mapping_json=payload.fhir_mapping_json,
        validation_json=payload.validation_json,
    )


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


@router.get("/forms/{form_id}/entries", response_model=list[EntryResponse])
def list_entries(
    form_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[EntryResponse]:
    form = _load_form(db, form_id, user)
    entries = (
        db.query(EdcEntry)
        .filter(EdcEntry.form_id == form.id)
        .order_by(EdcEntry.updated_at.desc())
        .all()
    )
    return [_serialize_entry(e) for e in entries]


@router.post("/forms/{form_id}/entries", response_model=EntryResponse, status_code=201)
def create_entry(
    form_id: str,
    body: dict,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> EntryResponse:
    form = _load_form(db, form_id, user, minimum="editor")
    if form.status == "locked":
        raise HTTPException(status_code=409, detail="Form is locked")
    participant_id = body.get("participant_id") or body.get("participantId")
    if not participant_id:
        raise HTTPException(status_code=400, detail="participant_id required")
    participant = _load_participant(db, str(participant_id), user, minimum="editor")
    if participant.study_id != form.study_id:
        raise HTTPException(status_code=400, detail="Participant belongs to a different study")

    entry = EdcEntry(
        id=uuid.uuid4(),
        form_id=form.id,
        participant_id=participant.id,
        created_by=user.id,
    )
    db.add(entry)
    record_audit(
        db,
        user_id=user.id,
        action="edc_entry_create",
        object_type="edc_entry",
        object_id=str(entry.id),
        request=request,
        extra={"form_id": str(form.id), "participant_id": str(participant.id)},
    )
    db.commit()
    db.refresh(entry)
    return _serialize_entry(entry)


@router.get("/entries/{entry_id}", response_model=EntryResponse)
def get_entry(
    entry_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> EntryResponse:
    return _serialize_entry(_load_entry(db, entry_id, user))


@router.patch("/entries/{entry_id}", response_model=EntryResponse)
def update_entry(
    entry_id: str,
    payload: EntryUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> EntryResponse:
    entry = _load_entry(db, entry_id, user, minimum="editor")
    if entry.status == "locked":
        raise HTTPException(status_code=409, detail="Entry is locked")

    form = db.get(EdcForm, entry.form_id)
    valid_field_ids = {f.id for f in (form.fields if form else [])}

    for v in payload.values:
        if v.field_id not in valid_field_ids:
            raise HTTPException(status_code=400, detail=f"Field {v.field_id} not on form")
        _upsert_value(db, entry, v.field_id, v.value, v.source, v.fhir_source_ref, user, v.reason_for_change)

    if payload.status is not None:
        if payload.status == "complete" and entry.status != "complete":
            entry.completed_at = datetime.utcnow()
        if payload.status == "locked":
            entry.locked_at = datetime.utcnow()
        entry.status = payload.status

    # CTFMS auto-accrue when entry transitions to complete or locked.
    if payload.status in {"complete", "locked"}:
        from app.services.ctfms import auto_accrue_for_entry
        auto_accrue_for_entry(db, entry, by_user_id=user.id)

    record_audit(
        db,
        user_id=user.id,
        action="edc_entry_update",
        object_type="edc_entry",
        object_id=str(entry.id),
        request=request,
        extra={"fields_updated": len(payload.values)},
    )
    db.commit()
    db.refresh(entry)
    return _serialize_entry(entry)


def _upsert_value(
    db: Session,
    entry: EdcEntry,
    field_id: uuid.UUID,
    new_value: Any,
    source: str,
    fhir_source_ref: str | None,
    user: User,
    reason: str | None,
) -> None:
    existing = (
        db.query(EdcEntryField)
        .filter(EdcEntryField.entry_id == entry.id, EdcEntryField.field_id == field_id)
        .first()
    )
    new_value_json = {"value": new_value} if new_value is not None else None
    if existing is None:
        existing = EdcEntryField(
            id=uuid.uuid4(),
            entry_id=entry.id,
            field_id=field_id,
            value_json=new_value_json,
            source=source,
            fhir_source_ref=fhir_source_ref,
            updated_by=user.id,
        )
        db.add(existing)
        db.flush()
        db.add(
            EdcEntryFieldHistory(
                id=uuid.uuid4(),
                entry_field_id=existing.id,
                old_value_json=None,
                new_value_json=new_value_json,
                old_source=None,
                new_source=source,
                changed_by=user.id,
                reason=reason or "initial entry",
            )
        )
        return

    old_value_json = existing.value_json
    if old_value_json == new_value_json and existing.source == source:
        return  # no-op

    db.add(
        EdcEntryFieldHistory(
            id=uuid.uuid4(),
            entry_field_id=existing.id,
            old_value_json=old_value_json,
            new_value_json=new_value_json,
            old_source=existing.source,
            new_source=source,
            changed_by=user.id,
            reason=reason,
        )
    )
    existing.value_json = new_value_json
    existing.source = source
    existing.fhir_source_ref = fhir_source_ref
    existing.updated_by = user.id
    existing.updated_at = datetime.utcnow()


@router.post("/entries/{entry_id}/pull", response_model=list[FhirPullResult])
def pull_entry(
    entry_id: str,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    field_id: Optional[str] = Query(None, description="Pull only this field"),
) -> list[FhirPullResult]:
    entry = _load_entry(db, entry_id, user, minimum="editor")
    if entry.status == "locked":
        raise HTTPException(status_code=409, detail="Entry is locked")
    form = db.get(EdcForm, entry.form_id)
    participant = db.get(StudyParticipant, entry.participant_id)
    if form is None or participant is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    fields_to_pull: list[tuple[str, str, dict | None]] = []
    if field_id:
        fid = _parse_uuid(field_id, "field_id")
        f = next((x for x in form.fields if x.id == fid), None)
        if f is None or not f.fhir_mapping_json:
            raise HTTPException(status_code=400, detail="Field has no FHIR mapping")
        fields_to_pull.append((str(f.id), f.key, f.fhir_mapping_json))
    else:
        for f in form.fields:
            if f.fhir_mapping_json:
                fields_to_pull.append((str(f.id), f.key, f.fhir_mapping_json))

    if not fields_to_pull:
        return []

    client = _build_fhir_client(request)
    results = pull_all_for_entry(client, participant.patient_id, fields_to_pull)

    # Persist as fhir_pull source.
    for r in results:
        if r["error"]:
            continue
        _upsert_value(
            db,
            entry,
            uuid.UUID(r["field_id"]),
            r["value"],
            "fhir_pull",
            r["source_ref"],
            user,
            "FHIR pull",
        )

    record_audit(
        db,
        user_id=user.id,
        action="edc_entry_pull",
        object_type="edc_entry",
        object_id=str(entry.id),
        request=request,
        extra={"fields": len(fields_to_pull), "errors": sum(1 for r in results if r["error"])},
    )
    db.commit()
    return [FhirPullResult(**r) for r in results]


@router.post("/entries/{entry_id}/sign", response_model=SignatureResponse, status_code=201)
def sign_entry(
    entry_id: str,
    payload: SignatureCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> SignatureResponse:
    entry = _load_entry(db, entry_id, user, minimum="editor")
    if entry.status not in {"complete", "locked"}:
        raise HTTPException(status_code=409, detail="Entry must be complete before signing")

    settings = get_settings()
    # PATCHED (audit fix, high): previously fell back to the hardcoded
    # public string "edc-fallback" as the HMAC key when SESSION_SECRET was
    # unset, unlike core/security.py's issue_session_token/verify_session_token,
    # which correctly raise when that same setting is missing. Since
    # SESSION_SECRET is `sync: false` in render.yaml (an operator can forget
    # to set it), any deploy that omits it would accept and "validate"
    # Part-11-style e-signatures signed with a secret published in this
    # repo, defeating the signature's integrity guarantee. Fail closed
    # instead, matching security.py's own pattern.
    if not settings.session_secret:
        raise HTTPException(
            status_code=503,
            detail="SESSION_SECRET not configured; cannot produce a trustworthy e-signature",
        )

    snapshot = json.dumps(
        {
            "entry_id": str(entry.id),
            "values": [
                {
                    "field_id": str(v.field_id),
                    "value": (v.value_json or {}).get("value"),
                    "source": v.source,
                }
                for v in entry.field_values
            ],
            "user_id": str(user.id),
            "meaning": payload.meaning,
            "confirmation": payload.confirmation,
            "ts": datetime.utcnow().isoformat(),
        },
        sort_keys=True,
    )
    digest = hmac.new(
        settings.session_secret.encode(),
        snapshot.encode(),
        hashlib.sha256,
    ).hexdigest()

    sig = EdcSignature(
        id=uuid.uuid4(),
        entry_id=entry.id,
        user_id=user.id,
        meaning=payload.meaning,
        signature_hash=digest,
    )
    db.add(sig)
    if entry.status == "complete":
        entry.status = "locked"
        entry.locked_at = datetime.utcnow()

    # CTFMS auto-accrue on sign (in case entry was completed without going through PATCH).
    from app.services.ctfms import auto_accrue_for_entry
    auto_accrue_for_entry(db, entry, by_user_id=user.id)

    record_audit(
        db,
        user_id=user.id,
        action="edc_entry_sign",
        object_type="edc_entry",
        object_id=str(entry.id),
        request=request,
        extra={"meaning": payload.meaning},
    )
    db.commit()
    db.refresh(sig)
    return _serialize_signature(sig)


@router.get("/entries/{entry_id}/history", response_model=list[EntryHistoryItem])
def entry_history(
    entry_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[EntryHistoryItem]:
    entry = _load_entry(db, entry_id, user)
    field_keys = {f.id: f.key for f in db.query(EdcField).filter(EdcField.form_id == entry.form_id).all()}
    rows = (
        db.query(EdcEntryFieldHistory, EdcEntryField)
        .join(EdcEntryField, EdcEntryFieldHistory.entry_field_id == EdcEntryField.id)
        .filter(EdcEntryField.entry_id == entry.id)
        .order_by(EdcEntryFieldHistory.changed_at.desc())
        .all()
    )
    out: list[EntryHistoryItem] = []
    for hist, ef in rows:
        out.append(
            EntryHistoryItem(
                field_id=str(ef.field_id),
                fieldKey=field_keys.get(ef.field_id, ""),
                oldValue=(hist.old_value_json or {}).get("value") if hist.old_value_json else None,
                newValue=(hist.new_value_json or {}).get("value") if hist.new_value_json else None,
                oldSource=hist.old_source,
                newSource=hist.new_source,
                changedBy=str(hist.changed_by) if hist.changed_by else None,
                reason=hist.reason,
                changedAt=hist.changed_at,
            )
        )
    return out
