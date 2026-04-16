from typing import Any, Optional

from pydantic import BaseModel


class StudyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner_user_id: Optional[str] = None


class StudyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str


class CriteriaSetCreate(BaseModel):
    version: int
    logic_json: Any
    created_by: Optional[str] = None
