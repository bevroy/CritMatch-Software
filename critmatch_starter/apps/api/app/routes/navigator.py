"""Community navigator workflow placeholder endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps.auth import CurrentUser

router = APIRouter()


class NavigatorTask(BaseModel):
    id: str
    participantId: str
    participantAlias: str
    barrier: str
    priority: str
    status: str
    dueDate: str
    assignedTo: str


class NavigatorMetrics(BaseModel):
    openTasks: int
    inProgressTasks: int
    resolvedTasks30d: int
    medianResolutionDays: float


@router.get("/tasks", response_model=list[NavigatorTask])
def list_tasks(user: CurrentUser) -> list[NavigatorTask]:
    _ = user
    return [
        NavigatorTask(
            id="nt-001",
            participantId="p-4302",
            participantAlias="Participant 4302",
            barrier="Transportation",
            priority="high",
            status="open",
            dueDate="2026-06-04",
            assignedTo="Navigator A",
        ),
        NavigatorTask(
            id="nt-002",
            participantId="p-4411",
            participantAlias="Participant 4411",
            barrier="Language interpretation",
            priority="high",
            status="in_progress",
            dueDate="2026-06-03",
            assignedTo="Navigator B",
        ),
        NavigatorTask(
            id="nt-003",
            participantId="p-4460",
            participantAlias="Participant 4460",
            barrier="Childcare",
            priority="medium",
            status="open",
            dueDate="2026-06-06",
            assignedTo="Navigator A",
        ),
        NavigatorTask(
            id="nt-004",
            participantId="p-4505",
            participantAlias="Participant 4505",
            barrier="Digital access",
            priority="medium",
            status="resolved",
            dueDate="2026-05-30",
            assignedTo="Navigator C",
        ),
    ]


@router.get("/metrics", response_model=NavigatorMetrics)
def navigator_metrics(user: CurrentUser) -> NavigatorMetrics:
    _ = user
    return NavigatorMetrics(
        openTasks=2,
        inProgressTasks=1,
        resolvedTasks30d=26,
        medianResolutionDays=3.4,
    )
