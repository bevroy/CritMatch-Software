"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchRoieOpportunities,
  fetchRoieStatus,
  type RoieOpportunity,
  type RoieStatus,
} from "../../lib/api";

export default function RoiePage() {
  const functions = [
    {
      title: "Study Discovery",
      description: "Searches ClinicalTrials.gov continuously for relevant research opportunities.",
    },
    {
      title: "Site Matching",
      description: "Identifies studies aligned with your site population and care profile.",
    },
    {
      title: "Feasibility Prediction",
      description: "Predicts enrollment potential for candidate studies at your site.",
    },
    {
      title: "Sponsor Targeting",
      description: "Suggests sponsors likely to benefit from your site participating in a study.",
    },
    {
      title: "Geographic Analysis",
      description: "Identifies underserved regions where research participation is limited.",
    },
    {
      title: "Diversity Forecasting",
      description: "Forecasts enrollment diversity potential to support representative trial planning.",
    },
  ];

  const [status, setStatus] = useState<RoieStatus | null>(null);
  const [opportunities, setOpportunities] = useState<RoieOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusData, opportunitiesData] = await Promise.all([
        fetchRoieStatus(),
        fetchRoieOpportunities(6),
      ]);
      setStatus(statusData);
      setOpportunities(opportunitiesData);
    } catch {
      setError("Unable to load ROIE preview data right now.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview]);

  const refreshed = useMemo(() => {
    if (!status?.refreshedAt) return null;
    try {
      return new Date(status.refreshedAt).toLocaleString();
    } catch {
      return status.refreshedAt;
    }
  }, [status]);

  return (
    <main className="container">
      <section className="card" style={{ maxWidth: 980, margin: "0 auto" }}>
        <h2 style={{ marginBottom: "0.5rem" }}>Research Opportunity Intelligence Engine (ROIE)</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.6 }}>
          ROIE expands CritMatch with proactive intelligence to help research teams identify the
          right studies, sponsors, and populations at the right time.
        </p>
      </section>

      <section className="grid grid-3" style={{ marginTop: "1rem" }}>
        {functions.map((item) => (
          <article key={item.title} className="card">
            <h3 style={{ marginBottom: "0.4rem" }}>{item.title}</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
              {item.description}
            </p>
          </article>
        ))}
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem",
            marginBottom: "0.6rem",
          }}
        >
          <h3 style={{ margin: 0 }}>ROIE Preview Feed</h3>
          <button
            type="button"
            className="button-secondary"
            onClick={() => void loadPreview()}
            disabled={loading}
            aria-label="Refresh ROIE preview feed"
          >
            {loading ? "Refreshing..." : "Refresh Feed"}
          </button>
        </div>
        {loading ? (
          <p style={{ margin: 0, color: "var(--cm-muted)" }}>Loading preview intelligence...</p>
        ) : error ? (
          <p className="error" style={{ margin: 0 }}>{error}</p>
        ) : (
          <>
            {status && (
              <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
                <strong>Status:</strong> {status.status} | <strong>Source:</strong> {status.source}
                {refreshed ? ` | Refreshed: ${refreshed}` : ""}
              </p>
            )}
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Study</th>
                    <th>NCT</th>
                    <th>Sponsor</th>
                    <th>Status</th>
                    <th>Phase</th>
                    <th>Region</th>
                    <th>Match</th>
                    <th>Enrollment</th>
                    <th>Diversity</th>
                    <th>Contact</th>
                  </tr>
                </thead>
                <tbody>
                  {opportunities.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div style={{ fontWeight: 700 }}>
                          <a href={item.studyUrl} target="_blank" rel="noreferrer">
                            {item.title}
                          </a>
                        </div>
                        <div style={{ fontSize: "0.83rem", color: "var(--cm-muted)" }}>
                          {item.indication}
                        </div>
                      </td>
                      <td>{item.nctId}</td>
                      <td>{item.sponsor}</td>
                      <td>{item.recruitingStatus}</td>
                      <td>{item.phase}</td>
                      <td>{item.region}</td>
                      <td>{Math.round(item.siteMatchScore * 100)}%</td>
                      <td>{item.enrollmentPotential}</td>
                      <td>{item.diversityPotential}</td>
                      <td>
                        <div>{item.studyContactName ?? "N/A"}</div>
                        <div style={{ fontSize: "0.83rem", color: "var(--cm-muted)" }}>
                          {item.studyContactEmail ?? item.studyContactPhone ?? "N/A"}
                        </div>
                      </td>
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
