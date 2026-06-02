"""Community Partner Network placeholder endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps.auth import CurrentUser

router = APIRouter()


class CommunityPartner(BaseModel):
    id: str
    name: str
    kind: str
    city: str
    state: str
    languages: list[str]
    activeReferrals: int
    enrolledParticipants: int
    lastActivity: str


class CommunitySummary(BaseModel):
    partnerCount: int
    activeReferrals: int
    enrolledParticipants: int
    topLanguageNeeds: list[str]


@router.get("/partners", response_model=list[CommunityPartner])
def list_partners(user: CurrentUser) -> list[CommunityPartner]:
    _ = user
    return [
        CommunityPartner(
            id="cp-001",
            name="Southside Community Health Collective",
            kind="FQHC",
            city="Chicago",
            state="IL",
            languages=["English", "Spanish"],
            activeReferrals=28,
            enrolledParticipants=13,
            lastActivity="2026-06-01",
        ),
        CommunityPartner(
            id="cp-002",
            name="Metro Faith & Wellness Alliance",
            kind="Community Organization",
            city="Detroit",
            state="MI",
            languages=["English", "Arabic"],
            activeReferrals=17,
            enrolledParticipants=8,
            lastActivity="2026-06-02",
        ),
        CommunityPartner(
            id="cp-003",
            name="Eastside Family Resource Center",
            kind="Navigation Hub",
            city="Baltimore",
            state="MD",
            languages=["English", "French", "Creole"],
            activeReferrals=22,
            enrolledParticipants=11,
            lastActivity="2026-05-31",
        ),
    ]


@router.get("/summary", response_model=CommunitySummary)
def community_summary(user: CurrentUser) -> CommunitySummary:
    _ = user
    return CommunitySummary(
        partnerCount=3,
        activeReferrals=67,
        enrolledParticipants=32,
        topLanguageNeeds=["Spanish", "Arabic", "Creole"],
    )
