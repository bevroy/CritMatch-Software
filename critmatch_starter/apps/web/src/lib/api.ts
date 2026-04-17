const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/* ── Studies ── */

export interface Study {
  id: string;
  name: string;
  description: string | null;
  status: string;
}

export function fetchStudies(): Promise<Study[]> {
  return apiFetch("/api/studies");
}

export function createStudy(name: string, description?: string): Promise<Study> {
  return apiFetch("/api/studies", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

/* ── Criteria Sets ── */

export function createCriteriaSet(
  studyId: string,
  version: number,
  logicJson: unknown,
): Promise<{ study_id: string; saved: boolean; version: number }> {
  return apiFetch(`/api/studies/${studyId}/criteria-sets`, {
    method: "POST",
    body: JSON.stringify({ version, logic_json: logicJson }),
  });
}

/* ── Terminology ── */

export interface Expansion {
  type: string;
  display: string;
  system?: string;
  code?: string;
}

export interface TerminologyResult {
  normalizedTerm: string;
  expansions: Expansion[];
}

export function expandTerm(text: string): Promise<TerminologyResult> {
  return apiFetch("/api/terminology/expand", {
    method: "POST",
    body: JSON.stringify({
      text,
      domains: ["Diagnosis"],
      includeSynonyms: true,
      includeMappedCodes: true,
      targetCodeSystems: ["ICD10CM", "SNOMEDCT"],
    }),
  });
}

/* ── Query ── */

export interface QueryRunResult {
  runId: string;
  studyId: string;
  criteriaSetId: string;
  status: string;
}

export function runQuery(studyId: string, criteriaSetId: string): Promise<QueryRunResult> {
  return apiFetch("/api/query/run", {
    method: "POST",
    body: JSON.stringify({ studyId, criteriaSetId }),
  });
}

/* ── Audit ── */

export interface AuditEvent {
  action: string;
  objectType: string;
  objectId: string;
  createdAt: string;
}

export function fetchAuditEvents(): Promise<AuditEvent[]> {
  return apiFetch("/api/audit");
}
