"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  fetchAuditEvents,
  fhirPing,
  getMe,
  type AuditEvent,
  type AuditFilters,
  type FhirPing,
  type SessionInfo,
} from "../../lib/api";

const PAGE_SIZE = 50;

const COMMON_ACTIONS = [
  "study_create",
  "criteria_set_create",
  "query_run",
  "query_run_cancel",
  "query_run_retry",
  "export_link_create",
  "export_download",
];

function describeError(e: unknown): string {
  if (e instanceof ApiError) return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  return (e as Error).message ?? "Unknown error";
}

export default function AuditPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);

  const [filters, setFilters] = useState<AuditFilters>({ limit: PAGE_SIZE, offset: 0 });
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ping, setPing] = useState<FhirPing | null>(null);
  const [pinging, setPinging] = useState(false);

  async function runPing() {
    setPinging(true);
    try {
      setPing(await fhirPing());
    } catch (e) {
      setPing({ ok: false, configured: false, reason: describeError(e) });
    } finally {
      setPinging(false);
    }
  }

  useEffect(() => {
    getMe()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setSessionLoaded(true));
  }, []);

  async function load(overrides?: Partial<AuditFilters>) {
    const next: AuditFilters = { ...filters, ...overrides };
    setFilters(next);
    setLoading(true);
    setError(null);
    try {
      const page = await fetchAuditEvents(next);
      setItems(page.items);
      setTotal(page.total);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (sessionLoaded && session && (session.role === "admin" || session.role === "auditor")) {
      load({ offset: 0 });
    }
    if (sessionLoaded && session && session.role === "admin") {
      runPing();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionLoaded, session]);

  if (sessionLoaded && (!session || (session.role !== "admin" && session.role !== "auditor"))) {
    return (
      <main className="container">
        <div className="card">
          <h1>Audit Log</h1>
          <p style={{ color: "#b91c1c" }}>
            This page is restricted to users with the <code>admin</code> or <code>auditor</code> role.
          </p>
        </div>
      </main>
    );
  }

  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;
  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <h1>Audit Log</h1>
        <p style={{ color: "#475569" }}>Immutable trail of mutations and exports.</p>
      </div>

      {session?.role === "admin" && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "1rem" }}>FHIR connectivity</h2>
              {ping == null ? (
                <p style={{ color: "#94a3b8", margin: "0.25rem 0 0" }}>{pinging ? "Probing…" : "Not yet probed."}</p>
              ) : ping.ok ? (
                <p style={{ margin: "0.25rem 0 0", color: "#475569" }}>
                  <span style={{ color: "#16a34a", fontWeight: 600 }}>● online</span>
                  {" · "}{ping.software ?? "FHIR"} {ping.fhirVersion ?? ""}
                  {" · "}{ping.resourceCount ?? 0} resource types
                  {ping.elapsedMs != null ? ` · ${ping.elapsedMs} ms` : ""}
                  {ping.url ? <span style={{ color: "#94a3b8" }}> · {ping.url}</span> : null}
                </p>
              ) : (
                <p style={{ margin: "0.25rem 0 0", color: "#b91c1c" }}>
                  ● {ping.configured ? "unreachable" : "not configured"}
                  {ping.reason ? ` · ${ping.reason}` : ""}
                </p>
              )}
            </div>
            <button className="button" onClick={runPing} disabled={pinging}>
              {pinging ? "Probing…" : "Re-probe"}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: "1rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem" }}>
        <div>
          <label>Action</label>
          <select
            className="select"
            value={filters.action ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value || undefined }))}
          >
            <option value="">Any</option>
            {COMMON_ACTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Object type</label>
          <input
            className="input"
            placeholder="e.g. query_run"
            value={filters.objectType ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, objectType: e.target.value || undefined }))}
          />
        </div>
        <div>
          <label>Object id</label>
          <input
            className="input"
            placeholder="uuid"
            value={filters.objectId ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, objectId: e.target.value || undefined }))}
          />
        </div>
        <div>
          <label>User id</label>
          <input
            className="input"
            placeholder="uuid"
            value={filters.userId ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, userId: e.target.value || undefined }))}
          />
        </div>
        <div>
          <label>Since (ISO)</label>
          <input
            className="input"
            placeholder="2026-04-01T00:00:00Z"
            value={filters.since ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, since: e.target.value || undefined }))}
          />
        </div>
        <div>
          <label>Until (ISO)</label>
          <input
            className="input"
            placeholder="2026-04-30T23:59:59Z"
            value={filters.until ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, until: e.target.value || undefined }))}
          />
        </div>
        <div style={{ display: "flex", alignItems: "end", gap: "0.5rem" }}>
          <button className="button" onClick={() => load({ offset: 0 })} disabled={loading}>
            {loading ? "Loading…" : "Apply"}
          </button>
          <button
            className="button"
            style={{ background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
            onClick={() => load({ action: undefined, objectType: undefined, objectId: undefined, userId: undefined, since: undefined, until: undefined, offset: 0 })}
          >
            Clear
          </button>
        </div>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <span style={{ color: "#475569" }}>{total} event(s)</span>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button
              onClick={() => load({ offset: Math.max(0, offset - limit) })}
              disabled={offset === 0 || loading}
              style={{ background: "transparent", border: "1px solid #cbd5e1", padding: "0.25rem 0.6rem", borderRadius: "0.5rem", cursor: "pointer" }}
            >
              ←
            </button>
            <span style={{ fontSize: "0.85rem", color: "#475569" }}>{page} / {pageCount}</span>
            <button
              onClick={() => load({ offset: offset + limit })}
              disabled={offset + limit >= total || loading}
              style={{ background: "transparent", border: "1px solid #cbd5e1", padding: "0.25rem 0.6rem", borderRadius: "0.5rem", cursor: "pointer" }}
            >
              →
            </button>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Object</th>
              <th>User</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={5} style={{ color: "#94a3b8" }}>No events match the current filters.</td></tr>
            ) : (
              items.map((ev, idx) => (
                <tr key={idx}>
                  <td style={{ fontSize: "0.85rem", color: "#475569" }}>{new Date(ev.createdAt).toLocaleString()}</td>
                  <td><code style={{ fontSize: "0.85rem" }}>{ev.action}</code></td>
                  <td>
                    <code style={{ fontSize: "0.85rem" }}>{ev.objectType}</code>
                    {ev.objectId ? <span style={{ color: "#94a3b8" }}> · {ev.objectId.slice(0, 8)}…</span> : null}
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "#475569" }}>
                    {ev.userId ? `${ev.userId.slice(0, 8)}…` : "—"}
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "#475569", maxWidth: "320px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {ev.metadata ? JSON.stringify(ev.metadata) : "—"}
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
