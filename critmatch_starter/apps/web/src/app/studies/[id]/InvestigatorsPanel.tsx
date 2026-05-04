"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  addInvestigator,
  fetchInvestigators,
  removeInvestigator,
  type Investigator,
  type InvestigatorList,
  type InvestigatorRole,
} from "../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

interface Props {
  studyId: string;
  canManage: boolean;
}

export default function InvestigatorsPanel({ studyId, canManage }: Props) {
  const [data, setData] = useState<InvestigatorList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const [practitionerId, setPractitionerId] = useState("");
  const [name, setName] = useState("");
  const [npi, setNpi] = useState("");
  const [role, setRole] = useState<InvestigatorRole>("sub_investigator");

  async function load() {
    setError(null);
    try {
      setData(await fetchInvestigators(studyId));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId]);

  async function handleAdd() {
    if (!practitionerId.trim()) {
      setError("Practitioner FHIR id is required.");
      return;
    }
    setWorking(true);
    setError(null);
    try {
      await addInvestigator(studyId, {
        practitioner_id: practitionerId.trim(),
        name: name.trim() || undefined,
        npi: npi.trim() || undefined,
        role,
      });
      setPractitionerId("");
      setName("");
      setNpi("");
      setRole("sub_investigator");
      await load();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setWorking(false);
    }
  }

  async function handleRemove(inv: Investigator) {
    if (!confirm(`Remove ${inv.name ?? inv.practitionerId} from this study?`)) return;
    setWorking(true);
    setError(null);
    try {
      await removeInvestigator(studyId, inv.id);
      await load();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="card" style={{ marginTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ margin: 0 }}>Study Investigators</h2>
        <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>
          PI / Sub-I scoping for cohort and feasibility searches
        </span>
      </div>
      <p style={{ color: "#475569", fontSize: "0.9rem", marginTop: "0.5rem" }}>
        When at least one investigator is listed, every cohort run and feasibility run for
        this study is restricted to patients with an Encounter involving one of these
        practitioners.
      </p>

      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}

      {loading ? (
        <p style={{ color: "#94a3b8" }}>Loading…</p>
      ) : data && data.items.length === 0 ? (
        <p style={{ color: "#94a3b8", margin: 0 }}>
          No investigators yet — searches will run against the entire EMR.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Practitioner</th>
              <th>Name</th>
              <th>NPI</th>
              <th>Role</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((inv) => (
              <tr key={inv.id}>
                <td><code style={{ fontSize: "0.85rem" }}>{inv.practitionerId}</code></td>
                <td>{inv.name || "—"}</td>
                <td>{inv.npi || "—"}</td>
                <td>
                  <code style={{ fontSize: "0.8rem" }}>
                    {inv.role === "principal_investigator" ? "PI" : "Sub-I"}
                  </code>
                </td>
                <td>
                  {canManage && (
                    <button
                      onClick={() => handleRemove(inv)}
                      disabled={working}
                      style={{
                        background: "transparent",
                        border: "1px solid #fecaca",
                        color: "#b91c1c",
                        padding: "0.2rem 0.5rem",
                        borderRadius: "0.5rem",
                        cursor: "pointer",
                        fontSize: "0.8rem",
                      }}
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {canManage && (
        <div style={{ marginTop: "1rem", borderTop: "1px solid #e2e8f0", paddingTop: "0.75rem" }}>
          <h3 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "0.95rem" }}>
            Add investigator
          </h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.2fr 1.2fr 1fr 1fr auto",
              gap: "0.5rem",
              alignItems: "end",
            }}
          >
            <div>
              <label>FHIR Practitioner id</label>
              <input
                className="input"
                placeholder="e.g. prac-123"
                value={practitionerId}
                onChange={(e) => setPractitionerId(e.target.value)}
              />
            </div>
            <div>
              <label>Display name</label>
              <input
                className="input"
                placeholder="Dr. Jane Smith"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label>NPI (optional)</label>
              <input
                className="input"
                placeholder="1234567890"
                value={npi}
                onChange={(e) => setNpi(e.target.value)}
              />
            </div>
            <div>
              <label>Role</label>
              <select
                className="select"
                value={role}
                onChange={(e) => setRole(e.target.value as InvestigatorRole)}
              >
                <option value="principal_investigator">Principal Investigator</option>
                <option value="sub_investigator">Sub-Investigator</option>
              </select>
            </div>
            <button className="button" onClick={handleAdd} disabled={working}>
              {working ? "Saving…" : "Add"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
