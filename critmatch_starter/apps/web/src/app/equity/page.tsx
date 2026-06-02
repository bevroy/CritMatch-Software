"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchEquityAlerts,
  fetchEquityScorecard,
  type EquityAlert,
  type EquityMetric,
} from "../../lib/api";

export default function EquityPage() {
  const [metrics, setMetrics] = useState<EquityMetric[]>([]);
  const [alerts, setAlerts] = useState<EquityAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricData, alertData] = await Promise.all([
        fetchEquityScorecard(),
        fetchEquityAlerts(),
      ]);
      setMetrics(metricData);
      setAlerts(alertData);
    } catch {
      setError("Unable to load equity scorecard data.");
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
        <h2 style={{ marginBottom: "0.5rem" }}>Equity Scorecards</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.6 }}>
          Monitor subgroup conversion outcomes and surface targeted recommendations to
          improve equitable clinical research participation.
        </p>
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", marginBottom: "0.6rem" }}>
          <h3 style={{ margin: 0 }}>Equity Metrics</h3>
          <button className="button-secondary" type="button" onClick={() => void loadData()} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loading ? (
          <p style={{ margin: 0, color: "var(--cm-muted)" }}>Loading equity scorecards...</p>
        ) : error ? (
          <p className="error" style={{ margin: 0 }}>{error}</p>
        ) : (
          <>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Subgroup</th>
                    <th>Screened</th>
                    <th>Enrolled</th>
                    <th>Conversion</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((item) => (
                    <tr key={`${item.category}-${item.subgroup}`}>
                      <td>{item.category}</td>
                      <td>{item.subgroup}</td>
                      <td>{item.screened}</td>
                      <td>{item.enrolled}</td>
                      <td>{item.conversionRate.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3 style={{ marginTop: "1rem", marginBottom: "0.5rem" }}>Equity Alerts</h3>
            <div className="grid" style={{ gap: "0.75rem" }}>
              {alerts.map((item) => (
                <article key={item.id} className="card">
                  <h4 style={{ marginBottom: "0.35rem" }}>{item.title}</h4>
                  <p style={{ margin: "0 0 0.35rem", color: "var(--cm-muted)" }}>
                    Severity: {item.severity}
                  </p>
                  <p style={{ margin: 0, color: "var(--cm-muted)" }}>{item.recommendation}</p>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  );
}
