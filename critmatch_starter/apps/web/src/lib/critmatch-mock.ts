/**
 * Client-side CritMatch matching engine + bundled sample patients.
 *
 * Mirrors critmatch_mvp/backend/services/matching_engine.py so the public
 * /demo route works without any backend (Netlify-only deploy is sufficient).
 */
import type { LabCriterion, MatchRequest, MatchResponse, PatientMatch } from "./critmatch-types";

type Patient = {
  patient_id: string;
  age?: number;
  sex?: string;
  diagnoses: string[];
  icd10: string[];
  medications: string[];
  conditions: string[];
  labs: Record<string, number>;
};

const SYNONYMS: Record<string, string> = {
  mi: "myocardial infarction",
  "heart attack": "myocardial infarction",
  hf: "heart failure",
  chf: "heart failure",
  t2dm: "type 2 diabetes",
  "diabetes mellitus type 2": "type 2 diabetes",
  "breast ca": "breast cancer",
  cva: "stroke",
  aki: "acute kidney injury",
  ckd: "chronic kidney disease",
  mci: "mild cognitive impairment",
};

function normalizeTerm(t: string): string {
  const v = (t || "").trim().toLowerCase();
  return SYNONYMS[v] ?? v;
}

function normalizeTerms(terms: string[]): Set<string> {
  return new Set(terms.filter(Boolean).map(normalizeTerm));
}

function intersection<T>(a: Set<T>, b: Set<T>): T[] {
  return Array.from(a).filter((x) => b.has(x)).sort();
}

function labMatches(patientLabs: Record<string, number>, c: LabCriterion): boolean | null {
  let key: string | undefined = c.name;
  if (!(key in patientLabs)) {
    key = Object.keys(patientLabs).find((k) => k.toLowerCase() === c.name.toLowerCase());
    if (!key) return null;
  }
  const value = patientLabs[key];
  if (value === undefined || value === null) return null;
  switch (c.operator) {
    case "=":
    case "==":
      return value === c.value;
    case ">":
      return value > c.value;
    case ">=":
      return value >= c.value;
    case "<":
      return value < c.value;
    case "<=":
      return value <= c.value;
  }
  return false;
}

export const SAMPLE_PATIENTS: Patient[] = [
  { patient_id: "CM-001", age: 64, sex: "F", diagnoses: ["heart failure", "type 2 diabetes"], icd10: ["I50.9", "E11.9"], medications: ["metformin", "lisinopril"], conditions: [], labs: { HbA1c: 8.4, eGFR: 62 } },
  { patient_id: "CM-002", age: 72, sex: "M", diagnoses: ["heart failure", "stroke"], icd10: ["I50.9", "I63.9"], medications: ["warfarin", "atorvastatin"], conditions: [], labs: { HbA1c: 7.1, eGFR: 54 } },
  { patient_id: "CM-003", age: 55, sex: "F", diagnoses: ["breast cancer"], icd10: ["C50.919"], medications: ["letrozole"], conditions: [], labs: { eGFR: 88 } },
  { patient_id: "CM-004", age: 49, sex: "F", diagnoses: ["breast cancer", "chronic kidney disease"], icd10: ["C50.919", "N18.9"], medications: ["tamoxifen"], conditions: [], labs: { eGFR: 28 } },
  { patient_id: "CM-005", age: 78, sex: "M", diagnoses: ["mild cognitive impairment"], icd10: ["G31.84"], medications: ["donepezil"], conditions: [], labs: { B12: 410, TSH: 2.1 } },
  { patient_id: "CM-006", age: 34, sex: "F", diagnoses: ["type 2 diabetes"], icd10: ["E11.9"], medications: ["insulin"], conditions: ["pregnancy"], labs: { HbA1c: 9.2, eGFR: 95 } },
  { patient_id: "CM-007", age: 61, sex: "M", diagnoses: ["myocardial infarction", "heart failure"], icd10: ["I21.9", "I50.9"], medications: ["aspirin", "metoprolol"], conditions: [], labs: { HbA1c: 6.3, eGFR: 70 } },
  { patient_id: "CM-008", age: 69, sex: "F", diagnoses: ["Alzheimer disease"], icd10: ["G30.9"], medications: [], conditions: [], labs: { B12: 310, TSH: 3.0 } },
];

function evaluatePatient(patient: Patient, req: MatchRequest): PatientMatch {
  const matched: string[] = [];
  const exclusions: string[] = [];
  const missing: string[] = [];

  const pDx = normalizeTerms(patient.diagnoses ?? []);
  const pMeds = normalizeTerms(patient.medications ?? []);
  const pConds = normalizeTerms(patient.conditions ?? []);
  const pIcd = new Set(patient.icd10 ?? []);
  const pLabs = patient.labs ?? {};

  const inc = req.inclusion;
  const exc = req.exclusion;

  // Age
  const age = patient.age;
  if (inc.age_min !== undefined || inc.age_max !== undefined) {
    if (age === undefined) {
      missing.push("age");
    } else if ((inc.age_min === undefined || age >= inc.age_min) && (inc.age_max === undefined || age <= inc.age_max)) {
      matched.push("age range");
    }
  }

  // Inclusion: diagnoses
  const reqDx = normalizeTerms(inc.diagnoses);
  if (reqDx.size) {
    const found = intersection(reqDx, pDx);
    if (found.length) found.forEach((d) => matched.push(`diagnosis: ${d}`));
    else missing.push("required diagnosis not found");
  }

  // Inclusion: meds
  const reqMeds = normalizeTerms(inc.medications);
  if (reqMeds.size) {
    const found = intersection(reqMeds, pMeds);
    if (found.length) found.forEach((m) => matched.push(`medication: ${m}`));
    else missing.push("required medication not found");
  }

  // Inclusion: ICD-10
  if (inc.icd10.length) {
    const found = intersection(new Set(inc.icd10), pIcd);
    if (found.length) found.forEach((c) => matched.push(`ICD-10: ${c}`));
    else missing.push("required ICD-10 code not found");
  }

  // Inclusion: labs
  for (const lab of inc.labs) {
    const r = labMatches(pLabs, lab);
    if (r === true) matched.push(`lab: ${lab.name} ${lab.operator} ${lab.value}`);
    else if (r === null) missing.push(`missing lab: ${lab.name}`);
    else missing.push(`lab criterion not met: ${lab.name}`);
  }

  // Exclusion checks
  intersection(normalizeTerms(exc.diagnoses), pDx).forEach((d) => exclusions.push(`excluded diagnosis: ${d}`));
  intersection(normalizeTerms(exc.medications), pMeds).forEach((m) => exclusions.push(`excluded medication: ${m}`));
  intersection(normalizeTerms(exc.conditions), pConds).forEach((c) => exclusions.push(`excluded condition: ${c}`));
  intersection(new Set(exc.icd10), pIcd).forEach((c) => exclusions.push(`excluded ICD-10: ${c}`));
  for (const lab of exc.labs) {
    if (labMatches(pLabs, lab) === true) exclusions.push(`excluded lab: ${lab.name} ${lab.operator} ${lab.value}`);
  }

  let confidence: PatientMatch["confidence"];
  let recommendation: string;
  if (exclusions.length) {
    confidence = "Excluded";
    recommendation = "Do not advance without investigator review; exclusion criteria detected.";
  } else if (matched.length && !missing.length) {
    confidence = "High";
    recommendation = "Candidate appears eligible for coordinator review.";
  } else if (matched.length && missing.length) {
    confidence = "Moderate";
    recommendation = "Potential candidate; verify missing or unresolved data.";
  } else {
    confidence = "Low";
    recommendation = "Weak match; not recommended for immediate screening.";
  }

  return {
    patient_id: patient.patient_id,
    age: patient.age,
    sex: patient.sex,
    confidence,
    matched_criteria: matched,
    exclusion_flags: exclusions,
    missing_data: missing,
    recommendation,
    patient_summary: {
      diagnoses: patient.diagnoses,
      icd10: patient.icd10,
      medications: patient.medications,
      labs: pLabs,
    },
  };
}

export function runMatchLocal(req: MatchRequest): MatchResponse {
  const matches = SAMPLE_PATIENTS.map((p) => evaluatePatient(p, req));
  const rank: Record<PatientMatch["confidence"], number> = { High: 0, Moderate: 1, Low: 2, Excluded: 3 };
  matches.sort((a, b) => rank[a.confidence] - rank[b.confidence] || a.patient_id.localeCompare(b.patient_id));
  return {
    trial_name: req.trial_name,
    total_patients_screened: SAMPLE_PATIENTS.length,
    matches,
  };
}

/** One-click trial presets to showcase how criteria affect matches. */
export type DemoPreset = {
  id: string;
  label: string;
  description: string;
  request: MatchRequest;
};

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: "hf-dm",
    label: "Heart Failure + Diabetes",
    description: "Adults 18–75 with heart failure and uncontrolled HbA1c, excluding stroke history and warfarin.",
    request: {
      trial_name: "Heart Failure + Diabetes Trial",
      inclusion: {
        age_min: 18,
        age_max: 75,
        diagnoses: ["heart failure"],
        medications: [],
        icd10: [],
        labs: [{ name: "HbA1c", operator: ">", value: 8 }],
      },
      exclusion: {
        diagnoses: ["stroke"],
        medications: ["warfarin"],
        conditions: ["pregnancy"],
        icd10: [],
        labs: [{ name: "eGFR", operator: "<", value: 30 }],
      },
    },
  },
  {
    id: "oncology",
    label: "Oncology — Breast Cancer",
    description: "Women 40–80 with breast cancer; exclude advanced renal impairment.",
    request: {
      trial_name: "Breast Cancer Adjuvant Therapy",
      inclusion: {
        age_min: 40,
        age_max: 80,
        diagnoses: ["breast cancer"],
        medications: [],
        icd10: [],
        labs: [],
      },
      exclusion: {
        diagnoses: [],
        medications: [],
        conditions: [],
        icd10: [],
        labs: [{ name: "eGFR", operator: "<", value: 45 }],
      },
    },
  },
  {
    id: "memory",
    label: "Memory & Cognition",
    description: "Patients 60+ with MCI or Alzheimer disease for a memory intervention study.",
    request: {
      trial_name: "Memory Intervention Study",
      inclusion: {
        age_min: 60,
        age_max: 95,
        diagnoses: ["mild cognitive impairment", "Alzheimer disease"],
        medications: [],
        icd10: [],
        labs: [],
      },
      exclusion: {
        diagnoses: [],
        medications: [],
        conditions: [],
        icd10: [],
        labs: [],
      },
    },
  },
];
