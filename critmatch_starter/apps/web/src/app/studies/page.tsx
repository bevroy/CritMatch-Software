"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  createStudy,
  devLogin,
  devLoginEnabled,
  fetchStudies,
  fetchStudyRuns,
  type RunSummary,
  type Study,
} from "../../lib/api";

export default function StudiesPage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [runsByStudy, setRunsByStudy] = useState<Record<string, RunSummary[]>>({});
  const [runsLoading, setRunsLoading] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [devLoginAvailable, setDevLoginAvailable] = useState(false);
  const [devLoginBusy, setDevLoginBusy] = useState(false);

  useEffect(() => {
    fetchStudies()
      .then((s) => {
        setStudies(s);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) {
          setAuthRequired(true);
        } else if (e instanceof ApiError) {
          setLoadError(`${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`);
        } else {
          setLoadError((e as Error).message ?? "Failed to load studies");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!authRequired) return;
    devLoginEnabled()
      .then((r) => setDevLoginAvailable(r.enabled))
      .catch(() => setDevLoginAvailable(false));
  }, [authRequired]);

  async function handleDevLogin(role: "research_user" | "admin" | "auditor") {
    setDevLoginBusy(true);
    try {
      await devLogin(role);
      window.location.reload();
    } catch (e) {
      setLoadError(e instanceof ApiError ? `${e.message}` : (e as Error).message);
      setDevLoginBusy(false);
    }
  }

  async function handleCreate() {
    setCreateError(null);
    if (!name.trim()) return;
    try {
      const study = await createStudy(name, description || undefined);
      setStudies((prev) => [study, ...prev]);
      setName("");
      setDescription("");
      setShowForm(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setAuthRequired(true);
      } else if (e instanceof ApiError) {
        setCreateError(`${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`);
      } else {
        setCreateError((e as Error).message ?? "Failed to create study");
      }
    }
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
        <button
          className="button"
          onClick={() => setShowForm(!showForm)}
          disabled={authRequired}
          title={authRequired ? "Sign in first" : ""}
        >
          {showForm ? "Cancel" : "New Study"}
        </button>
      </div>

      {authRequired && (
        <div className="card" style={{ marginBottom: "1rem", borderLeft: "4px solid #b45309" }}>
          <strong>You&apos;re not signed in.</strong>
          <p style={{ margin: "0.25rem 0 0", color: "#475569" }}>
            CritMatch authenticates through SMART-on-FHIR. Launch the app from your EHR, or visit{" "}
            <Link href="/launch" style={{ color: "#1d4ed8" }}>/launch</Link> with the right{" "}
            <code>iss</code> parameter to start a session.
          </p>
          {devLoginAvailable && (
            <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ color: "#475569", fontSize: "0.85rem" }}>Dev sign in:</span>
              <button
                className="button"
                style={{ padding: "0.4rem 0.75rem" }}
                disabled={devLoginBusy}
                onClick={() => handleDevLogin("research_user")}
              >
                {devLoginBusy ? "Signing in…" : "Researcher"}
              </button>
              <button
                className="button"
                style={{ padding: "0.4rem 0.75rem", background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
                disabled={devLoginBusy}
                onClick={() => handleDevLogin("admin")}
              >
                Admin
              </button>
              <button
                className="button"
                style={{ padding: "0.4rem 0.75rem", background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
                disabled={devLoginBusy}
                onClick={() => handleDevLogin("auditor")}
              >
                Auditor
              </button>
            </div>
          )}
        </div>
      )}

      {loadError && !authRequired && (
        <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{loadError}</div>
      )}

      {showForm && !authRequired && (
        <div className="card" style={{ marginBottom: "1rem", display: "grid", gap: "0.75rem" }}>
          <input className="input" placeholder="Study name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="button" onClick={handleCreate}>Create Study</button>
          {createError && <p style={{ color: "#b91c1c", margin: 0 }}>{createError}</p>}
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
            ) : authRequired ? (
              <tr><td colSpan={4} style={{ color: "#94a3b8" }}>Sign in to view studies.</td></tr>
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
                      {study.myAccess && study.myAccess !== "owner" && (
                        <span
                          title={`Your access: ${study.myAccess}`}
                          style={{
                            marginLeft: "0.5rem",
                            padding: "0.1rem 0.45rem",
                            borderRadius: "999px",
                            fontSize: "0.7rem",
                            background: study.myAccess === "admin" ? "#fef3c7" : "#e0e7ff",
                            color: study.myAccess === "admin" ? "#92400e" : "#3730a3",
                            verticalAlign: "middle",
                          }}
                        >
                          {study.myAccess === "admin" ? "admin" : `shared · ${study.myAccess}`}
                        </span>
                      )}
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
