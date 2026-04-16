from typing import Any, Dict, Optional

from pydantic import BaseModel


class QueryRunRequest(BaseModel):
    studyId: str
    criteriaSetId: str
    filters: Optional[Dict[str, Any]] = None
