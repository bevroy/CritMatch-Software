import json
from pathlib import Path
from backend.schemas.match import MatchRequest, MatchResponse, PatientMatch, LabCriterion
from backend.services.terminology import normalize_terms

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'sample_patients.json'


def _load_patients() -> list[dict]:
    with DATA_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)


def _lab_matches(patient_labs: dict, criterion: LabCriterion) -> bool | None:
    # returns None when lab is missing
    lab_name = criterion.name
    if lab_name not in patient_labs:
        # try case-insensitive matching
        found_key = next((k for k in patient_labs if k.lower() == lab_name.lower()), None)
        if not found_key:
            return None
        lab_name = found_key
    value = patient_labs.get(lab_name)
    if value is None:
        return None
    if criterion.operator in ('=', '=='):
        return float(value) == criterion.value
    if criterion.operator == '>':
        return float(value) > criterion.value
    if criterion.operator == '>=':
        return float(value) >= criterion.value
    if criterion.operator == '<':
        return float(value) < criterion.value
    if criterion.operator == '<=':
        return float(value) <= criterion.value
    return False


def evaluate_patient(patient: dict, request: MatchRequest) -> PatientMatch:
    matched: list[str] = []
    exclusions: list[str] = []
    missing: list[str] = []

    patient_diagnoses = normalize_terms(patient.get('diagnoses', []))
    patient_meds = normalize_terms(patient.get('medications', []))
    patient_conditions = normalize_terms(patient.get('conditions', []))
    patient_icd10 = set(patient.get('icd10', []))
    patient_labs = patient.get('labs', {})

    inclusion = request.inclusion
    exclusion = request.exclusion

    # Inclusion: age
    age = patient.get('age')
    if inclusion.age_min is not None or inclusion.age_max is not None:
        if age is None:
            missing.append('age')
        elif (inclusion.age_min is None or age >= inclusion.age_min) and (inclusion.age_max is None or age <= inclusion.age_max):
            matched.append('age range')

    # Inclusion: diagnoses
    requested_dx = normalize_terms(inclusion.diagnoses)
    if requested_dx:
        found = requested_dx.intersection(patient_diagnoses)
        if found:
            matched.extend([f'diagnosis: {dx}' for dx in sorted(found)])
        else:
            missing.append('required diagnosis not found')

    # Inclusion: meds
    requested_meds = normalize_terms(inclusion.medications)
    if requested_meds:
        found = requested_meds.intersection(patient_meds)
        if found:
            matched.extend([f'medication: {med}' for med in sorted(found)])
        else:
            missing.append('required medication not found')

    # Inclusion: ICD-10
    if inclusion.icd10:
        found = set(inclusion.icd10).intersection(patient_icd10)
        if found:
            matched.extend([f'ICD-10: {code}' for code in sorted(found)])
        else:
            missing.append('required ICD-10 code not found')

    # Inclusion: labs
    for lab in inclusion.labs:
        lab_result = _lab_matches(patient_labs, lab)
        if lab_result is True:
            matched.append(f'lab: {lab.name} {lab.operator} {lab.value}')
        elif lab_result is None:
            missing.append(f'missing lab: {lab.name}')
        else:
            missing.append(f'lab criterion not met: {lab.name}')

    # Exclusion checks
    excluded_dx = normalize_terms(exclusion.diagnoses)
    for dx in sorted(excluded_dx.intersection(patient_diagnoses)):
        exclusions.append(f'excluded diagnosis: {dx}')

    excluded_meds = normalize_terms(exclusion.medications)
    for med in sorted(excluded_meds.intersection(patient_meds)):
        exclusions.append(f'excluded medication: {med}')

    excluded_conditions = normalize_terms(exclusion.conditions)
    for cond in sorted(excluded_conditions.intersection(patient_conditions)):
        exclusions.append(f'excluded condition: {cond}')

    for code in sorted(set(exclusion.icd10).intersection(patient_icd10)):
        exclusions.append(f'excluded ICD-10: {code}')

    for lab in exclusion.labs:
        lab_result = _lab_matches(patient_labs, lab)
        if lab_result is True:
            exclusions.append(f'excluded lab: {lab.name} {lab.operator} {lab.value}')

    if exclusions:
        confidence = 'Excluded'
        recommendation = 'Do not advance without investigator review; exclusion criteria detected.'
    elif matched and not missing:
        confidence = 'High'
        recommendation = 'Candidate appears eligible for coordinator review.'
    elif matched and missing:
        confidence = 'Moderate'
        recommendation = 'Potential candidate; verify missing or unresolved data.'
    else:
        confidence = 'Low'
        recommendation = 'Weak match; not recommended for immediate screening.'

    return PatientMatch(
        patient_id=patient.get('patient_id', 'UNKNOWN'),
        age=patient.get('age'),
        sex=patient.get('sex'),
        confidence=confidence,
        matched_criteria=matched,
        exclusion_flags=exclusions,
        missing_data=missing,
        recommendation=recommendation,
        patient_summary={
            'diagnoses': patient.get('diagnoses', []),
            'icd10': patient.get('icd10', []),
            'medications': patient.get('medications', []),
            'labs': patient_labs,
        },
    )


def match_patients(request: MatchRequest) -> MatchResponse:
    patients = _load_patients()
    matches = [evaluate_patient(patient, request) for patient in patients]
    # surface the most relevant first
    rank = {'High': 0, 'Moderate': 1, 'Low': 2, 'Excluded': 3}
    matches.sort(key=lambda m: (rank[m.confidence], m.patient_id))
    return MatchResponse(
        trial_name=request.trial_name,
        total_patients_screened=len(patients),
        matches=matches,
    )
