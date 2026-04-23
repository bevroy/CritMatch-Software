"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  createCriteriaSet,
  expandTerm,
  fetchStudies,
  runQuery,
  type CriteriaLogic,
  type CriteriaRule,
  type Expansion,
  type Study,
} from "../../lib/api";

type Kind = "condition" | "observation" | "demographic";

interface Criterion {
  id: string;
  kind: Kind;
  label: string;
  expansions: Expansion[];
  field?: string;
  op?: string;
  value?: string | number;
}

function genId(): string {
  return `rule-${Math.random().toString(36).slice(2, 9)}`;
}

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

function toRule(c: Criterion): CriteriaRule {
  if (c.kind === "demographic") {
    return {
      id: c.id,
      kind: "demographic",
      label: c.label,
      field: c.field,
      op: c.op,
      value: c.value,
    };
  }
  const codes = c.expansions
    .filter((e) => e.code && e.system)
    .map((e) => ({ system: e.system!, code: e.code!, display: e.display }));
  return { id: c.id, kind: c.kind, label: c.label, codes };
}

export default function BuilderPage() {
  const router = useRouter();
  const [studies, setStudies] = useState<Study[]>([]);
  const [studyId, setStudyId] = useState<string>("");
  const [operator, setOperator] = useState<"AND" | "OR">("AND");

  const [kind, setKind] = useState<Kind>("condition");
  const [searchTerm, setSearchTerm] = useState("");
  const [includeSynonyms, setIncludeSynonyms] = useState(true);

  const [demoField, setDemoField] = useState("age");
  const [demoOp, setDemoOp] = useState(">=");
  const [demoValue, setDemoValue] = useState<string>("18");

  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStudies()
      .then((s) => {
        setStudies(s);
        if (s.length > 0) setStudyId(s[0].id);
      })
      .catch((e) => setError(describeError(e)));
  }, []);

  async function handleAdd() {
    setError(null);
    setMessage(null);
    if (kind === "demographic") {
      const value: string | number = demoField === "age" ? Number(demoValue) : demoValue;
      const label = `${demoField} ${demoOp} ${demoValue}`;
      setCriteria((prev) => [
        ...prev,
        { id: genId(), kind: "demographic", label, expansions: [], field: demoField, op: demoOp, value },
      ]);
      return;
    }
    if (!searchTerm.trim()) return;
    setLoading(true);
    try {
      const result = await expandTerm(searchTerm);
      const exps = includeSynonyms ? result.expansions : result.expansions.filter((e) => e.type === "code");
      setCriteria((prev) => [
        ...prev,
        { id: genId(), kind, label: result.normalizedTerm, expansions: exps },
      ]);
      setSearchTerm("");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveAndRun() {
    setError(null);
    setMessage(null);
    if (!studyId) return setError("Pick a study first.");
    if (criteria.length === 0) return setError("Add at least one criterion.");
    setBusy(true);
    try {
      const logic: CriteriaLogic = { operator, rules: criteria.map(toRule) };
      const cs = await createCriteriaSet(studyId, Date.now(), logic);
      if (!cs.id) throw new Error("Backend did not return criteria set id");
      const run = await runQuery(studyId, cs.id);
      router.push(`/results?run=${encodeURIComponent(run.runId)}`);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveOnly() {
    setError(null);
    setMessage(null);
    if (!studyId) return setError("Pick a study first.");
    if (criteria.length === 0) return setError("Add at least one criterion.");
    setBusy(true);
    try {
      const logic: CriteriaLogic = { operator, rules: criteria.map(toRule) };
      const cs = await createCriteriaSet(studyId, Date.now(), logic);
      setMessage(`Saved criteria set v${cs.version}.`);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  function removeCriterion(id: string) {
    setCriteria((prev) => prev.filter((c) => c.id !== id));
  }

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem", display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <label>Study</label>
          <select className="select" value={studyId} onChange={(e) => setStudyId(e.target.value)}>
            {studies.length === 0 ? <option value="">No studies — create one first</option> : null}
            {studies.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Combine rules with</label>
          <select className="select" value={operator} onChange={(e) => setOperator(e.target.value as "AND" | "OR")}>
            <option value="AND">AND (all must match)</option>
            <option value="OR">OR (any may match)</option>
          </select>
        </div>
      </div>

      <div className="grid grid-3">
        <section className="card">
          <h2>Add Criterion</h2>
          <div style={{ display: "grid", gap: "1rem" }}>
            <div>
              <label>Kind</label>
              <select className="select" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
                <option value="condition">Condition / Diagnosis</option>
                <option value="observation">Observation / Lab</option>
                <option value="demographic">Demographic</option>
              </select>
            </div>

            {kind !== "demographic" ? (
              <>
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
              </>
            ) : (
              <>
                <div>
                  <label>Field</label>
                  <select className="select" value={demoField} onChange={(e) => setDemoField(e.target.value)}>
                    <option value="age">age</option>
                    <option value="gender">gender</option>
                  </select>
                </div>
                <div>
                  <label>Operator</label>
                  <select className="select" value={demoOp} onChange={(e) => setDemoOp(e.target.value)}>
                    <option value="==">=</option>
                    <option value="!=">≠</option>
                    <option value=">">&gt;</option>
                    <option value=">=">≥</option>
                    <option value="<">&lt;</option>
                    <option value="<=">≤</option>
                  </select>
                </div>
                <div>
                  <label>Value</label>
                  <input className="input" value={demoValue} onChange={(e) => setDemoValue(e.target.value)} />
                </div>
              </>
            )}

            <button className="button" onClick={handleAdd} disabled={loading}>
              {loading ? "Expanding…" : "Add Criterion"}
            </button>
          </div>
        </section>

        <section className="card">
          <h2>Logic Summary</h2>
          {criteria.length === 0 ? (
            <p style={{ color: "#94a3b8" }}>No criteria added yet</p>
          ) : (
            <div style={{ display: "grid", gap: "0.75rem" }}>
              {criteria.map((c, i) => (
                <div key={c.id} className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong>
                      {i > 0 ? `${operator} ` : ""}{c.kind}: {c.label}
                    </strong>
                    <button
                      onClick={() => removeCriterion(c.id)}
                      style={{ background: "transparent", border: "none", color: "#b91c1c", cursor: "pointer" }}
                    >
                      remove
                    </button>
                  </div>
                  {c.expansions.length > 0 && (
                    <ul style={{ margin: "0.5rem 0 0 1rem", color: "#475569", fontSize: "0.85rem" }}>
                      {c.expansions.slice(0, 6).map((e, j) => (
                        <li key={j}>
                          {e.system ? `${e.system}: ${e.code} – ${e.display}` : e.display}
                        </li>
                      ))}
                      {c.expansions.length > 6 && <li>…and {c.expansions.length - 6} more</li>}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="card">
          <h2>Save &amp; Run</h2>
          <p style={{ color: "#475569", fontSize: "0.9rem" }}>
            Saves the rule set to the selected study and queues a query run against the connected FHIR server.
          </p>
          <div style={{ display: "grid", gap: "0.5rem", marginTop: "1rem" }}>
            <button className="button" onClick={handleSaveAndRun} disabled={busy}>
              {busy ? "Working…" : "Save & Run Query"}
            </button>
            <button
              className="button"
              style={{ background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
              onClick={handleSaveOnly}
              disabled={busy}
            >
              Save Only
            </button>
            <button
              className="button"
              style={{ background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
              onClick={() => setCriteria([])}
              disabled={busy}
            >
              Clear
            </button>
          </div>
          {message && <p style={{ color: "#166534", marginTop: "1rem" }}>{message}</p>}
          {error && <p style={{ color: "#b91c1c", marginTop: "1rem" }}>{error}</p>}
        </section>
      </div>
    </main>
  );
}
