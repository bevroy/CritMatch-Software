// If NEXT_PUBLIC_API_BASE_URL is explicitly set (even to ""), use it. An
// empty string means "same-origin" — used in production where Netlify
// proxies /api/* to the API so the session cookie stays first-party.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL !== undefined
    ? process.env.NEXT_PUBLIC_API_BASE_URL
    : "http://localhost:8000";

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
  myAccess?: "viewer" | "editor" | "owner" | "admin" | null;
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

/* ── FHIR connectivity ── */

export interface FhirPing {
  ok: boolean;
  configured: boolean;
  url?: string;
  status?: number;
  elapsedMs?: number;
  fhirVersion?: string;
  software?: string;
  publisher?: string;
  resourceTypes?: string[];
  resourceCount?: number;
  reason?: string;
}

export function fhirPing(): Promise<FhirPing> {
  return apiFetch("/api/fhir/ping");
}


/* ── Sharing / RBAC ── */

export type AccessLevel = "none" | "viewer" | "editor" | "owner" | "admin";

export interface CollaboratorOwner {
  userId: string;
  name: string;
  email: string | null;
}

export interface CollaboratorEntry {
  userId: string;
  role: "viewer" | "editor";
  name: string | null;
  email: string | null;
  createdAt: string;
}

export interface CollaboratorList {
  studyId: string;
  owner: CollaboratorOwner | null;
  myAccess: AccessLevel;
  items: CollaboratorEntry[];
}

export function fetchCollaborators(studyId: string): Promise<CollaboratorList> {
  return apiFetch(`/api/studies/${studyId}/collaborators`);
}

export function addCollaborator(
  studyId: string,
  userId: string,
  role: "viewer" | "editor",
): Promise<{ studyId: string; userId: string; role: string }> {
  return apiFetch(`/api/studies/${studyId}/collaborators`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}

export function removeCollaborator(
  studyId: string,
  userId: string,
): Promise<{ studyId: string; userId: string; removed: boolean }> {
  return apiFetch(`/api/studies/${studyId}/collaborators/${userId}`, {
    method: "DELETE",
  });
}

export function transferStudy(studyId: string, ownerUserId: string): Promise<Study> {
  return apiFetch(`/api/studies/${studyId}`, {
    method: "PATCH",
    body: JSON.stringify({ owner_user_id: ownerUserId }),
  });
}

export interface UserSearchResult {
  id: string;
  name: string;
  email: string | null;
  role: string;
}

export function searchUsers(q: string, limit = 20): Promise<UserSearchResult[]> {
  const qs = new URLSearchParams({ q, limit: String(limit) });
  return apiFetch(`/api/studies/_users/search?${qs.toString()}`);
}

/* ── Notifications ── */

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  readAt: string | null;
  createdAt: string;
  metadata: Record<string, unknown> | null;
}

export interface NotificationPage {
  items: NotificationItem[];
  total: number;
  unread: number;
  limit: number;
  offset: number;
}

export function fetchNotifications(opts?: { unreadOnly?: boolean; limit?: number; offset?: number }): Promise<NotificationPage> {
  const qs = new URLSearchParams();
  if (opts?.unreadOnly) qs.set("unread_only", "true");
  if (opts?.limit != null) qs.set("limit", String(opts.limit));
  if (opts?.offset != null) qs.set("offset", String(opts.offset));
  const tail = qs.toString();
  return apiFetch(`/api/notifications${tail ? `?${tail}` : ""}`);
}

export function fetchUnreadCount(): Promise<{ unread: number }> {
  return apiFetch("/api/notifications/unread-count");
}

export function markNotificationRead(id: string): Promise<{ ok: true }> {
  return apiFetch(`/api/notifications/${id}/read`, { method: "POST" });
}

export function markAllNotificationsRead(): Promise<{ ok: true; marked: number }> {
  return apiFetch("/api/notifications/read-all", { method: "POST" });
}

/* ── Feasibility ── */

export type FeasibilityRuleKind = "condition" | "observation" | "demographic";

export interface FeasibilityRule {
  id?: string;
  kind: FeasibilityRuleKind;
  label?: string;
  codes?: RuleCode[];
  field?: string;
  op?: string;
  value?: string | number;
}

export interface FeasibilityLogic {
  operator: "AND" | "OR";
  rules: FeasibilityRule[];
}

export interface FeasibilityQuestionInput {
  text: string;
  logic_json: FeasibilityLogic;
  position?: number;
}

export interface FeasibilityQuestion {
  id: string;
  position: number;
  text: string;
  logicJson: FeasibilityLogic;
}

export interface FeasibilityQuestionnaire {
  id: string;
  name: string;
  description: string | null;
  studyId: string | null;
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
  questions: FeasibilityQuestion[];
}

export interface FeasibilityQuestionnaireSummary {
  id: string;
  name: string;
  description: string | null;
  studyId: string | null;
  questionCount: number;
  updatedAt: string;
}

export interface FeasibilityResultItem {
  questionId: string;
  questionText: string;
  count: number;
  detail: Record<string, unknown> | null;
}

export interface FeasibilityRun {
  id: string;
  questionnaireId: string;
  status: string;
  totalPatients: number | null;
  executionMs: number | null;
  errorMessage: string | null;
  createdAt: string;
  results: FeasibilityResultItem[];
}

export function fetchFeasibilityQuestionnaires(
  studyId?: string,
): Promise<FeasibilityQuestionnaireSummary[]> {
  const qs = new URLSearchParams();
  if (studyId) qs.set("studyId", studyId);
  const tail = qs.toString();
  return apiFetch(`/api/feasibility/questionnaires${tail ? `?${tail}` : ""}`);
}

export function fetchFeasibilityQuestionnaire(id: string): Promise<FeasibilityQuestionnaire> {
  return apiFetch(`/api/feasibility/questionnaires/${id}`);
}

export function createFeasibilityQuestionnaire(payload: {
  name: string;
  description?: string;
  studyId?: string;
  questions: FeasibilityQuestionInput[];
}): Promise<FeasibilityQuestionnaire> {
  return apiFetch("/api/feasibility/questionnaires", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateFeasibilityQuestionnaire(
  id: string,
  payload: Partial<{
    name: string;
    description: string;
    studyId: string | null;
    questions: FeasibilityQuestionInput[];
  }>,
): Promise<FeasibilityQuestionnaire> {
  return apiFetch(`/api/feasibility/questionnaires/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteFeasibilityQuestionnaire(id: string): Promise<{ id: string; deleted: boolean }> {
  return apiFetch(`/api/feasibility/questionnaires/${id}`, { method: "DELETE" });
}

export function runFeasibility(id: string): Promise<FeasibilityRun> {
  return apiFetch(`/api/feasibility/questionnaires/${id}/run`, { method: "POST" });
}

export function fetchFeasibilityRun(runId: string): Promise<FeasibilityRun> {
  return apiFetch(`/api/feasibility/runs/${runId}`);
}

export function fetchFeasibilityRuns(questionnaireId: string, limit = 25): Promise<FeasibilityRun[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  return apiFetch(`/api/feasibility/questionnaires/${questionnaireId}/runs?${qs.toString()}`);
}

/* ── ROIE ── */

export interface RoieStatus {
  module: string;
  status: string;
  source: string;
  refreshedAt: string;
  note: string;
}

export interface RoieOpportunity {
  id: string;
  title: string;
  nctId: string;
  studyUrl: string;
  recruitingStatus: string;
  studyContactName: string | null;
  studyContactEmail: string | null;
  studyContactPhone: string | null;
  sponsor: string;
  phase: string;
  indication: string;
  region: string;
  siteMatchScore: number;
  enrollmentPotential: string;
  diversityPotential: string;
}

export function fetchRoieStatus(): Promise<RoieStatus> {
  return apiFetch("/api/roie/status");
}

export function fetchRoieOpportunities(limit = 6): Promise<RoieOpportunity[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  return apiFetch(`/api/roie/opportunities?${qs.toString()}`);
}

/* ── RWD & Readiness ── */

export interface ReadinessStatus {
  module: string;
  status: string;
  refreshedAt: string;
  note: string;
}

export interface ReadinessProfile {
  siteId: string;
  siteName: string;
  readinessScore: number;
  eligiblePopulationEstimate: number;
  feasibilityTier: string;
  primaryIndications: string[];
  careGaps: string[];
  sponsorReadySummary: string;
}

export function fetchReadinessStatus(): Promise<ReadinessStatus> {
  return apiFetch("/api/readiness/status");
}

export function fetchReadinessProfile(): Promise<ReadinessProfile> {
  return apiFetch("/api/readiness/profile");
}

/* ── Investigators (PI / Sub-I) ── */

export type InvestigatorRole = "principal_investigator" | "sub_investigator";

export interface Investigator {
  id: string;
  practitionerId: string;
  name: string | null;
  npi: string | null;
  role: InvestigatorRole;
  createdAt: string;
}

export interface InvestigatorList {
  studyId: string;
  items: Investigator[];
}

export function fetchInvestigators(studyId: string): Promise<InvestigatorList> {
  return apiFetch(`/api/studies/${studyId}/investigators`);
}

export function addInvestigator(
  studyId: string,
  payload: {
    practitioner_id: string;
    name?: string;
    npi?: string;
    role: InvestigatorRole;
  },
): Promise<Investigator> {
  return apiFetch(`/api/studies/${studyId}/investigators`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateInvestigator(
  studyId: string,
  investigatorId: string,
  payload: Partial<{ name: string; npi: string; role: InvestigatorRole }>,
): Promise<Investigator> {
  return apiFetch(`/api/studies/${studyId}/investigators/${investigatorId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function removeInvestigator(
  studyId: string,
  investigatorId: string,
): Promise<{ id: string; removed: boolean }> {
  return apiFetch(`/api/studies/${studyId}/investigators/${investigatorId}`, {
    method: "DELETE",
  });
}

/* ── EDC ── */

export type EdcItemType =
  | "string"
  | "text"
  | "integer"
  | "decimal"
  | "boolean"
  | "date"
  | "dateTime"
  | "time"
  | "choice"
  | "open-choice"
  | "quantity"
  | "attachment"
  | "group"
  | "display";

export interface EdcFhirMapping {
  resource: string;
  params?: Record<string, string>;
  extract?: string;
}

export interface EdcField {
  id: string;
  position: number;
  key: string;
  label: string;
  item_type: EdcItemType;
  required: boolean;
  options_json: Record<string, unknown> | null;
  fhir_mapping_json: EdcFhirMapping | null;
  validation_json: Record<string, unknown> | null;
}

export interface EdcFieldInput {
  key: string;
  label: string;
  item_type?: EdcItemType;
  position?: number;
  required?: boolean;
  options_json?: Record<string, unknown> | null;
  fhir_mapping_json?: EdcFhirMapping | null;
  validation_json?: Record<string, unknown> | null;
}

export interface EdcForm {
  id: string;
  study_id: string;
  name: string;
  description: string | null;
  version: number;
  status: "draft" | "active" | "locked";
  created_by: string | null;
  created_at: string;
  updated_at: string;
  fields: EdcField[];
}

export type EdcFormSummary = Omit<EdcForm, "fields" | "created_by" | "created_at"> & {
  fieldCount: number;
};

export type ParticipantStatus = "screening" | "enrolled" | "withdrawn" | "completed";

export interface Participant {
  id: string;
  study_id: string;
  patient_id: string;
  subject_id: string;
  status: ParticipantStatus;
  source: "manual" | "cohort_promotion";
  source_run_id: string | null;
  enrolled_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EntryFieldValue {
  field_id: string;
  value: unknown;
  source: "manual" | "fhir_pull";
  fhir_source_ref: string | null;
  updated_at: string | null;
}

export interface Signature {
  id: string;
  user_id: string;
  meaning: "author" | "reviewer" | "approver";
  signature_hash: string;
  signed_at: string;
}

export interface EdcEntry {
  id: string;
  form_id: string;
  participant_id: string;
  status: "in_progress" | "complete" | "locked";
  completed_at: string | null;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
  values: EntryFieldValue[];
  signatures: Signature[];
}

export interface EntryHistoryItem {
  fieldId: string;
  fieldKey: string;
  oldValue: unknown;
  newValue: unknown;
  oldSource: string | null;
  newSource: string | null;
  changedBy: string | null;
  reason: string | null;
  changedAt: string;
}

export interface FhirPullResult {
  field_id: string;
  field_key: string;
  value: unknown;
  source_ref: string | null;
  error: string | null;
}

/* Forms */
export function fetchEdcForms(studyId?: string): Promise<EdcFormSummary[]> {
  const qs = studyId ? `?studyId=${encodeURIComponent(studyId)}` : "";
  return apiFetch(`/api/edc/forms${qs}`);
}

export function fetchEdcForm(formId: string): Promise<EdcForm> {
  return apiFetch(`/api/edc/forms/${formId}`);
}

export function createEdcForm(payload: {
  study_id: string;
  name: string;
  description?: string;
  fields?: EdcFieldInput[];
}): Promise<EdcForm> {
  return apiFetch(`/api/edc/forms`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateEdcForm(
  formId: string,
  payload: Partial<{ name: string; description: string; status: "draft" | "active" | "locked"; fields: EdcFieldInput[] }>,
): Promise<EdcForm> {
  return apiFetch(`/api/edc/forms/${formId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteEdcForm(formId: string): Promise<{ id: string; deleted: boolean }> {
  return apiFetch(`/api/edc/forms/${formId}`, { method: "DELETE" });
}

/* Participants */
export function fetchParticipants(studyId: string): Promise<Participant[]> {
  return apiFetch(`/api/studies/${studyId}/participants`);
}

export function createParticipant(
  studyId: string,
  payload: { patient_id: string; subject_id: string; status?: ParticipantStatus; notes?: string },
): Promise<Participant> {
  return apiFetch(`/api/studies/${studyId}/participants`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function promoteParticipants(
  studyId: string,
  payload: { run_id: string; patient_ids: string[]; subject_id_prefix?: string },
): Promise<Participant[]> {
  return apiFetch(`/api/studies/${studyId}/participants/promote`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateParticipant(
  studyId: string,
  participantId: string,
  payload: Partial<{ subject_id: string; status: ParticipantStatus; notes: string }>,
): Promise<Participant> {
  return apiFetch(`/api/studies/${studyId}/participants/${participantId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteParticipant(
  studyId: string,
  participantId: string,
): Promise<{ id: string; deleted: boolean }> {
  return apiFetch(`/api/studies/${studyId}/participants/${participantId}`, { method: "DELETE" });
}

/* Entries */
export function fetchEdcEntries(formId: string): Promise<EdcEntry[]> {
  return apiFetch(`/api/edc/forms/${formId}/entries`);
}

export function createEdcEntry(formId: string, participantId: string): Promise<EdcEntry> {
  return apiFetch(`/api/edc/forms/${formId}/entries`, {
    method: "POST",
    body: JSON.stringify({ participant_id: participantId }),
  });
}

export function fetchEdcEntry(entryId: string): Promise<EdcEntry> {
  return apiFetch(`/api/edc/entries/${entryId}`);
}

export function updateEdcEntry(
  entryId: string,
  payload: {
    values?: Array<{ field_id: string; value: unknown; source?: "manual" | "fhir_pull"; fhir_source_ref?: string | null; reason_for_change?: string }>;
    status?: "in_progress" | "complete" | "locked";
  },
): Promise<EdcEntry> {
  return apiFetch(`/api/edc/entries/${entryId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function pullEdcEntry(entryId: string): Promise<FhirPullResult[]> {
  return apiFetch(`/api/edc/entries/${entryId}/pull`, { method: "POST" });
}

export function signEdcEntry(
  entryId: string,
  payload: { meaning?: "author" | "reviewer" | "approver"; confirmation?: string } = {},
): Promise<Signature> {
  return apiFetch(`/api/edc/entries/${entryId}/sign`, { method: "POST", body: JSON.stringify(payload) });
}

export function fetchEdcEntryHistory(entryId: string): Promise<EntryHistoryItem[]> {
  return apiFetch(`/api/edc/entries/${entryId}/history`);
}

// ===========================================================================
// CTFMS (Clinical Trial Financial Management) types & helpers
// ===========================================================================

export type CtfmsBudgetItemType =
  | "per_visit"
  | "per_procedure"
  | "fixed_milestone"
  | "passthrough"
  | "overhead"
  | "patient_stipend";

export type CtfmsBudgetStatus = "draft" | "active" | "archived";
export type CtfmsAccrualStatus = "accrued" | "invoiced" | "void";
export type CtfmsInvoiceStatus = "draft" | "sent" | "partial" | "paid" | "void";
export type CtfmsStipendStatus = "pending" | "paid" | "void";

export type CtfmsBudgetItem = {
  id: string;
  budget_id: string;
  code: string | null;
  name: string;
  description: string | null;
  item_type: CtfmsBudgetItemType;
  unit_price: number;
  currency: string;
  edc_form_id: string | null;
  edc_field_id: string | null;
  auto_accrue: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type CtfmsBudgetItemInput = {
  code?: string | null;
  name: string;
  description?: string | null;
  item_type?: CtfmsBudgetItemType;
  unit_price: number;
  currency: string;
  edc_form_id?: string | null;
  edc_field_id?: string | null;
  auto_accrue?: boolean;
  active?: boolean;
};

export type CtfmsBudget = {
  id: string;
  study_id: string;
  name: string;
  sponsor: string | null;
  contract_number: string | null;
  currency: string;
  version: number;
  status: CtfmsBudgetStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: CtfmsBudgetItem[];
};

export type CtfmsBudgetSummary = {
  id: string;
  study_id: string;
  name: string;
  currency: string;
  version: number;
  status: CtfmsBudgetStatus;
  itemCount: number;
  updated_at: string;
};

export type CtfmsAccrual = {
  id: string;
  study_id: string;
  budget_id: string;
  budget_item_id: string;
  participant_id: string | null;
  entry_id: string | null;
  quantity: number;
  unit_price: number;
  amount: number;
  currency: string;
  status: CtfmsAccrualStatus;
  invoice_line_id: string | null;
  notes: string | null;
  accrued_at: string;
};

export type CtfmsInvoiceLine = {
  id: string;
  accrual_id: string | null;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  currency: string;
};

export type CtfmsInvoice = {
  id: string;
  study_id: string;
  budget_id: string | null;
  number: string;
  currency: string;
  subtotal: number;
  total: number;
  amount_paid: number;
  status: CtfmsInvoiceStatus;
  issued_at: string;
  sent_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  lines: CtfmsInvoiceLine[];
};

export type CtfmsPayment = {
  id: string;
  study_id: string;
  invoice_id: string | null;
  amount: number;
  currency: string;
  paid_at: string;
  method: string | null;
  reference: string | null;
  notes: string | null;
  created_at: string;
};

export type CtfmsStipend = {
  id: string;
  study_id: string;
  participant_id: string;
  budget_item_id: string | null;
  entry_id: string | null;
  amount: number;
  currency: string;
  status: CtfmsStipendStatus;
  paid_at: string | null;
  method: string | null;
  reference: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CtfmsFinanceSummary = {
  accruedOpen: number;
  accruedInvoiced: number;
  invoiceTotal: number;
  paid: number;
  outstanding: number;
  stipendsPending: number;
  stipendsPaid: number;
};

export function formatMoney(minor: number, currency = "USD"): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(minor / 100);
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }
}

// --- Budgets -------------------------------------------------------------

export function fetchCtfmsBudgets(studyId: string): Promise<CtfmsBudgetSummary[]> {
  return apiFetch(`/api/ctfms/budgets?studyId=${encodeURIComponent(studyId)}`);
}

export function fetchCtfmsBudget(id: string): Promise<CtfmsBudget> {
  return apiFetch(`/api/ctfms/budgets/${id}`);
}

export function createCtfmsBudget(payload: {
  study_id: string;
  name: string;
  sponsor?: string;
  contract_number?: string;
  currency?: string;
  notes?: string;
  items?: CtfmsBudgetItemInput[];
}): Promise<CtfmsBudget> {
  return apiFetch(`/api/ctfms/budgets`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateCtfmsBudget(
  id: string,
  payload: Partial<{
    name: string;
    sponsor: string;
    contract_number: string;
    currency: string;
    notes: string;
    status: CtfmsBudgetStatus;
    items: CtfmsBudgetItemInput[];
  }>,
): Promise<CtfmsBudget> {
  return apiFetch(`/api/ctfms/budgets/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteCtfmsBudget(id: string): Promise<{ id: string; deleted: boolean }> {
  return apiFetch(`/api/ctfms/budgets/${id}`, { method: "DELETE" });
}

// --- Accruals -------------------------------------------------------------

export function fetchCtfmsAccruals(studyId: string, status?: CtfmsAccrualStatus): Promise<CtfmsAccrual[]> {
  const qs = status ? `&status=${status}` : "";
  return apiFetch(`/api/ctfms/accruals?studyId=${encodeURIComponent(studyId)}${qs}`);
}

export function createCtfmsAccrual(
  budgetId: string,
  payload: { budget_item_id: string; participant_id?: string; quantity?: number; unit_price?: number; notes?: string },
): Promise<CtfmsAccrual> {
  return apiFetch(`/api/ctfms/budgets/${budgetId}/accruals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCtfmsAccrual(
  id: string,
  payload: { status?: CtfmsAccrualStatus; notes?: string },
): Promise<CtfmsAccrual> {
  return apiFetch(`/api/ctfms/accruals/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

// --- Invoices -------------------------------------------------------------

export function fetchCtfmsInvoices(studyId: string): Promise<CtfmsInvoice[]> {
  return apiFetch(`/api/ctfms/invoices?studyId=${encodeURIComponent(studyId)}`);
}

export function fetchCtfmsInvoice(id: string): Promise<CtfmsInvoice> {
  return apiFetch(`/api/ctfms/invoices/${id}`);
}

export function createCtfmsInvoice(
  studyId: string,
  payload: { accrual_ids: string[]; notes?: string },
): Promise<CtfmsInvoice> {
  return apiFetch(`/api/ctfms/studies/${studyId}/invoices`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCtfmsInvoice(
  id: string,
  payload: { status?: CtfmsInvoiceStatus; notes?: string },
): Promise<CtfmsInvoice> {
  return apiFetch(`/api/ctfms/invoices/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

// --- Payments -------------------------------------------------------------

export function fetchCtfmsPayments(studyId: string): Promise<CtfmsPayment[]> {
  return apiFetch(`/api/ctfms/payments?studyId=${encodeURIComponent(studyId)}`);
}

export function recordCtfmsPayment(
  studyId: string,
  payload: { invoice_id?: string; amount: number; currency: string; paid_at?: string; method?: string; reference?: string; notes?: string },
): Promise<CtfmsPayment> {
  return apiFetch(`/api/ctfms/studies/${studyId}/payments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- Stipends -------------------------------------------------------------

export function fetchCtfmsStipends(studyId: string, status?: CtfmsStipendStatus): Promise<CtfmsStipend[]> {
  const qs = status ? `&status=${status}` : "";
  return apiFetch(`/api/ctfms/stipends?studyId=${encodeURIComponent(studyId)}${qs}`);
}

export function createCtfmsStipend(
  studyId: string,
  payload: { participant_id: string; budget_item_id?: string; amount: number; currency: string; notes?: string },
): Promise<CtfmsStipend> {
  return apiFetch(`/api/ctfms/studies/${studyId}/stipends`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCtfmsStipend(
  id: string,
  payload: { status?: CtfmsStipendStatus; method?: string; reference?: string; notes?: string },
): Promise<CtfmsStipend> {
  return apiFetch(`/api/ctfms/stipends/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

// --- Summary --------------------------------------------------------------

export function fetchCtfmsFinanceSummary(studyId: string): Promise<CtfmsFinanceSummary> {
  return apiFetch(`/api/ctfms/studies/${studyId}/summary`);
}
