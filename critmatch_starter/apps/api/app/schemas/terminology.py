from typing import Dict, List

from pydantic import BaseModel, Field


class TerminologyExpandRequest(BaseModel):
    text: str
    domains: List[str]
    includeSynonyms: bool = True
    includeMappedCodes: bool = True
    targetCodeSystems: List[str] = Field(default_factory=lambda: ["ICD10CM", "SNOMEDCT", "CPT"])


class TerminologyExpandResponse(BaseModel):
    normalizedTerm: str
    expansions: List[Dict[str, str]]
