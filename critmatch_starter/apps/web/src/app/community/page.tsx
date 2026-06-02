"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchCommunityPartners,
  fetchCommunitySummary,
  type CommunityPartner,
  type CommunitySummary,
} from "../../lib/api";

export default function CommunityPage() {
  const [summary, setSummary] = useState<CommunitySummary | null>(null);
  const [partners, setPartners] = useState<CommunityPartner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, partnersData] = await Promise.all([
        fetchCommunitySummary(),
        fetchCommunityPartners(),
      ]);
      setSummary(summaryData);
      setPartners(partnersData);
    } catch {
      setError("Unable to load community network data.");
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
        <h2 style={{ marginBottom: "0.5rem" }}>Community Partner Network</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.6 }}>
          Connect community organizations, referral partners, and health centers to expand
          trial access and support closed-loop recruitment workflows.
        </p>
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", marginBottom: "0.6rem" }}>
          <h3 style={{ margin: 0 }}>Network Snapshot</h3>
          <button className="button-secondary" type="button" onClick={() => void loadData()} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loading ? (
          <p style={{ margin: 0, color: "var(--cm-muted)" }}>Loading community partners...</p>
        ) : error ? (
          <p className="error" style={{ margin: 0 }}>{error}</p>
        ) : (
          <>
            {summary && (
              <div className="grid grid-3" style={{ marginBottom: "1rem" }}>
                <article className="card">
                  <h3 style={{ marginBottom: "0.35rem" }}>Partners</h3>
                  <p style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800 }}>{summary.partnerCount}</p>
                </article>
                <article className="card">
                  <h3 style={{ marginBottom: "0.35rem" }}>Active Referrals</h3>
                  <p style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800 }}>{summary.activeReferrals}</p>
                </article>
                <article className="card">
                  <h3 style={{ marginBottom: "0.35rem" }}>Enrolled</h3>
                  <p style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800 }}>{summary.enrolledParticipants}</p>
                </article>
              </div>
            )}

            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Partner</th>
                    <th>Type</th>
                    <th>Location</th>
                    <th>Languages</th>
                    <th>Referrals</th>
                    <th>Enrolled</th>
                    <th>Last Activity</th>
                  </tr>
                </thead>
                <tbody>
                  {partners.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td>
                      <td>{item.kind}</td>
                      <td>{item.city}, {item.state}</td>
                      <td>{item.languages.join(", ")}</td>
                      <td>{item.activeReferrals}</td>
                      <td>{item.enrolledParticipants}</td>
                      <td>{item.lastActivity}</td>
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
