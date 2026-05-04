"""Pydantic schemas for the feasibility module."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeasibilityQuestionInput(BaseModel):
    """A single question in a questionnaire.

    ``logic_json`` follows the same shape as ``criteria_sets.logic_json`` but is
    interpreted by the feasibility engine to produce an aggregate count. See
    services/feasibility_engine.py for the supported rule kinds.
    """

    text: str
    logic_json: Any
    position: Optional[int] = None


class FeasibilityQuestionnaireCreate(BaseModel):
    name: str
    description: Optional[str] = None
    studyId: Optional[str] = None  # noqa: N815 - camelCase wire field
    questions: List[FeasibilityQuestionInput] = Field(default_factory=list)


class FeasibilityQuestionnaireUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    studyId: Optional[str] = None  # noqa: N815
    questions: Optional[List[FeasibilityQuestionInput]] = None


class FeasibilityQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
    text: str
    logicJson: Any  # noqa: N815

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return str(v) if v is not None else v


class FeasibilityQuestionnaireResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    studyId: Optional[str] = None  # noqa: N815
    createdBy: Optional[str] = None  # noqa: N815
    createdAt: str  # noqa: N815
    updatedAt: str  # noqa: N815
    questions: List[FeasibilityQuestionResponse] = Field(default_factory=list)


class FeasibilityQuestionnaireSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    studyId: Optional[str] = None  # noqa: N815
    questionCount: int  # noqa: N815
    updatedAt: str  # noqa: N815


class FeasibilityResultItem(BaseModel):
    questionId: str  # noqa: N815
    questionText: str  # noqa: N815
    count: int
    detail: Optional[dict[str, Any]] = None


class FeasibilityRunResponse(BaseModel):
    id: str
    questionnaireId: str  # noqa: N815
    status: str
    totalPatients: Optional[int] = None  # noqa: N815
    executionMs: Optional[int] = None  # noqa: N815
    errorMessage: Optional[str] = None  # noqa: N815
    createdAt: str  # noqa: N815
    results: List[FeasibilityResultItem] = Field(default_factory=list)
