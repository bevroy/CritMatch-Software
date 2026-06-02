"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchNavigatorMetrics,
  fetchNavigatorTasks,
  type NavigatorMetrics,
  type NavigatorTask,
} from "../../lib/api";

export default function NavigatorPage() {
  const [metrics, setMetrics] = useState<NavigatorMetrics | null>(null);
  const [tasks, setTasks] = useState<NavigatorTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, tasksData] = await Promise.all([
        fetchNavigatorMetrics(),
        fetchNavigatorTasks(),
      ]);
      setMetrics(metricsData);
      setTasks(tasksData);
    } catch {
      setError("Unable to load navigator workspace data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  return (
    <main className="container">
      <section className="card" style={{ maxWidth: 980, margin: "0 auto" }}>
        <h2 style={{ marginBottom: "0.5rem" }}>Navigator Workspace</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.6 }}>
          Coordinate barrier-resolution tasks for participants across transportation,
          language support, childcare, and digital access.
        </p>
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", marginBottom: "0.6rem" }}>
          <h3 style={{ margin: 0 }}>Navigator Queue</h3>
          <button className="button-secondary" type="button" onClick={() => void loadData()} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loading ? (
          <p style={{ margin: 0, color: "var(--cm-muted)" }}>Loading navigator queue...</p>
        ) : error ? (
          <p className="error" style={{ margin: 0 }}>{error}</p>
        ) : (
          <>
            {metrics && (
              <div className="grid grid-3" style={{ marginBottom: "1rem" }}>
                <article className="card">
                  <h3 style={{ marginBottom: "0.35rem" }}>Open</h3>
                  <p style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800 }}>{metrics.openTasks}</p>
                </article>
                <article className="card">
                  <h3 style={{ marginBottom: "0.35rem" }}>In Progress</h3>
                  <p style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800 }}>{metrics.inProgressTasks}</p>
                </article>
                <article className="card">
                  <h3 style={{ marginBottom: "0.35rem" }}>Resolved (30d)</h3>
                  <p style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800 }}>{metrics.resolvedTasks30d}</p>
                </article>
              </div>
            )}

            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Participant</th>
                    <th>Barrier</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Due</th>
                    <th>Assigned</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((item) => (
                    <tr key={item.id}>
                      <td>{item.participantAlias}</td>
                      <td>{item.barrier}</td>
                      <td>{item.priority}</td>
                      <td>{item.status}</td>
                      <td>{item.dueDate}</td>
                      <td>{item.assignedTo}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
