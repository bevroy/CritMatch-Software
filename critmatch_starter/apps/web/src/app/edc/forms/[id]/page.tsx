"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  ApiError,
  createEdcEntry,
  deleteEdcForm,
  fetchEdcEntries,
  fetchEdcForm,
  fetchParticipants,
  updateEdcForm,
  type EdcEntry,
  type EdcField,
  type EdcFieldInput,
  type EdcForm,
  type EdcItemType,
  type Participant,
} from "../../../../lib/api";

const ITEM_TYPES: EdcItemType[] = [
  "string", "text", "integer", "decimal", "boolean", "date", "dateTime", "time",
  "choice", "open-choice", "quantity", "attachment", "group", "display",
];

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

function fieldToInput(f: EdcField): EdcFieldInput {
  return {
    key: f.key,
    label: f.label,
    item_type: f.item_type,
    position: f.position,
    required: f.required,
    options_json: f.options_json,
    fhir_mapping_json: f.fhir_mapping_json,
    validation_json: f.validation_json,
  };
}

export default function EdcFormPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [form, setForm] = useState<EdcForm | null>(null);
  const [draft, setDraft] = useState<EdcFieldInput[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [entries, setEntries] = useState<EdcEntry[]>([]);
  const [selParticipant, setSelParticipant] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setError(null);
    try {
      const f = await fetchEdcForm(id);
      setForm(f);
      setDraft(f.fields.map(fieldToInput));
      const [ps, es] = await Promise.all([
        fetchParticipants(f.study_id).catch(() => []),
        fetchEdcEntries(f.id).catch(() => []),
      ]);
      setParticipants(ps);
      setEntries(es);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  function updateDraft(idx: number, patch: Partial<EdcFieldInput>) {
    setDraft((d) => d.map((f, i) => i === idx ? { ...f, ...patch } : f));
  }

  function addField() {
    setDraft((d) => [...d, { key: `field_${d.length + 1}`, label: "Untitled", item_type: "string", required: false }]);
  }

  function removeField(idx: number) {
    setDraft((d) => d.filter((_, i) => i !== idx));
  }

  function moveField(idx: number, dir: -1 | 1) {
    setDraft((d) => {
      const j = idx + dir;
      if (j < 0 || j >= d.length) return d;
      const next = d.slice();
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  }

  async function saveFields() {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateEdcForm(form.id, { fields: draft });
      setForm(updated);
      setDraft(updated.fields.map(fieldToInput));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setSaving(false);
    }
  }

  async function setStatus(status: "draft" | "active" | "locked") {
    if (!form) return;
    try {
      const updated = await updateEdcForm(form.id, { status });
      setForm(updated);
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function deleteForm() {
    if (!form) return;
    if (!confirm(`Delete "${form.name}"? This removes all entries.`)) return;
    try {
      await deleteEdcForm(form.id);
      window.location.href = "/edc";
    } catch (e) {
      setError(describeError(e));
    }
  }

  async function newEntry() {
    if (!form || !selParticipant) return;
    try {
      const created = await createEdcEntry(form.id, selParticipant);
      window.location.href = `/edc/entries/${encodeURIComponent(created.id)}`;
    } catch (e) {
      setError(describeError(e));
    }
  }

  if (loading) return <main className="container"><div className="card">Loading…</div></main>;
  if (!form) return <main className="container"><div className="card">Not found.</div></main>;

  const locked = form.status === "locked";

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>{form.name}</h1>
          <p style={{ color: "#475569", margin: 0 }}>{form.description || "No description."}</p>
          <p style={{ color: "#94a3b8", margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
            v{form.version} · {form.status} · {form.id}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <Link href="/edc" className="button">Back</Link>
          {!locked && form.status !== "active" && (
            <button className="button" onClick={() => setStatus("active")}>Activate</button>
          )}
          {!locked && (
            <button className="button" onClick={() => setStatus("locked")}>Lock</button>
          )}
          <button className="button" onClick={deleteForm} style={{ background: "#fee2e2", color: "#991b1b" }}>
            Delete
          </button>
        </div>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      <section className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Fields ({draft.length})</h2>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="button" onClick={addField} disabled={locked}>Add field</button>
            <button className="button" onClick={saveFields} disabled={saving || locked}>
              {saving ? "Saving…" : "Save fields"}
            </button>
          </div>
        </div>

        {draft.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No fields yet.</p>
        ) : (
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {draft.map((f, idx) => (
              <FieldEditor
                key={idx}
                field={f}
                disabled={locked}
                onChange={(patch) => updateDraft(idx, patch)}
                onRemove={() => removeField(idx)}
                onUp={() => moveField(idx, -1)}
                onDown={() => moveField(idx, 1)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2>New entry</h2>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <select className="select" value={selParticipant} onChange={(e) => setSelParticipant(e.target.value)}>
            <option value="">— Select a participant —</option>
            {participants.map((p) => (
              <option key={p.id} value={p.id}>{p.subject_id} (patient {p.patient_id})</option>
            ))}
          </select>
          <button className="button" onClick={newEntry} disabled={!selParticipant || form.status === "draft"}>
            Start entry
          </button>
        </div>
        {form.status === "draft" && (
          <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            Activate the form before collecting data.
          </p>
        )}
        {participants.length === 0 && (
          <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: "0.5rem" }}>
            No participants yet. Open the study to enroll or promote from a cohort.
          </p>
        )}
      </section>

      <section className="card">
        <h2>Entries ({entries.length})</h2>
        {entries.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No entries yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Participant</th>
                <th>Status</th>
                <th>Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => {
                const p = participants.find((pp) => pp.id === e.participant_id);
                return (
                  <tr key={e.id}>
                    <td>{p?.subject_id ?? e.participant_id.slice(0, 8)}</td>
                    <td>{e.status}</td>
                    <td style={{ color: "#475569", fontSize: "0.85rem" }}>
                      {new Date(e.updated_at).toLocaleString()}
                    </td>
                    <td>
                      <Link href={`/edc/entries/${encodeURIComponent(e.id)}`} style={{ color: "#1d4ed8" }}>Open</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function FieldEditor({
  field, disabled, onChange, onRemove, onUp, onDown,
}: {
  field: EdcFieldInput;
  disabled: boolean;
  onChange: (patch: Partial<EdcFieldInput>) => void;
  onRemove: () => void;
  onUp: () => void;
  onDown: () => void;
}) {
  const m = field.fhir_mapping_json ?? null;
  const paramsText = m && m.params ? Object.entries(m.params).map(([k, v]) => `${k}=${v}`).join("\n") : "";

  function setParams(text: string) {
    const params: Record<string, string> = {};
    for (const line of text.split(/\n+/)) {
      const eq = line.indexOf("=");
      if (eq > 0) params[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
    }
    onChange({ fhir_mapping_json: { ...(m ?? { resource: "" }), params } });
  }

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 6, padding: "0.75rem", display: "grid", gap: "0.5rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <input className="input" placeholder="key" value={field.key}
               disabled={disabled} onChange={(e) => onChange({ key: e.target.value })}
               style={{ width: 160 }} />
        <input className="input" placeholder="label" value={field.label}
               disabled={disabled} onChange={(e) => onChange({ label: e.target.value })} />
        <select className="select" value={field.item_type ?? "string"}
                disabled={disabled} onChange={(e) => onChange({ item_type: e.target.value as EdcItemType })}>
          {ITEM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label style={{ fontSize: "0.85rem", color: "#475569", display: "flex", alignItems: "center", gap: "0.25rem" }}>
          <input type="checkbox" checked={!!field.required}
                 disabled={disabled} onChange={(e) => onChange({ required: e.target.checked })} />
          required
        </label>
        <button className="button" onClick={onUp} disabled={disabled} style={{ padding: "0.25rem 0.5rem" }}>↑</button>
        <button className="button" onClick={onDown} disabled={disabled} style={{ padding: "0.25rem 0.5rem" }}>↓</button>
        <button className="button" onClick={onRemove} disabled={disabled}
                style={{ padding: "0.25rem 0.5rem", background: "#fee2e2", color: "#991b1b" }}>×</button>
      </div>

      <details>
        <summary style={{ cursor: "pointer", color: "#475569", fontSize: "0.85rem" }}>FHIR mapping</summary>
        <div style={{ display: "grid", gap: "0.5rem", marginTop: "0.5rem" }}>
          <input className="input" placeholder="Resource (e.g. Observation, Patient)"
                 value={m?.resource ?? ""}
                 disabled={disabled}
                 onChange={(e) => onChange({ fhir_mapping_json: { ...(m ?? {}), resource: e.target.value } })} />
          <textarea className="input" placeholder="Search params (one per line, k=v)" rows={3}
                    value={paramsText} disabled={disabled}
                    onChange={(e) => setParams(e.target.value)} />
          <input className="input" placeholder="Extract path (e.g. valueQuantity.value)"
                 value={m?.extract ?? ""} disabled={disabled}
                 onChange={(e) => onChange({ fhir_mapping_json: { ...(m ?? { resource: "" }), extract: e.target.value } })} />
        </div>
      </details>
    </div>
  );
}
