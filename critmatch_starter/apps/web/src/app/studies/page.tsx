"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  createStudy,
  fetchStudies,
  fetchStudyRuns,
  type RunSummary,
  type Study,
} from "../../lib/api";

export default function StudiesPage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [runsByStudy, setRunsByStudy] = useState<Record<string, RunSummary[]>>({});
  const [runsLoading, setRunsLoading] = useState<string | null>(null);

  useEffect(() => {
    fetchStudies()
      .then(setStudies)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate() {
    if (!name.trim()) return;
    const study = await createStudy(name, description || undefined);
    setStudies((prev) => [study, ...prev]);
    setName("");
    setDescription("");
    setShowForm(false);
  }

  async function toggleRuns(studyId: string) {
    if (expanded === studyId) {
      setExpanded(null);
      return;
    }
    setExpanded(studyId);
    if (runsByStudy[studyId]) return;
    setRunsLoading(studyId);
    try {
      const page = await fetchStudyRuns(studyId, 10, 0);
      setRunsByStudy((prev) => ({ ...prev, [studyId]: page.items }));
    } catch {
      setRunsByStudy((prev) => ({ ...prev, [studyId]: [] }));
    } finally {
      setRunsLoading(null);
    }
  }

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h1>Studies</h1>
          <p style={{ color: "#475569" }}>Saved cohort definitions and study workspaces.</p>
        </div>
        <button className="button" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "New Study"}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: "1rem", display: "grid", gap: "0.75rem" }}>
          <input className="input" placeholder="Study name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="button" onClick={handleCreate}>Create Study</button>
        </div>
      )}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Status</th>
              <th>Recent Runs</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4}>Loading…</td></tr>
            ) : studies.length === 0 ? (
              <tr><td colSpan={4}>No studies yet. Click &quot;New Study&quot; to create one.</td></tr>
            ) : (
              studies.flatMap((study) => {
                const isOpen = expanded === study.id;
                const runs = runsByStudy[study.id];
                const rows = [
                  <tr key={study.id}>
                    <td>
                      <Link href={`/studies/${encodeURIComponent(study.id)}`} style={{ color: "#1d4ed8" }}>
                        {study.name}
                      </Link>
                    </td>
                    <td>{study.description || "—"}</td>
                    <td>{study.status}</td>
                    <td>
                      <button
                        onClick={() => toggleRuns(study.id)}
                        style={{ background: "transparent", border: "none", color: "#1d4ed8", cursor: "pointer", padding: 0 }}
                      >
                        {isOpen ? "Hide runs" : "Show runs"}
                      </button>
                    </td>
                  </tr>,
                ];
                if (isOpen) {
                  rows.push(
                    <tr key={`${study.id}-runs`}>
                      <td colSpan={4} style={{ background: "#f8fafc" }}>
                        {runsLoading === study.id ? (
                          <span style={{ color: "#475569" }}>Loading runs…</span>
                        ) : !runs || runs.length === 0 ? (
                          <span style={{ color: "#94a3b8" }}>No runs yet for this study.</span>
                        ) : (
                          <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                            {runs.map((r) => (
                              <li key={r.id} style={{ marginBottom: "0.25rem" }}>
                                <Link href={`/results?run=${encodeURIComponent(r.id)}`}>
                                  <code style={{ fontSize: "0.85rem" }}>{r.id.slice(0, 8)}…</code>
                                </Link>{" "}
                                — {r.status}
                                {r.resultCount != null && r.status === "completed" ? ` (${r.resultCount} matches)` : ""}
                                <span style={{ color: "#94a3b8", marginLeft: "0.5rem", fontSize: "0.8rem" }}>
                                  {new Date(r.createdAt).toLocaleString()}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>,
                  );
                }
                return rows;
              })
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
