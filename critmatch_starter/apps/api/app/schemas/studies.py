from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class StudyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner_user_id: Optional[str] = None


class StudyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    status: str

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return str(v) if v is not None else v


class CriteriaSetCreate(BaseModel):
    version: int
    logic_json: Any
    created_by: Optional[str] = None
