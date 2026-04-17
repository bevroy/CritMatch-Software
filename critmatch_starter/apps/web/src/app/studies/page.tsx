"use client";

import { useEffect, useState } from "react";
import { createStudy, fetchStudies, type Study } from "../../lib/api";

export default function StudiesPage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

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
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={3}>Loading…</td></tr>
            ) : studies.length === 0 ? (
              <tr><td colSpan={3}>No studies yet. Click &quot;New Study&quot; to create one.</td></tr>
            ) : (
              studies.map((study) => (
                <tr key={study.id}>
                  <td>{study.name}</td>
                  <td>{study.description || "—"}</td>
                  <td>{study.status}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
