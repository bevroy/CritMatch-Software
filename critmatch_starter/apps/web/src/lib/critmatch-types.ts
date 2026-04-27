export type LabCriterion = {
  name: string;
  operator: '>' | '>=' | '<' | '<=' | '=' | '==';
  value: number;
};

export type MatchRequest = {
  trial_name: string;
  inclusion: {
    age_min?: number;
    age_max?: number;
    diagnoses: string[];
    medications: string[];
    icd10: string[];
    labs: LabCriterion[];
  };
  exclusion: {
    diagnoses: string[];
    medications: string[];
    conditions: string[];
    icd10: string[];
    labs: LabCriterion[];
  };
};

export type PatientMatch = {
  patient_id: string;
  age?: number;
  sex?: string;
  confidence: 'High' | 'Moderate' | 'Low' | 'Excluded';
  matched_criteria: string[];
  exclusion_flags: string[];
  missing_data: string[];
  recommendation: string;
  patient_summary: Record<string, unknown>;
};

export type MatchResponse = {
  trial_name: string;
  total_patients_screened: number;
  matches: PatientMatch[];
};
