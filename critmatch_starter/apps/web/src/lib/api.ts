const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* noop */ }
    throw new ApiError(res.status, `API ${res.status}: ${res.statusText}`, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/* ── Auth / SMART ── */

export interface SessionInfo {
  user_id: string;
  role: string;
  patient_context: string | null;
  signature_verified: boolean;
}

export function getMe(): Promise<SessionInfo> {
  return apiFetch("/api/auth/me");
}

export function logout(): Promise<void> {
  return apiFetch("/api/auth/logout", { method: "POST" });
}

export function smartAuthorize(
  iss: string,
  launch?: string | null,
): Promise<{ authorize_url: string; state: string }> {
  return apiFetch("/api/auth/smart/authorize", {
    method: "POST",
    body: JSON.stringify({ iss, launch }),
  });
}

export function smartCallback(code: string, state: string): Promise<SessionInfo> {
  return apiFetch("/api/auth/smart/callback", {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
}

export function devLoginEnabled(): Promise<{ enabled: boolean }> {
  return apiFetch("/api/auth/dev-login/enabled");
}

export function devLogin(role: "research_user" | "admin" | "auditor" = "research_user", name = "Dev User"): Promise<SessionInfo> {
  return apiFetch("/api/auth/dev-login", {
    method: "POST",
    body: JSON.stringify({ role, name }),
  });
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

export function fetchStudy(studyId: string): Promise<Study> {
  return apiFetch(`/api/studies/${studyId}`);
}

export function createStudy(name: string, description?: string): Promise<Study> {
  return apiFetch("/api/studies", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

/* ── Criteria Sets ── */

export interface RuleCode {
  system: string;
  code: string;
  display?: string;
}

export interface CriteriaRule {
  id: string;
  kind: "condition" | "observation" | "demographic";
  label?: string;
  codes?: RuleCode[];
  field?: string;
  op?: string;
  value?: string | number;
}

export interface CriteriaLogic {
  operator: "AND" | "OR";
  rules: CriteriaRule[];
}

export interface CriteriaSetCreated {
  id?: string;
  study_id: string;
  saved: boolean;
  version: number;
}

export function createCriteriaSet(
  studyId: string,
  version: number,
  logicJson: CriteriaLogic,
): Promise<CriteriaSetCreated> {
  return apiFetch(`/api/studies/${studyId}/criteria-sets`, {
    method: "POST",
    body: JSON.stringify({ version, logic_json: logicJson }),
  });
}

export interface CriteriaSetSummary {
  id: string;
  studyId: string;
  version: number;
  logicJson: CriteriaLogic;
  createdAt: string;
}

export function fetchCriteriaSets(studyId: string): Promise<CriteriaSetSummary[]> {
  return apiFetch(`/api/studies/${studyId}/criteria-sets`);
}

export interface RunSummary {
  id: string;
  criteriaSetId: string;
  status: string;
  resultCount: number | null;
  executionMs: number | null;
  createdAt: string;
}

export interface StudyRunsPage {
  studyId: string;
  total: number;
  limit: number;
  offset: number;
  items: RunSummary[];
}

export function fetchStudyRuns(
  studyId: string,
  limit = 50,
  offset = 0,
): Promise<StudyRunsPage> {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch(`/api/studies/${studyId}/runs?${qs.toString()}`);
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

/* ── Query / Runs ── */

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

export interface RunDetail {
  id: string;
  studyId: string;
  criteriaSetId: string;
  status: string;
  resultCount: number | null;
  executionMs: number | null;
  createdAt: string;
}

export function fetchRun(runId: string): Promise<RunDetail> {
  return apiFetch(`/api/runs/${runId}`);
}

export interface RunResultRow {
  patientId: string;
  mrnHash: string | null;
  matchedRules: string[];
  primaryMatchReason: string | null;
}

export interface RunResultsPage {
  runId: string;
  total: number;
  limit: number;
  offset: number;
  items: RunResultRow[];
}

export function fetchRunResults(
  runId: string,
  limit = 100,
  offset = 0,
): Promise<RunResultsPage> {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch(`/api/runs/${runId}/results?${qs.toString()}`);
}

export interface ExportLink {
  downloadPath: string;
  expiresAt: number;
}

export function createExportLink(runId: string, ttlSeconds = 300): Promise<ExportLink> {
  const qs = new URLSearchParams({ ttl_seconds: String(ttlSeconds) });
  return apiFetch(`/api/runs/${runId}/export?${qs.toString()}`, { method: "POST" });
}

export function exportDownloadUrl(downloadPath: string): string {
  return `${API_BASE}${downloadPath}`;
}

export function cancelRun(runId: string): Promise<{ runId: string; status: string }> {
  return apiFetch(`/api/runs/${runId}/cancel`, { method: "POST" });
}

export interface RetryRunResult {
  runId: string;
  studyId: string;
  criteriaSetId: string;
  status: string;
  retriedFrom: string;
}

export function retryRun(runId: string): Promise<RetryRunResult> {
  return apiFetch(`/api/runs/${runId}/retry`, { method: "POST" });
}

export interface RunDiff {
  baseRunId: string;
  compareRunId: string;
  baseTotal: number;
  compareTotal: number;
  added: string[];
  removed: string[];
  addedCount: number;
  removedCount: number;
  unchangedCount: number;
  sample: number;
}

export function diffRuns(baseRunId: string, compareRunId: string, sample = 50): Promise<RunDiff> {
  const qs = new URLSearchParams({ sample: String(sample) });
  return apiFetch(`/api/runs/${baseRunId}/diff/${compareRunId}?${qs.toString()}`);
}

/* ── Audit ── */

export interface AuditEvent {
  userId: string | null;
  action: string;
  objectType: string;
  objectId: string | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

export interface AuditPage {
  total: number;
  limit: number;
  offset: number;
  items: AuditEvent[];
}

export interface AuditFilters {
  action?: string;
  objectType?: string;
  objectId?: string;
  userId?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export function fetchAuditEvents(filters: AuditFilters = {}): Promise<AuditPage> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "" && v !== null) qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/api/audit${suffix}`);
}

