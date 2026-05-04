"""Tests for the CTFMS module."""

from __future__ import annotations

import uuid


def _make_study(db, owner_id, name="Trial Y"):
    from app.db.models import Study
    s = Study(id=uuid.uuid4(), name=name, owner_user_id=owner_id, status="active")
    db.add(s)
    db.commit()
    return s


def _make_finance_user(db):
    from app.db.models import User
    u = User(id=uuid.uuid4(), ehr_user_id=f"fin-{uuid.uuid4().hex[:8]}", name="Fin", role="research_user")
    db.add(u)
    db.commit()
    return u


def _add_collab(db, study_id, user_id, role):
    from app.db.models import StudyCollaborator
    c = StudyCollaborator(study_id=study_id, user_id=user_id, role=role)
    db.add(c)
    db.commit()


def _client_for(client, user):
    from app.core.config import get_settings
    from app.core.security import issue_session_token
    token = issue_session_token({"sub": str(user.id), "role": user.role})
    client.cookies.set(get_settings().session_cookie_name, token)
    return client


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


def test_budget_crud_and_versioning(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    payload = {
        "study_id": str(study.id),
        "name": "Sponsor X 2025",
        "sponsor": "Sponsor X",
        "currency": "USD",
        "items": [
            {"name": "Visit 1", "item_type": "per_visit", "unit_price": 25000, "currency": "USD"},
            {"name": "ECG", "item_type": "per_procedure", "unit_price": 7500, "currency": "USD"},
        ],
    }
    r = authed_client.post("/api/ctfms/budgets", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["study_id"] == str(study.id)
    assert body["version"] == 1
    assert body["status"] == "draft"
    assert len(body["items"]) == 2
    bid = body["id"]

    # Second budget for same study bumps version
    r2 = authed_client.post("/api/ctfms/budgets", json={**payload, "name": "Amend 1"})
    assert r2.status_code == 201
    assert r2.json()["version"] == 2

    # List
    r = authed_client.get(f"/api/ctfms/budgets?studyId={study.id}")
    assert r.status_code == 200
    assert len(r.json()) == 2

    # Update activates and replaces items
    r = authed_client.patch(f"/api/ctfms/budgets/{bid}", json={
        "status": "active",
        "items": [{"name": "Visit 1", "item_type": "per_visit", "unit_price": 30000, "currency": "USD"}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert len(body["items"]) == 1
    assert body["items"][0]["unit_price"] == 30000

    # Delete
    r = authed_client.delete(f"/api/ctfms/budgets/{bid}")
    assert r.status_code == 200
    assert authed_client.get(f"/api/ctfms/budgets/{bid}").status_code == 404


# ---------------------------------------------------------------------------
# Manual accruals + invoicing + payments
# ---------------------------------------------------------------------------


def _make_active_budget(authed_client, study, items=None):
    items = items or [
        {"name": "Visit 1", "item_type": "per_visit", "unit_price": 20000, "currency": "USD"},
    ]
    r = authed_client.post("/api/ctfms/budgets", json={
        "study_id": str(study.id), "name": "B", "currency": "USD", "items": items,
    })
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    r = authed_client.patch(f"/api/ctfms/budgets/{bid}", json={"status": "active"})
    assert r.status_code == 200, r.text
    return r.json()


def test_manual_accrual_and_invoice_and_payment(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    budget = _make_active_budget(authed_client, study)
    item = budget["items"][0]

    # Manual accrual
    r = authed_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": item["id"], "quantity": 2,
    })
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["quantity"] == 2
    assert a["amount"] == 2 * item["unit_price"]
    assert a["status"] == "accrued"

    # Second accrual
    r = authed_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": item["id"],
    })
    a2 = r.json()

    # List & filter
    r = authed_client.get(f"/api/ctfms/accruals?studyId={study.id}&status=accrued")
    assert r.status_code == 200
    assert len(r.json()) == 2

    # Invoice both accruals
    r = authed_client.post(f"/api/ctfms/studies/{study.id}/invoices", json={
        "accrual_ids": [a["id"], a2["id"]], "notes": "Q1 invoice",
    })
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "draft"
    assert inv["total"] == a["amount"] + a2["amount"]
    assert len(inv["lines"]) == 2

    # Already-invoiced accruals are rejected
    r = authed_client.post(f"/api/ctfms/studies/{study.id}/invoices", json={
        "accrual_ids": [a["id"]],
    })
    assert r.status_code == 400

    # Send the invoice
    r = authed_client.patch(f"/api/ctfms/invoices/{inv['id']}", json={"status": "sent"})
    assert r.status_code == 200
    assert r.json()["sent_at"] is not None

    # Partial payment
    half = inv["total"] // 2
    r = authed_client.post(f"/api/ctfms/studies/{study.id}/payments", json={
        "invoice_id": inv["id"], "amount": half, "currency": "USD",
    })
    assert r.status_code == 201
    inv_after = authed_client.get(f"/api/ctfms/invoices/{inv['id']}").json()
    assert inv_after["status"] == "partial"
    assert inv_after["amount_paid"] == half

    # Remainder
    r = authed_client.post(f"/api/ctfms/studies/{study.id}/payments", json={
        "invoice_id": inv["id"], "amount": inv["total"] - half, "currency": "USD",
    })
    assert r.status_code == 201
    inv_after = authed_client.get(f"/api/ctfms/invoices/{inv['id']}").json()
    assert inv_after["status"] == "paid"


def test_invoice_rejects_mixed_currency(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    budget = _make_active_budget(authed_client, study, items=[
        {"name": "USD item", "item_type": "per_visit", "unit_price": 100, "currency": "USD"},
        {"name": "EUR item", "item_type": "per_visit", "unit_price": 100, "currency": "EUR"},
    ])
    items = {i["name"]: i for i in budget["items"]}
    a_usd = authed_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": items["USD item"]["id"],
    }).json()
    a_eur = authed_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": items["EUR item"]["id"],
    }).json()
    r = authed_client.post(f"/api/ctfms/studies/{study.id}/invoices", json={
        "accrual_ids": [a_usd["id"], a_eur["id"]],
    })
    assert r.status_code == 400
    assert "currenc" in r.json()["detail"].lower()


def test_invoice_void_releases_accruals(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    budget = _make_active_budget(authed_client, study)
    item = budget["items"][0]
    a = authed_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": item["id"],
    }).json()
    inv = authed_client.post(f"/api/ctfms/studies/{study.id}/invoices", json={
        "accrual_ids": [a["id"]],
    }).json()
    # Void
    r = authed_client.patch(f"/api/ctfms/invoices/{inv['id']}", json={"status": "void"})
    assert r.status_code == 200
    # Accrual should be back to 'accrued'
    a_after = next(x for x in authed_client.get(f"/api/ctfms/accruals?studyId={study.id}").json()
                   if x["id"] == a["id"])
    assert a_after["status"] == "accrued"
    assert a_after["invoice_line_id"] is None


# ---------------------------------------------------------------------------
# Stipends
# ---------------------------------------------------------------------------


def test_stipend_create_and_pay(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)

    # Create participant
    r = authed_client.post(f"/api/studies/{study.id}/participants", json={
        "patient_id": "pat-1", "subject_id": "S-001", "status": "enrolled",
    })
    assert r.status_code == 201
    pid = r.json()["id"]

    r = authed_client.post(f"/api/ctfms/studies/{study.id}/stipends", json={
        "participant_id": pid, "amount": 5000, "currency": "USD",
    })
    assert r.status_code == 201
    s = r.json()
    assert s["status"] == "pending"

    r = authed_client.patch(f"/api/ctfms/stipends/{s['id']}", json={
        "status": "paid", "method": "check", "reference": "CHK-001",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "paid"
    assert body["paid_at"] is not None


# ---------------------------------------------------------------------------
# Auto-accrue from EDC entry signing
# ---------------------------------------------------------------------------


def test_auto_accrue_from_entry_signing(authed_client, db_session, authed_user):
    """Sign an EDC entry → matching budget items create accruals automatically."""
    study = _make_study(db_session, authed_user.id)

    # Create an EDC form
    r = authed_client.post("/api/edc/forms", json={
        "study_id": str(study.id), "name": "Visit 1",
        "fields": [
            {"key": "ecg", "label": "ECG done?", "item_type": "boolean"},
            {"key": "weight", "label": "Weight", "item_type": "decimal"},
        ],
    })
    assert r.status_code == 201, r.text
    form = r.json()
    fields = {f["key"]: f for f in form["fields"]}

    # Build an active budget with per-visit (linked to the form), per-procedure
    # (linked to the ecg field), patient_stipend (per visit), and a manual-only
    # fixed_milestone (auto_accrue=False) item.
    budget = _make_active_budget(authed_client, study, items=[
        {"name": "Visit 1 fee", "item_type": "per_visit", "unit_price": 30000,
         "currency": "USD", "edc_form_id": form["id"]},
        {"name": "ECG procedure", "item_type": "per_procedure", "unit_price": 5000,
         "currency": "USD", "edc_form_id": form["id"], "edc_field_id": fields["ecg"]["id"]},
        {"name": "Travel stipend", "item_type": "patient_stipend", "unit_price": 2500,
         "currency": "USD", "edc_form_id": form["id"]},
        {"name": "Milestone", "item_type": "fixed_milestone", "unit_price": 100000,
         "currency": "USD", "auto_accrue": False},
    ])

    # Create participant + entry, set values, sign
    p = authed_client.post(f"/api/studies/{study.id}/participants", json={
        "patient_id": "pat-1", "subject_id": "S-001", "status": "enrolled",
    }).json()
    entry = authed_client.post(f"/api/edc/forms/{form['id']}/entries",
                               json={"participant_id": p["id"]}).json()
    r = authed_client.patch(f"/api/edc/entries/{entry['id']}", json={"values": [
        {"field_id": fields["ecg"]["id"], "value": True},
        {"field_id": fields["weight"]["id"], "value": 70.5},
    ], "status": "complete"})
    assert r.status_code == 200, r.text

    # Sign the entry (transitions to locked)
    r = authed_client.post(f"/api/edc/entries/{entry['id']}/sign", json={"meaning": "author"})
    assert r.status_code == 201, r.text

    # Verify auto-accruals
    accruals = authed_client.get(f"/api/ctfms/accruals?studyId={study.id}").json()
    by_amount = sorted(a["amount"] for a in accruals)
    assert by_amount == [5000, 30000], f"expected per_visit + per_procedure accruals, got {accruals}"
    # No accrual for the manual-only milestone
    assert all(a["amount"] != 100000 for a in accruals)

    # Stipend was created (not an accrual)
    stipends = authed_client.get(f"/api/ctfms/stipends?studyId={study.id}").json()
    assert len(stipends) == 1
    assert stipends[0]["amount"] == 2500
    assert stipends[0]["status"] == "pending"

    # Idempotency: re-signing does not double-accrue.
    # (Re-signing is rejected as locked, so transition complete instead via update.)
    # Triggering the hook manually proves idempotency directly.
    from app.db.models import EdcEntry
    from app.services.ctfms import auto_accrue_for_entry
    e = db_session.query(EdcEntry).filter(EdcEntry.id == uuid.UUID(entry["id"])).one()
    auto_accrue_for_entry(db_session, e, by_user_id=authed_user.id)
    db_session.commit()
    accruals2 = authed_client.get(f"/api/ctfms/accruals?studyId={study.id}").json()
    assert len(accruals2) == len(accruals), "re-running auto_accrue must be idempotent"


def test_auto_accrue_skips_falsy_per_procedure(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    r = authed_client.post("/api/edc/forms", json={
        "study_id": str(study.id), "name": "Visit",
        "fields": [{"key": "ecg", "label": "ECG", "item_type": "boolean"}],
    })
    form = r.json()
    fields = {f["key"]: f for f in form["fields"]}

    _make_active_budget(authed_client, study, items=[
        {"name": "Visit fee", "item_type": "per_visit", "unit_price": 1000,
         "currency": "USD", "edc_form_id": form["id"]},
        {"name": "ECG", "item_type": "per_procedure", "unit_price": 500,
         "currency": "USD", "edc_form_id": form["id"], "edc_field_id": fields["ecg"]["id"]},
    ])
    p = authed_client.post(f"/api/studies/{study.id}/participants", json={
        "patient_id": "pat-2", "subject_id": "S-002",
    }).json()
    entry = authed_client.post(f"/api/edc/forms/{form['id']}/entries",
                               json={"participant_id": p["id"]}).json()
    # ECG = false → only per_visit accrues
    authed_client.patch(f"/api/edc/entries/{entry['id']}", json={"values": [
        {"field_id": fields["ecg"]["id"], "value": False},
    ], "status": "complete"})
    authed_client.post(f"/api/edc/entries/{entry['id']}/sign", json={"meaning": "author"})

    accruals = authed_client.get(f"/api/ctfms/accruals?studyId={study.id}").json()
    assert [a["amount"] for a in accruals] == [1000]


# ---------------------------------------------------------------------------
# Finance role gating
# ---------------------------------------------------------------------------


def test_editor_cannot_create_invoice_or_payment(client, db_session, authed_user):
    """An editor (non-finance) collaborator may create accruals but not invoices/payments."""
    # Owner sets up budget + accrual
    owner_client = _client_for(client, authed_user)
    study = _make_study(db_session, authed_user.id)
    budget = _make_active_budget(owner_client, study)
    item = budget["items"][0]
    a = owner_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": item["id"],
    }).json()

    # Editor collaborator tries to invoice/pay
    editor = _make_finance_user(db_session)
    _add_collab(db_session, study.id, editor.id, "editor")
    ec = _client_for(client, editor)
    r = ec.post(f"/api/ctfms/studies/{study.id}/invoices", json={"accrual_ids": [a["id"]]})
    assert r.status_code == 403
    r = ec.post(f"/api/ctfms/studies/{study.id}/payments",
                json={"amount": 100, "currency": "USD"})
    assert r.status_code == 403


def test_finance_role_can_invoice_and_pay(client, db_session, authed_user):
    owner_client = _client_for(client, authed_user)
    study = _make_study(db_session, authed_user.id)
    budget = _make_active_budget(owner_client, study)
    item = budget["items"][0]
    a = owner_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals", json={
        "budget_item_id": item["id"],
    }).json()

    finance = _make_finance_user(db_session)
    _add_collab(db_session, study.id, finance.id, "finance")
    fc = _client_for(client, finance)

    # Finance can read accruals
    r = fc.get(f"/api/ctfms/accruals?studyId={study.id}")
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1

    # Finance can invoice + pay
    r = fc.post(f"/api/ctfms/studies/{study.id}/invoices", json={"accrual_ids": [a["id"]]})
    assert r.status_code == 201, r.text
    inv = r.json()
    r = fc.post(f"/api/ctfms/studies/{study.id}/payments", json={
        "invoice_id": inv["id"], "amount": inv["total"], "currency": "USD",
    })
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_finance_summary(authed_client, db_session, authed_user):
    study = _make_study(db_session, authed_user.id)
    budget = _make_active_budget(authed_client, study)
    item = budget["items"][0]
    a = authed_client.post(f"/api/ctfms/budgets/{budget['id']}/accruals",
                           json={"budget_item_id": item["id"], "quantity": 3}).json()
    inv = authed_client.post(f"/api/ctfms/studies/{study.id}/invoices",
                             json={"accrual_ids": [a["id"]]}).json()
    authed_client.post(f"/api/ctfms/studies/{study.id}/payments", json={
        "invoice_id": inv["id"], "amount": inv["total"] // 2, "currency": "USD",
    })

    r = authed_client.get(f"/api/ctfms/studies/{study.id}/summary")
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["accruedInvoiced"] == inv["total"]
    assert s["invoiceTotal"] == inv["total"]
    assert s["paid"] == inv["total"] // 2
    assert s["outstanding"] == inv["total"] - (inv["total"] // 2)


# ---------------------------------------------------------------------------
# Cross-study isolation
# ---------------------------------------------------------------------------


def test_cross_study_budget_rejected(client, db_session, authed_user):
    study_a = _make_study(db_session, authed_user.id, name="A")
    other_owner = _make_finance_user(db_session)
    study_b = _make_study(db_session, other_owner.id, name="B")

    me = _client_for(client, authed_user)
    # I cannot create a budget in study B (no access)
    r = me.post("/api/ctfms/budgets", json={
        "study_id": str(study_b.id), "name": "x", "currency": "USD", "items": [],
    })
    assert r.status_code in (403, 404)

    # And accruals from B are not visible to me
    r = me.get(f"/api/ctfms/accruals?studyId={study_b.id}")
    assert r.status_code in (403, 404)
