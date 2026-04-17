"use client";

import { useState } from "react";
import { expandTerm, type Expansion } from "../../lib/api";

interface Criterion {
  type: string;
  term: string;
  include: boolean;
  expansions: Expansion[];
}

export default function BuilderPage() {
  const [criterionType, setCriterionType] = useState("Diagnosis");
  const [searchTerm, setSearchTerm] = useState("");
  const [includeSynonyms, setIncludeSynonyms] = useState(true);
  const [expansions, setExpansions] = useState<Expansion[]>([]);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleAdd() {
    if (!searchTerm.trim()) return;
    setLoading(true);
    try {
      const result = await expandTerm(searchTerm);
      const exps = includeSynonyms ? result.expansions : result.expansions.filter((e) => e.type === "code");
      setExpansions(exps);
      setCriteria((prev) => [
        ...prev,
        { type: criterionType, term: result.normalizedTerm, include: true, expansions: exps },
      ]);
    } catch {
      setExpansions([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <div className="grid grid-3">
        <section className="card">
          <h2>Criteria Builder</h2>
          <div style={{ display: "grid", gap: "1rem" }}>
            <div>
              <label>Criterion Type</label>
              <select className="select" value={criterionType} onChange={(e) => setCriterionType(e.target.value)}>
                <option>Diagnosis</option>
                <option>Procedure</option>
                <option>Age</option>
                <option>Sex</option>
                <option>Encounter Date</option>
                <option>Site</option>
              </select>
            </div>
            <div>
              <label>Search Term or Code</label>
              <input
                className="input"
                placeholder="e.g. heart attack or I21"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              />
            </div>
            <label>
              <input type="checkbox" checked={includeSynonyms} onChange={(e) => setIncludeSynonyms(e.target.checked)} />{" "}
              Include known variations / synonyms
            </label>
            <button className="button" onClick={handleAdd} disabled={loading}>
              {loading ? "Expanding…" : "Add Criterion"}
            </button>
          </div>
        </section>

        <section className="card">
          <h2>Expanded Terms</h2>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {expansions.length === 0 ? (
              <p style={{ color: "#94a3b8" }}>Add a criterion to see expanded terms</p>
            ) : (
              expansions.map((exp, i) => (
                <div key={i} className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>
                  {exp.system ? `${exp.system}: ${exp.code} – ${exp.display}` : exp.display}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="card">
          <h2>Logic Summary</h2>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {criteria.length === 0 ? (
              <p style={{ color: "#94a3b8" }}>No criteria added yet</p>
            ) : (
              criteria.map((c, i) => (
                <div key={i} className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>
                  {c.include ? "Include" : "Exclude"} {c.type.toLowerCase()}: {c.term}
                </div>
              ))
            )}
          </div>
          {criteria.length > 0 && (
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
              <button
                className="button"
                style={{ background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
                onClick={() => setCriteria([])}
              >
                Clear
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
