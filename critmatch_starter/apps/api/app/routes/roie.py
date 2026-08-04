"""ROIE placeholder endpoints.

These endpoints provide lightweight, deterministic payloads so the web app can
render interactive ROIE views before full pipeline integration lands.

PATCHED (audit fix, medium): both endpoints already labeled their payload as
"preview"/placeholder data in the response body (``status="preview"`` and a
``note`` field), but there was no server-side signal an operator could alert
on if this fake data ever got surfaced somewhere a user could mistake it for
real results (a page exists in the web app at ``apps/web/src/app/roie/page.tsx``).
Added a log warning on every call when running in production, plus an
``X-CritMatch-Preview-Data`` response header, so this is observable and
alertable without guessing at (and potentially getting wrong) whether an
operator wants the feature hard-disabled in production - that's a product
decision this patch doesn't have enough information to make safely.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.deps.auth import CurrentUser

router = APIRouter()

logger = logging.getLogger("critmatch.roie")


class RoieStatus(BaseModel):
    module: str
    status: str
    source: str
    refreshedAt: str
    note: str


class RoieOpportunity(BaseModel):
    id: str
    title: str
    nctId: str
    studyUrl: str
    recruitingStatus: str
    studyContactName: str | None = None
    studyContactEmail: str | None = None
    studyContactPhone: str | None = None
    sponsor: str
    phase: str
    indication: str
    region: str
    siteMatchScore: float
    enrollmentPotential: str
    diversityPotential: str


def _mark_preview_response(response: Response) -> None:
    response.headers["X-CritMatch-Preview-Data"] = "true"
    if get_settings().is_production:
        logger.warning("ROIE preview/placeholder data served in production")


@router.get("/status", response_model=RoieStatus)
def get_roie_status(user: CurrentUser, response: Response) -> RoieStatus:
    _ = user
    _mark_preview_response(response)
    return RoieStatus(
        module="ROIE",
        status="preview",
        source="ClinicalTrials.gov + CritMatch profile matching (placeholder)",
        refreshedAt=datetime.now(UTC).isoformat(),
        note="Preview data only. Replace with production ingestion and scoring jobs.",
    )


@router.get("/opportunities", response_model=list[RoieOpportunity])
def list_roie_opportunities(
    user: CurrentUser,
    response: Response,
    limit: int = Query(default=6, ge=1, le=20),
) -> list[RoieOpportunity]:
    _ = user
    _mark_preview_response(response)
    seed: list[RoieOpportunity] = [
        RoieOpportunity(
            id="roie-001",
            title="Phase II Precision Oncology Basket Trial",
            nctId="NCT06230011",
            studyUrl="https://clinicaltrials.gov/study/NCT06230011",
            recruitingStatus="Recruiting",
            studyContactName="Laura Finch, RN",
            studyContactEmail="laura.finch@nstar-thera.example",
            studyContactPhone="+1-312-555-0147",
            sponsor="Northstar Therapeutics",
            phase="Phase II",
            indication="Solid Tumors",
            region="US Midwest",
            siteMatchScore=0.92,
            enrollmentPotential="High",
            diversityPotential="High",
        ),
        RoieOpportunity(
            id="roie-002",
            title="Type 2 Diabetes Real-World Intervention Study",
            nctId="NCT05992044",
            studyUrl="https://clinicaltrials.gov/study/NCT05992044",
            recruitingStatus="Recruiting",
            studyContactName="Angela Reed",
            studyContactEmail="angela.reed@asterbio.example",
            studyContactPhone="+1-404-555-0172",
            sponsor="Aster Biopharma",
            phase="Phase III",
            indication="Endocrinology",
            region="Southeast US",
            siteMatchScore=0.88,
            enrollmentPotential="High",
            diversityPotential="Medium",
        ),
        RoieOpportunity(
            id="roie-003",
            title="Heart Failure Digital Monitoring Trial",
            nctId="NCT06117783",
            studyUrl="https://clinicaltrials.gov/study/NCT06117783",
            recruitingStatus="Active, not recruiting",
            studyContactName="Marcus Ellis, MD",
            studyContactEmail="mellis@helixcardio.example",
            studyContactPhone="+1-617-555-0139",
            sponsor="Helix Cardio",
            phase="Phase II",
            indication="Cardiology",
            region="Northeast US",
            siteMatchScore=0.83,
            enrollmentPotential="Medium",
            diversityPotential="High",
        ),
        RoieOpportunity(
            id="roie-004",
            title="Pediatric Rare Disease Registry Expansion",
            nctId="NCT05874420",
            studyUrl="https://clinicaltrials.gov/study/NCT05874420",
            recruitingStatus="Recruiting",
            studyContactName="Priya Narang",
            studyContactEmail="p.narang@luminarare.example",
            studyContactPhone=None,
            sponsor="Lumina Rare",
            phase="Observational",
            indication="Rare Disease",
            region="Western US",
            siteMatchScore=0.79,
            enrollmentPotential="Medium",
            diversityPotential="High",
        ),
        RoieOpportunity(
            id="roie-005",
            title="COPD Rescue Inhaler Comparative Study",
            nctId="NCT05744092",
            studyUrl="https://clinicaltrials.gov/study/NCT05744092",
            recruitingStatus="Not yet recruiting",
            studyContactName="Kristen Ochoa",
            studyContactEmail=None,
            studyContactPhone="+1-602-555-0118",
            sponsor="Summit Respiratory",
            phase="Phase IV",
            indication="Pulmonology",
            region="Southwest US",
            siteMatchScore=0.76,
            enrollmentPotential="Medium",
            diversityPotential="Medium",
        ),
        RoieOpportunity(
            id="roie-006",
            title="Chronic Kidney Disease Biomarker Trial",
            nctId="NCT06011306",
            studyUrl="https://clinicaltrials.gov/study/NCT06011306",
            recruitingStatus="Recruiting",
            studyContactName="Daniel Cho",
            studyContactEmail="dcho@vantagerenal.example",
            studyContactPhone="+1-206-555-0194",
            sponsor="Vantage Renal",
            phase="Phase II",
            indication="Nephrology",
            region="US National",
            siteMatchScore=0.73,
            enrollmentPotential="Low",
            diversityPotential="Medium",
        ),
    ]
    return seed[:limit]
