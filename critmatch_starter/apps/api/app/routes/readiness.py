"""Real-World Data & Research Readiness Engine placeholder endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps.auth import CurrentUser

router = APIRouter()


class ReadinessStatus(BaseModel):
    module: str
    status: str
    refreshedAt: str
    note: str


class ReadinessProfile(BaseModel):
    siteId: str
    siteName: str
    readinessScore: int
    eligiblePopulationEstimate: int
    feasibilityTier: str
    primaryIndications: list[str]
    careGaps: list[str]
    sponsorReadySummary: str


@router.get("/status", response_model=ReadinessStatus)
def get_readiness_status(user: CurrentUser) -> ReadinessStatus:
    _ = user
    return ReadinessStatus(
        module="RWD & Research Readiness Engine",
        status="preview",
        refreshedAt=datetime.now(UTC).isoformat(),
        note="Preview values only. Replace with production RWD pipelines and site scoring logic.",
    )


@router.get("/profile", response_model=ReadinessProfile)
def get_readiness_profile(user: CurrentUser) -> ReadinessProfile:
    _ = user
    return ReadinessProfile(
        siteId="site-chi-001",
        siteName="CritMatch Demonstration Medical Center",
        readinessScore=84,
        eligiblePopulationEstimate=1260,
        feasibilityTier="High",
        primaryIndications=["Oncology", "Cardiology", "Endocrinology"],
        careGaps=[
            "Low minority participation in cardiometabolic trials",
            "Delayed referral from primary care to research intake",
            "Limited weekend screening capacity",
        ],
        sponsorReadySummary=(
            "Site has strong EHR data completeness, active PI coverage, and scalable recruitment "
            "operations with moderate workflow gaps that can be remediated in 30-60 days."
        ),
    )
