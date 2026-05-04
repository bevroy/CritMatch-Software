"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  createEdcForm,
  fetchEdcForms,
  fetchStudies,
  type EdcFormSummary,
  type Study,
} from "../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

export default function EdcIndexPage() {
  const [items, setItems] = useState<EdcFormSummary[]>([]);
  const [studies, setStudies] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [studyId, setStudyId] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    setError(null);
    try {
      const [forms, studiesList] = await Promise.all([
        fetchEdcForms(),
        fetchStudies().catch(() => []),
      ]);
      setItems(forms);
      setStudies(studiesList);
      if (studiesList.length > 0 && !studyId) setStudyId(studiesList[0].id);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate() {
    if (!name.trim() || !studyId) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createEdcForm({
        study_id: studyId,
        name: name.trim(),
        description: description.trim() || undefined,
        fields: [],
      });
      setName("");
      setDescription("");
      setShowForm(false);
      window.location.href = `/edc/forms/${encodeURIComponent(created.id)}`;
    } catch (e) {
      setError(describeError(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h1>EDC</h1>
          <p style={{ color: "#475569" }}>
            Build data-collection forms, identify enrolled participants, and pull data points
            directly from the EMR with a full Part 11 audit trail.
          </p>
        </div>
        <button className="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New Form"}
        </button>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: "1rem", display: "grid", gap: "0.75rem" }}>
          <div>
            <label>Study</label>
            <select className="select" value={studyId} onChange={(e) => setStudyId(e.target.value)}>
              <option value="">— Select a study —</option>
              {studies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <input className="input" placeholder="Form name (e.g. Baseline Visit)"
                 value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="Description (optional)"
                 value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="button" onClick={handleCreate} disabled={creating || !studyId || !name.trim()}>
            {creating ? "Creating…" : "Create"}
          </button>
        </div>
      )}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Study</th>
              <th>Status</th>
              <th>Version</th>
              <th>Fields</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6}>Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={6} style={{ color: "#94a3b8" }}>No forms yet.</td></tr>
            ) : (
              items.map((f) => {
                const study = studies.find((s) => s.id === f.study_id);
                return (
                  <tr key={f.id}>
                    <td>
                      <Link href={`/edc/forms/${encodeURIComponent(f.id)}`} style={{ color: "#1d4ed8" }}>
                        {f.name}
                      </Link>
                    </td>
                    <td>{study?.name ?? f.study_id.slice(0, 8)}</td>
                    <td>{f.status}</td>
                    <td>v{f.version}</td>
                    <td>{f.fieldCount}</td>
                    <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                      {new Date(f.updated_at).toLocaleString()}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
