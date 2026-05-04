"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  ApiError,
  cancelRun,
  diffRuns,
  fetchCriteriaSets,
  fetchStudy,
  fetchStudyRuns,
  retryRun,
  runQuery,
  type CriteriaSetSummary,
  type RunDiff,
  type RunSummary,
  type Study,
} from "../../../lib/api";
import SharingPanel from "./SharingPanel";
import InvestigatorsPanel from "./InvestigatorsPanel";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

function statusBadge(status: string): React.CSSProperties {
  const map: Record<string, string> = {
    queued: "#64748b",
    claimed: "#0ea5e9",
    running: "#0ea5e9",
    completed: "#16a34a",
    failed: "#b91c1c",
    cancelled: "#a16207",
  };
  return {
    display: "inline-block",
    padding: "0.1rem 0.5rem",
    borderRadius: "0.5rem",
    background: map[status] ?? "#475569",
    color: "white",
    fontSize: "0.75rem",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  };
}

interface PageParams {
  params: Promise<{ id: string }>;
}

export default function StudyDetailPage({ params }: PageParams) {
  const { id } = use(params);

  const [study, setStudy] = useState<Study | null>(null);
  const [criteriaSets, setCriteriaSets] = useState<CriteriaSetSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [baseRunId, setBaseRunId] = useState<string>("");
  const [compareRunId, setCompareRunId] = useState<string>("");
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  async function loadAll() {
    setError(null);
    try {
      const [s, cs, page] = await Promise.all([
        fetchStudy(id),
        fetchCriteriaSets(id),
        fetchStudyRuns(id, 50, 0),
      ]);
      setStudy(s);
      setCriteriaSets(cs);
      setRuns(page.items);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Auto-refresh while any run is in-flight.
  useEffect(() => {
    const inFlight = runs.some(
      (r) => r.status === "queued" || r.status === "claimed" || r.status === "running",
    );
    if (!inFlight) return;
    const t = setInterval(loadAll, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs]);

  async function handleRunLatest() {
    if (criteriaSets.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const latest = criteriaSets[0];
      await runQuery(id, latest.id);
      await loadAll();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel(runId: string) {
    setError(null);
    try {
      await cancelRun(runId);
      await loadAll();
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function handleRetry(runId: string) {
    setError(null);
    try {
      await retryRun(runId);
      await loadAll();
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function handleDiff() {
    setDiffError(null);
    setDiff(null);
    if (!baseRunId || !compareRunId) {
      setDiffError("Pick two completed runs.");
      return;
    }
    if (baseRunId === compareRunId) {
      setDiffError("Pick two different runs.");
      return;
    }
    setDiffLoading(true);
    try {
      const result = await diffRuns(baseRunId, compareRunId);
      setDiff(result);
    } catch (e) {
      setDiffError(describeError(e));
    } finally {
      setDiffLoading(false);
    }
  }

  if (loading) {
    return (
      <main className="container">
        <div className="card">Loading study…</div>
      </main>
    );
  }

  if (!study) {
    return (
      <main className="container">
        <div className="card" style={{ color: "#b91c1c" }}>
          {error ?? "Study not found"}
        </div>
        <p style={{ marginTop: "1rem" }}>
          <Link href="/studies">← Back to studies</Link>
        </p>
      </main>
    );
  }

  const latestCs = criteriaSets[0];
  const completedRuns = runs.filter((r) => r.status === "completed");

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <Link href="/studies" style={{ color: "#475569" }}>← All studies</Link>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h1 style={{ marginBottom: "0.25rem" }}>{study.name}</h1>
            <p style={{ color: "#475569", margin: 0 }}>{study.description || "No description."}</p>
            <p style={{ color: "#94a3b8", margin: "0.25rem 0 0", fontSize: "0.85rem" }}>{study.id}</p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <Link href={`/builder?study=${encodeURIComponent(study.id)}`} className="button">
              Edit Criteria
            </Link>
            <button
              className="button"
              onClick={handleRunLatest}
              disabled={busy || !latestCs}
              title={!latestCs ? "Save a criteria set first" : ""}
            >
              {busy ? "Queuing…" : "Run Latest"}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2>Criteria Set Versions ({criteriaSets.length})</h2>
        {criteriaSets.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>
            No criteria sets yet. <Link href={`/builder?study=${encodeURIComponent(study.id)}`} style={{ color: "#1d4ed8" }}>Open the builder</Link> to create one.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Operator</th>
                <th>Rules</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {criteriaSets.map((cs) => (
                <tr key={cs.id}>
                  <td><strong>v{cs.version}</strong></td>
                  <td>{cs.logicJson?.operator ?? "—"}</td>
                  <td>{cs.logicJson?.rules?.length ?? 0}</td>
                  <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                    {new Date(cs.createdAt).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>Run History ({runs.length})</h2>
        {runs.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No runs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Matches</th>
                <th>Time</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const cancellable = r.status === "queued" || r.status === "claimed" || r.status === "running";
                const retryable = r.status === "failed" || r.status === "cancelled";
                return (
                  <tr key={r.id}>
                    <td>
                      <Link href={`/results?run=${encodeURIComponent(r.id)}`} style={{ color: "#1d4ed8" }}>
                        <code style={{ fontSize: "0.85rem" }}>{r.id.slice(0, 8)}…</code>
                      </Link>
                    </td>
                    <td><span style={statusBadge(r.status)}>{r.status}</span></td>
                    <td>{r.resultCount ?? "—"}</td>
                    <td>{r.executionMs != null ? `${r.executionMs} ms` : "—"}</td>
                    <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                      {new Date(r.createdAt).toLocaleString()}
                    </td>
                    <td style={{ display: "flex", gap: "0.5rem" }}>
                      {cancellable && (
                        <button
                          onClick={() => handleCancel(r.id)}
                          style={{ background: "transparent", border: "1px solid #cbd5e1", padding: "0.25rem 0.5rem", borderRadius: "0.5rem", cursor: "pointer", fontSize: "0.8rem" }}
                        >
                          Cancel
                        </button>
                      )}
                      {retryable && (
                        <button
                          onClick={() => handleRetry(r.id)}
                          style={{ background: "transparent", border: "1px solid #cbd5e1", padding: "0.25rem 0.5rem", borderRadius: "0.5rem", cursor: "pointer", fontSize: "0.8rem" }}
                        >
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2>Cohort Diff</h2>
        <p style={{ color: "#475569", fontSize: "0.9rem", marginTop: 0 }}>
          Compare matched patients between two completed runs to see who was added or removed.
        </p>

        {completedRuns.length < 2 ? (
          <p style={{ color: "#94a3b8" }}>Need at least two completed runs to diff.</p>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "0.5rem", alignItems: "end" }}>
              <div>
                <label>Base run</label>
                <select className="select" value={baseRunId} onChange={(e) => setBaseRunId(e.target.value)}>
                  <option value="">Pick a run…</option>
                  {completedRuns.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.id.slice(0, 8)}… · {r.resultCount ?? 0} matches · {new Date(r.createdAt).toLocaleString()}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Compare run</label>
                <select className="select" value={compareRunId} onChange={(e) => setCompareRunId(e.target.value)}>
                  <option value="">Pick a run…</option>
                  {completedRuns.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.id.slice(0, 8)}… · {r.resultCount ?? 0} matches · {new Date(r.createdAt).toLocaleString()}
                    </option>
                  ))}
                </select>
              </div>
              <button className="button" onClick={handleDiff} disabled={diffLoading}>
                {diffLoading ? "Diffing…" : "Diff"}
              </button>
            </div>

            {diffError && <p style={{ color: "#b91c1c", marginTop: "0.75rem" }}>{diffError}</p>}

            {diff && (
              <div style={{ marginTop: "1rem", display: "grid", gap: "0.75rem" }}>
                <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
                  <div><strong>Base:</strong> {diff.baseTotal} patients</div>
                  <div><strong>Compare:</strong> {diff.compareTotal} patients</div>
                  <div style={{ color: "#16a34a" }}><strong>Added:</strong> {diff.addedCount}</div>
                  <div style={{ color: "#b91c1c" }}><strong>Removed:</strong> {diff.removedCount}</div>
                  <div style={{ color: "#475569" }}><strong>Unchanged:</strong> {diff.unchangedCount}</div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div>
                    <h3 style={{ color: "#16a34a", marginBottom: "0.25rem" }}>Added (sample {diff.added.length} of {diff.addedCount})</h3>
                    {diff.added.length === 0 ? (
                      <p style={{ color: "#94a3b8" }}>None</p>
                    ) : (
                      <ul style={{ margin: 0, paddingLeft: "1.25rem", fontFamily: "monospace", fontSize: "0.8rem" }}>
                        {diff.added.map((pid) => <li key={pid}>{pid}</li>)}
                      </ul>
                    )}
                  </div>
                  <div>
                    <h3 style={{ color: "#b91c1c", marginBottom: "0.25rem" }}>Removed (sample {diff.removed.length} of {diff.removedCount})</h3>
                    {diff.removed.length === 0 ? (
                      <p style={{ color: "#94a3b8" }}>None</p>
                    ) : (
                      <ul style={{ margin: 0, paddingLeft: "1.25rem", fontFamily: "monospace", fontSize: "0.8rem" }}>
                        {diff.removed.map((pid) => <li key={pid}>{pid}</li>)}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      <SharingPanel studyId={study.id} onOwnerChanged={loadAll} />
      <InvestigatorsPanel
        studyId={study.id}
        canManage={
          study.myAccess === "owner" ||
          study.myAccess === "editor" ||
          study.myAccess === "admin"
        }
      />
    </main>
  );
}
