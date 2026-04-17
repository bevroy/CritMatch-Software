"use client";

import { useEffect, useState } from "react";
import { fetchAuditEvents, type AuditEvent } from "../../lib/api";

export default function ResultsPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuditEvents()
      .then(setEvents)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <h1>Results &amp; Audit Log</h1>
        <p style={{ color: "#475569" }}>Review query runs and audit events.</p>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Action</th>
              <th>Object Type</th>
              <th>Object ID</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4}>Loading…</td></tr>
            ) : events.length === 0 ? (
              <tr><td colSpan={4}>No events yet. Run a query to generate audit entries.</td></tr>
            ) : (
              events.map((e, i) => (
                <tr key={i}>
                  <td>{e.action}</td>
                  <td>{e.objectType}</td>
                  <td>{e.objectId}</td>
                  <td>{e.createdAt}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
