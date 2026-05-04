"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  createParticipant,
  deleteParticipant,
  fetchParticipants,
  fetchStudyRuns,
  promoteParticipants,
  type Participant,
  type RunSummary,
} from "../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

export default function ParticipantsPanel({
  studyId,
  canManage,
}: {
  studyId: string;
  canManage: boolean;
}) {
  const [items, setItems] = useState<Participant[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showAdd, setShowAdd] = useState(false);
  const [patientId, setPatientId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [adding, setAdding] = useState(false);

  const [showPromote, setShowPromote] = useState(false);
  const [runId, setRunId] = useState("");
  const [prefix, setPrefix] = useState("S");
  const [patientList, setPatientList] = useState("");
  const [promoting, setPromoting] = useState(false);

  async function load() {
    setError(null);
    try {
      const [ps, runPage] = await Promise.all([
        fetchParticipants(studyId),
        fetchStudyRuns(studyId, 25, 0).catch(() => ({ items: [] as RunSummary[] })),
      ]);
      setItems(ps);
      setRuns(runPage.items.filter((r) => r.status === "completed"));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [studyId]);

  async function handleAdd() {
    if (!patientId.trim() || !subjectId.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await createParticipant(studyId, {
        patient_id: patientId.trim(),
        subject_id: subjectId.trim(),
        status: "enrolled",
      });
      setPatientId("");
      setSubjectId("");
      setShowAdd(false);
      await load();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setAdding(false);
    }
  }

  async function handlePromote() {
    if (!runId) return;
    const ids = patientList.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    if (ids.length === 0) return;
    setPromoting(true);
    setError(null);
    try {
      await promoteParticipants(studyId, {
        run_id: runId,
        patient_ids: ids,
        subject_id_prefix: prefix.trim() || "S",
      });
      setPatientList("");
      setShowPromote(false);
      await load();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setPromoting(false);
    }
  }

  async function handleDelete(p: Participant) {
    if (!confirm(`Remove ${p.subject_id}?`)) return;
    try {
      await deleteParticipant(studyId, p.id);
      await load();
    } catch (e) {
      setError(describeError(e));
    }
  }

  return (
    <section className="card" style={{ marginTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>Participants ({items.length})</h2>
        {canManage && (
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="button" onClick={() => setShowAdd((v) => !v)}>
              {showAdd ? "Cancel" : "Add manually"}
            </button>
            <button className="button" onClick={() => setShowPromote((v) => !v)} disabled={runs.length === 0}>
              {showPromote ? "Cancel" : "Promote from run"}
            </button>
          </div>
        )}
      </div>

      {error && <div style={{ color: "#b91c1c", marginBottom: "0.5rem" }}>{error}</div>}

      {showAdd && (
        <div style={{ display: "grid", gap: "0.5rem", marginBottom: "0.75rem", padding: "0.75rem",
                      border: "1px solid #e2e8f0", borderRadius: 6 }}>
          <input className="input" placeholder="Patient ID (FHIR Patient.id)"
                 value={patientId} onChange={(e) => setPatientId(e.target.value)} />
          <input className="input" placeholder="Subject ID (e.g. S-001)"
                 value={subjectId} onChange={(e) => setSubjectId(e.target.value)} />
          <button className="button" onClick={handleAdd} disabled={adding}>
            {adding ? "Adding…" : "Enroll"}
          </button>
        </div>
      )}

      {showPromote && (
        <div style={{ display: "grid", gap: "0.5rem", marginBottom: "0.75rem", padding: "0.75rem",
                      border: "1px solid #e2e8f0", borderRadius: 6 }}>
          <select className="select" value={runId} onChange={(e) => setRunId(e.target.value)}>
            <option value="">— Select a completed run —</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id.slice(0, 8)}… · {r.resultCount ?? 0} matches · {new Date(r.createdAt).toLocaleString()}
              </option>
            ))}
          </select>
          <input className="input" placeholder="Subject ID prefix (default S)"
                 value={prefix} onChange={(e) => setPrefix(e.target.value)} />
          <textarea className="input" rows={4} placeholder="Patient IDs (one per line or comma-separated)"
                    value={patientList} onChange={(e) => setPatientList(e.target.value)} />
          <button className="button" onClick={handlePromote} disabled={promoting || !runId}>
            {promoting ? "Promoting…" : "Promote"}
          </button>
        </div>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : items.length === 0 ? (
        <p style={{ color: "#94a3b8" }}>No participants enrolled yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Subject</th>
              <th>Patient ID</th>
              <th>Status</th>
              <th>Source</th>
              <th>Enrolled</th>
              {canManage && <th></th>}
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td><strong>{p.subject_id}</strong></td>
                <td><code style={{ fontSize: "0.85rem" }}>{p.patient_id}</code></td>
                <td>{p.status}</td>
                <td style={{ fontSize: "0.85rem" }}>{p.source}</td>
                <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                  {p.enrolled_at ? new Date(p.enrolled_at).toLocaleString() : "—"}
                </td>
                {canManage && (
                  <td>
                    <button onClick={() => handleDelete(p)}
                            style={{ background: "transparent", border: "1px solid #cbd5e1",
                                     padding: "0.25rem 0.5rem", borderRadius: "0.5rem",
                                     cursor: "pointer", fontSize: "0.8rem", color: "#991b1b" }}>
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
