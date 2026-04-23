"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ApiError,
  createExportLink,
  exportDownloadUrl,
  fetchRun,
  fetchRunResults,
  type RunDetail,
  type RunResultRow,
} from "../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

function ResultsInner() {
  const params = useSearchParams();
  const initialRunId = params.get("run") || "";
  const [runId, setRunId] = useState(initialRunId);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [rows, setRows] = useState<RunResultRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  async function load(id: string) {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetchRun(id);
      setRun(r);
      const page = await fetchRunResults(id, 100, 0);
      setRows(page.items);
      setTotal(page.total);
    } catch (e) {
      setError(describeError(e));
      setRun(null);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (initialRunId) load(initialRunId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRunId]);

  // Auto-poll while a run is queued/running
  useEffect(() => {
    if (!run || (run.status !== "queued" && run.status !== "running")) return;
    const t = setInterval(() => load(run.id), 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.status, run?.id]);

  async function handleExport() {
    if (!run) return;
    setExporting(true);
    setError(null);
    try {
      const link = await createExportLink(run.id, 300);
      window.location.href = exportDownloadUrl(link.downloadPath);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setExporting(false);
    }
  }

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <h1>Query Run Results</h1>
        <p style={{ color: "#475569" }}>Look up a query run by id and inspect matched patients.</p>
      </div>

      <div className="card" style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <input
          className="input"
          placeholder="run id (uuid)"
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          style={{ flex: 1 }}
        />
        <button className="button" onClick={() => load(runId.trim())} disabled={loading || !runId.trim()}>
          {loading ? "Loading…" : "Load Run"}
        </button>
      </div>

      {error && (
        <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>
      )}

      {run && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <div><strong>Status:</strong> {run.status}</div>
              <div><strong>Matches:</strong> {run.resultCount ?? 0}</div>
              <div><strong>Execution:</strong> {run.executionMs != null ? `${run.executionMs} ms` : "—"}</div>
              <div style={{ color: "#94a3b8", fontSize: "0.85rem" }}>{run.id}</div>
            </div>
            <button
              className="button"
              onClick={handleExport}
              disabled={exporting || run.status !== "completed"}
              title={run.status !== "completed" ? "Available once the run completes" : ""}
            >
              {exporting ? "Preparing…" : "Export CSV"}
            </button>
          </div>
        </div>
      )}

      {run && (
        <div className="card">
          <h2>Matched Patients ({rows.length} of {total})</h2>
          <table>
            <thead>
              <tr>
                <th>Patient ID</th>
                <th>MRN Hash</th>
                <th>Primary Reason</th>
                <th>Matched Rules</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={4}>{run.status === "completed" ? "No matches" : "Run not complete yet"}</td></tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.patientId}>
                    <td>{r.patientId}</td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                      {r.mrnHash ? `${r.mrnHash.slice(0, 12)}…` : "—"}
                    </td>
                    <td>{r.primaryMatchReason || "—"}</td>
                    <td>{r.matchedRules.join(", ")}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<main className="container"><div className="card">Loading…</div></main>}>
      <ResultsInner />
    </Suspense>
  );
}
