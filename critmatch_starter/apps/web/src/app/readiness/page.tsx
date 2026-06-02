"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchReadinessProfile,
  fetchReadinessStatus,
  type ReadinessProfile,
  type ReadinessStatus,
} from "../../lib/api";

export default function ReadinessPage() {
  const [status, setStatus] = useState<ReadinessStatus | null>(null);
  const [profile, setProfile] = useState<ReadinessProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusData, profileData] = await Promise.all([
        fetchReadinessStatus(),
        fetchReadinessProfile(),
      ]);
      setStatus(statusData);
      setProfile(profileData);
    } catch {
      setError("Unable to load readiness data right now.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

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
        <h2 style={{ marginBottom: "0.5rem" }}>Real-World Data & Research Readiness Engine</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.6 }}>
          Assess site readiness, estimate eligible populations, support feasibility analyses,
          identify care gaps, and generate sponsor-ready profiles.
        </p>
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
          <h3 style={{ margin: 0 }}>Readiness Snapshot</h3>
          <button
            type="button"
            className="button-secondary"
            onClick={() => void loadData()}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loading ? (
          <p style={{ margin: 0, color: "var(--cm-muted)" }}>Loading readiness snapshot...</p>
        ) : error ? (
          <p className="error" style={{ margin: 0 }}>{error}</p>
        ) : profile ? (
          <>
            {status && (
              <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
                <strong>Status:</strong> {status.status}
                {refreshed ? ` | Refreshed: ${refreshed}` : ""}
              </p>
            )}
            <div className="grid grid-3" style={{ marginTop: "0.25rem" }}>
              <article className="card">
                <h3 style={{ marginBottom: "0.35rem" }}>Research Readiness</h3>
                <p style={{ margin: 0, fontSize: "1.55rem", fontWeight: 800, color: "var(--cm-teal)" }}>
                  {profile.readinessScore}/100
                </p>
                <p style={{ margin: "0.45rem 0 0", color: "var(--cm-muted)" }}>{profile.siteName}</p>
              </article>
              <article className="card">
                <h3 style={{ marginBottom: "0.35rem" }}>Eligible Population</h3>
                <p style={{ margin: 0, fontSize: "1.55rem", fontWeight: 800, color: "var(--cm-teal)" }}>
                  {profile.eligiblePopulationEstimate.toLocaleString()}
                </p>
                <p style={{ margin: "0.45rem 0 0", color: "var(--cm-muted)" }}>
                  Estimated patients for active protocol fit
                </p>
              </article>
              <article className="card">
                <h3 style={{ marginBottom: "0.35rem" }}>Feasibility Tier</h3>
                <p style={{ margin: 0, fontSize: "1.55rem", fontWeight: 800, color: "var(--cm-teal)" }}>
                  {profile.feasibilityTier}
                </p>
                <p style={{ margin: "0.45rem 0 0", color: "var(--cm-muted)" }}>
                  Based on data quality, operations, and recruitment velocity
                </p>
              </article>
            </div>

            <div className="grid grid-3" style={{ marginTop: "1rem" }}>
              <article className="card">
                <h3 style={{ marginBottom: "0.4rem" }}>Primary Indications</h3>
                <ul style={{ margin: 0, paddingLeft: "1.05rem", color: "var(--cm-muted)" }}>
                  {profile.primaryIndications.map((item) => (
                    <li key={item} style={{ marginBottom: "0.35rem" }}>{item}</li>
                  ))}
                </ul>
              </article>

              <article className="card" style={{ gridColumn: "span 2" }}>
                <h3 style={{ marginBottom: "0.4rem" }}>Care Gaps</h3>
                <ul style={{ margin: 0, paddingLeft: "1.05rem", color: "var(--cm-muted)" }}>
                  {profile.careGaps.map((item) => (
                    <li key={item} style={{ marginBottom: "0.35rem" }}>{item}</li>
                  ))}
                </ul>
              </article>
            </div>

            <article className="card" style={{ marginTop: "1rem" }}>
              <h3 style={{ marginBottom: "0.4rem" }}>Sponsor-Ready Profile</h3>
              <p style={{ margin: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
                {profile.sponsorReadySummary}
              </p>
            </article>
          </>
        ) : null}
      </section>
    </main>
  );
}
