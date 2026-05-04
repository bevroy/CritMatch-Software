"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  ApiError,
  expandTerm,
  fetchFeasibilityQuestionnaire,
  fetchFeasibilityRuns,
  runFeasibility,
  updateFeasibilityQuestionnaire,
  type Expansion,
  type FeasibilityLogic,
  type FeasibilityQuestion,
  type FeasibilityQuestionInput,
  type FeasibilityQuestionnaire,
  type FeasibilityRun,
} from "../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

type DraftKind = "condition" | "observation" | "demographic";

interface DraftQuestion {
  text: string;
  kind: DraftKind;
  searchTerm: string;
  field?: string;
  op?: string;
  value?: string;
  expansions: Expansion[];
}

function emptyDraft(): DraftQuestion {
  return {
    text: "",
    kind: "condition",
    searchTerm: "",
    field: "age",
    op: ">=",
    value: "18",
    expansions: [],
  };
}

function questionToInput(q: FeasibilityQuestion): FeasibilityQuestionInput {
  return { text: q.text, logic_json: q.logicJson, position: q.position };
}

function draftToInput(d: DraftQuestion, position: number): FeasibilityQuestionInput {
  let logic: FeasibilityLogic;
  if (d.kind === "demographic") {
    const value: string | number = d.field === "age" ? Number(d.value ?? "0") : d.value ?? "";
    logic = {
      operator: "AND",
      rules: [
        { id: `r-${position}`, kind: "demographic", field: d.field, op: d.op, value, label: d.text },
      ],
    };
  } else {
    const codes = d.expansions
      .filter((e) => e.code && e.system)
      .map((e) => ({ system: e.system!, code: e.code!, display: e.display }));
    logic = {
      operator: "AND",
      rules: [{ id: `r-${position}`, kind: d.kind, label: d.text, codes }],
    };
  }
  return { text: d.text || d.searchTerm || `${d.kind} question`, logic_json: logic, position };
}

interface PageParams { params: Promise<{ id: string }> }

export default function FeasibilityDetailPage({ params }: PageParams) {
  const { id } = use(params);
  const [fq, setFq] = useState<FeasibilityQuestionnaire | null>(null);
  const [runs, setRuns] = useState<FeasibilityRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<DraftQuestion>(emptyDraft());
  const [expanding, setExpanding] = useState(false);
  const [latestRun, setLatestRun] = useState<FeasibilityRun | null>(null);

  async function load() {
    setError(null);
    try {
      const [data, history] = await Promise.all([
        fetchFeasibilityQuestionnaire(id),
        fetchFeasibilityRuns(id, 10).catch(() => [] as FeasibilityRun[]),
      ]);
      setFq(data);
      setRuns(history);
      if (history.length > 0) setLatestRun(history[0]);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleExpand() {
    if (draft.kind === "demographic" || !draft.searchTerm.trim()) return;
    setExpanding(true);
    setError(null);
    try {
      const result = await expandTerm(draft.searchTerm.trim());
      setDraft((d) => ({
        ...d,
        text: d.text || result.normalizedTerm,
        expansions: result.expansions,
      }));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setExpanding(false);
    }
  }

  async function handleAddQuestion() {
    if (!fq) return;
    if (!draft.text.trim() && !draft.searchTerm.trim()) {
      setError("Add a question text or search term first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const existing: FeasibilityQuestionInput[] = fq.questions.map(questionToInput);
      const newInput = draftToInput(draft, existing.length);
      const updated = await updateFeasibilityQuestionnaire(fq.id, {
        questions: [...existing, newInput],
      });
      setFq(updated);
      setDraft(emptyDraft());
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleRemoveQuestion(qid: string) {
    if (!fq) return;
    setBusy(true);
    setError(null);
    try {
      const remaining = fq.questions
        .filter((q) => q.id !== qid)
        .map((q, i) => ({ ...questionToInput(q), position: i }));
      const updated = await updateFeasibilityQuestionnaire(fq.id, { questions: remaining });
      setFq(updated);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleRun() {
    if (!fq) return;
    if (fq.questions.length === 0) {
      setError("Add at least one question first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await runFeasibility(fq.id);
      setLatestRun(result);
      const history = await fetchFeasibilityRuns(fq.id, 10);
      setRuns(history);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="container"><div className="card">Loading…</div></main>;
  }
  if (!fq) {
    return (
      <main className="container">
        <div className="card" style={{ color: "#b91c1c" }}>{error ?? "Not found"}</div>
        <p style={{ marginTop: "1rem" }}><Link href="/feasibility">← Back</Link></p>
      </main>
    );
  }

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <Link href="/feasibility" style={{ color: "#475569" }}>← All questionnaires</Link>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h1 style={{ marginBottom: "0.25rem" }}>{fq.name}</h1>
            <p style={{ color: "#475569", margin: 0 }}>{fq.description || "No description."}</p>
            {fq.studyId && (
              <p style={{ color: "#94a3b8", margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                Linked to study{" "}
                <Link href={`/studies/${fq.studyId}`} style={{ color: "#1d4ed8" }}>
                  {fq.studyId.slice(0, 8)}…
                </Link>{" "}
                — runs are scoped to its investigators (if any).
              </p>
            )}
          </div>
          <button className="button" onClick={handleRun} disabled={busy}>
            {busy ? "Running…" : "Run Questionnaire"}
          </button>
        </div>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2>Questions ({fq.questions.length})</h2>
        {fq.questions.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No questions yet.</p>
        ) : (
          <table>
            <thead>
              <tr><th>#</th><th>Question</th><th>Rules</th><th></th></tr>
            </thead>
            <tbody>
              {fq.questions.map((q, i) => (
                <tr key={q.id}>
                  <td>{i + 1}</td>
                  <td>{q.text}</td>
                  <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                    {(q.logicJson?.rules?.length ?? 0)} rule(s)
                  </td>
                  <td>
                    <button
                      onClick={() => handleRemoveQuestion(q.id)}
                      disabled={busy}
                      style={{ background: "transparent", border: "1px solid #fecaca", color: "#b91c1c", padding: "0.2rem 0.5rem", borderRadius: "0.5rem", cursor: "pointer", fontSize: "0.8rem" }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2>Add a question</h2>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <div>
            <label>Question text</label>
            <input
              className="input"
              placeholder='e.g. "How many patients with type 2 diabetes?"'
              value={draft.text}
              onChange={(e) => setDraft((d) => ({ ...d, text: e.target.value }))}
            />
          </div>
          <div>
            <label>Kind</label>
            <select
              className="select"
              value={draft.kind}
              onChange={(e) => setDraft((d) => ({ ...d, kind: e.target.value as DraftKind, expansions: [] }))}
            >
              <option value="condition">Condition / Diagnosis</option>
              <option value="observation">Observation / Lab</option>
              <option value="demographic">Demographic</option>
            </select>
          </div>

          {draft.kind !== "demographic" ? (
            <>
              <div>
                <label>Search term or code</label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <input
                    className="input"
                    placeholder="e.g. type 2 diabetes or E11"
                    value={draft.searchTerm}
                    onChange={(e) => setDraft((d) => ({ ...d, searchTerm: e.target.value }))}
                    style={{ flex: 1 }}
                  />
                  <button className="button" onClick={handleExpand} disabled={expanding}>
                    {expanding ? "…" : "Expand"}
                  </button>
                </div>
              </div>
              {draft.expansions.length > 0 && (
                <ul style={{ color: "#475569", fontSize: "0.85rem", margin: 0, paddingLeft: "1.25rem" }}>
                  {draft.expansions.slice(0, 8).map((e, j) => (
                    <li key={j}>{e.system ? `${e.system}: ${e.code} – ${e.display}` : e.display}</li>
                  ))}
                  {draft.expansions.length > 8 && <li>…and {draft.expansions.length - 8} more</li>}
                </ul>
              )}
            </>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem" }}>
              <div>
                <label>Field</label>
                <select className="select" value={draft.field} onChange={(e) => setDraft((d) => ({ ...d, field: e.target.value }))}>
                  <option value="age">age</option>
                  <option value="gender">gender</option>
                </select>
              </div>
              <div>
                <label>Operator</label>
                <select className="select" value={draft.op} onChange={(e) => setDraft((d) => ({ ...d, op: e.target.value }))}>
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
                <input className="input" value={draft.value} onChange={(e) => setDraft((d) => ({ ...d, value: e.target.value }))} />
              </div>
            </div>
          )}

          <button className="button" onClick={handleAddQuestion} disabled={busy}>
            {busy ? "Saving…" : "Add Question"}
          </button>
        </div>
      </section>

      {latestRun && (
        <section className="card" style={{ marginBottom: "1rem" }}>
          <h2>Latest Run</h2>
          <p style={{ color: "#475569", margin: "0 0 0.5rem" }}>
            <strong>Status:</strong> {latestRun.status}
            {latestRun.totalPatients != null && (
              <>
                {" · "}
                <strong>Total unique patients (union):</strong> {latestRun.totalPatients}
              </>
            )}
            {latestRun.executionMs != null && (
              <>
                {" · "}
                <strong>Time:</strong> {latestRun.executionMs} ms
              </>
            )}
          </p>
          {latestRun.errorMessage && (
            <p style={{ color: "#b91c1c", margin: 0 }}>Error: {latestRun.errorMessage}</p>
          )}
          {latestRun.results.length > 0 && (
            <table>
              <thead>
                <tr><th>Question</th><th>Count</th></tr>
              </thead>
              <tbody>
                {latestRun.results.map((r) => (
                  <tr key={r.questionId}>
                    <td>{r.questionText}</td>
                    <td><strong>{r.count}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {runs.length > 1 && (
        <section className="card">
          <h2>Run History ({runs.length})</h2>
          <table>
            <thead>
              <tr><th>When</th><th>Status</th><th>Total Patients</th><th>Time</th></tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td style={{ color: "#475569", fontSize: "0.85rem" }}>{new Date(r.createdAt).toLocaleString()}</td>
                  <td>{r.status}</td>
                  <td>{r.totalPatients ?? "—"}</td>
                  <td>{r.executionMs != null ? `${r.executionMs} ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
