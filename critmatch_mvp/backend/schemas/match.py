from pydantic import BaseModel, Field
from typing import Any, Literal


class LabCriterion(BaseModel):
    name: str
    operator: Literal['>', '>=', '<', '<=', '=', '==']
    value: float


class TrialInclusion(BaseModel):
    age_min: int | None = None
    age_max: int | None = None
    diagnoses: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    icd10: list[str] = Field(default_factory=list)
    labs: list[LabCriterion] = Field(default_factory=list)


class TrialExclusion(BaseModel):
    diagnoses: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    icd10: list[str] = Field(default_factory=list)
    labs: list[LabCriterion] = Field(default_factory=list)


class MatchRequest(BaseModel):
    trial_name: str = 'Untitled Trial'
    inclusion: TrialInclusion = Field(default_factory=TrialInclusion)
    exclusion: TrialExclusion = Field(default_factory=TrialExclusion)


class PatientMatch(BaseModel):
    patient_id: str
    age: int | None = None
    sex: str | None = None
    confidence: Literal['High', 'Moderate', 'Low', 'Excluded']
    matched_criteria: list[str] = Field(default_factory=list)
    exclusion_flags: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    recommendation: str
    patient_summary: dict[str, Any] = Field(default_factory=dict)


class MatchResponse(BaseModel):
    trial_name: str
    total_patients_screened: int
    matches: list[PatientMatch]
