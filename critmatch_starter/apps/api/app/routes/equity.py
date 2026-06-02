"""Equity scorecard placeholder endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps.auth import CurrentUser

router = APIRouter()


class EquityMetric(BaseModel):
    category: str
    subgroup: str
    screened: int
    enrolled: int
    conversionRate: float


class EquityAlert(BaseModel):
    id: str
    severity: str
    title: str
    recommendation: str


@router.get("/scorecard", response_model=list[EquityMetric])
def scorecard(user: CurrentUser) -> list[EquityMetric]:
    _ = user
    return [
        EquityMetric(
            category="Race",
            subgroup="Black / African American",
            screened=210,
            enrolled=58,
            conversionRate=27.6,
        ),
        EquityMetric(
            category="Race",
            subgroup="White",
            screened=285,
            enrolled=96,
            conversionRate=33.7,
        ),
        EquityMetric(
            category="Ethnicity",
            subgroup="Hispanic / Latino",
            screened=190,
            enrolled=48,
            conversionRate=25.3,
        ),
        EquityMetric(
            category="Language",
            subgroup="Non-English preferred",
            screened=132,
            enrolled=29,
            conversionRate=22.0,
        ),
    ]


@router.get("/alerts", response_model=list[EquityAlert])
def alerts(user: CurrentUser) -> list[EquityAlert]:
    _ = user
    return [
        EquityAlert(
            id="ea-001",
            severity="high",
            title="Lower conversion for non-English participants",
            recommendation="Increase interpreter staffing and translated pre-screen messaging.",
        ),
        EquityAlert(
            id="ea-002",
            severity="medium",
            title="Enrollment lag in two underserved zip-code clusters",
            recommendation="Activate mobile screening and community-partner referral campaign.",
        ),
    ]
