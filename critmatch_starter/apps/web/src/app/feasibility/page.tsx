"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  createFeasibilityQuestionnaire,
  fetchFeasibilityQuestionnaires,
  fetchStudies,
  type FeasibilityQuestionnaireSummary,
  type Study,
} from "../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

export default function FeasibilityIndexPage() {
  const [items, setItems] = useState<FeasibilityQuestionnaireSummary[]>([]);
  const [studies, setStudies] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [studyId, setStudyId] = useState<string>("");
  const [creating, setCreating] = useState(false);

  async function load() {
    setError(null);
    try {
      const [list, studiesList] = await Promise.all([
        fetchFeasibilityQuestionnaires(),
        fetchStudies().catch(() => []),
      ]);
      setItems(list);
      setStudies(studiesList);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createFeasibilityQuestionnaire({
        name: name.trim(),
        description: description.trim() || undefined,
        studyId: studyId || undefined,
        questions: [],
      });
      setName("");
      setDescription("");
      setStudyId("");
      setShowForm(false);
      window.location.href = `/feasibility/${encodeURIComponent(created.id)}`;
    } catch (e) {
      setError(describeError(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="container">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <div>
          <h1>Feasibility</h1>
          <p style={{ color: "#475569" }}>
            Answer typical research-study feasibility questionnaire items by querying the EMR.
            When attached to a study with PI / Sub-I rows, results are limited to those
            providers&apos; patients.
          </p>
        </div>
        <button className="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New Questionnaire"}
        </button>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: "1rem", display: "grid", gap: "0.75rem" }}>
          <input
            className="input"
            placeholder="Questionnaire name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="input"
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div>
            <label>Attach to study (optional)</label>
            <select
              className="select"
              value={studyId}
              onChange={(e) => setStudyId(e.target.value)}
            >
              <option value="">— None (personal) —</option>
              {studies.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <button className="button" onClick={handleCreate} disabled={creating}>
            {creating ? "Creating…" : "Create"}
          </button>
        </div>
      )}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Questions</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4}>Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} style={{ color: "#94a3b8" }}>No questionnaires yet.</td></tr>
            ) : (
              items.map((q) => (
                <tr key={q.id}>
                  <td>
                    <Link
                      href={`/feasibility/${encodeURIComponent(q.id)}`}
                      style={{ color: "#1d4ed8" }}
                    >
                      {q.name}
                    </Link>
                  </td>
                  <td>{q.description || "—"}</td>
                  <td>{q.questionCount}</td>
                  <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                    {new Date(q.updatedAt).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
