"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  fetchEdcEntry,
  fetchEdcEntryHistory,
  fetchEdcForm,
  fetchParticipants,
  pullEdcEntry,
  signEdcEntry,
  updateEdcEntry,
  type EdcEntry,
  type EdcField,
  type EdcForm,
  type EntryFieldValue,
  type EntryHistoryItem,
  type Participant,
} from "../../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

type DraftMap = Record<string, { value: unknown; reason: string; source: string; ref: string | null }>;

function initDraft(entry: EdcEntry): DraftMap {
  const map: DraftMap = {};
  for (const v of entry.values) {
    map[v.field_id] = { value: v.value, reason: "", source: v.source, ref: v.fhir_source_ref };
  }
  return map;
}

export default function EntryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [entry, setEntry] = useState<EdcEntry | null>(null);
  const [form, setForm] = useState<EdcForm | null>(null);
  const [participant, setParticipant] = useState<Participant | null>(null);
  const [draft, setDraft] = useState<DraftMap>({});
  const [history, setHistory] = useState<EntryHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setError(null);
    try {
      const e = await fetchEdcEntry(id);
      setEntry(e);
      setDraft(initDraft(e));
      const f = await fetchEdcForm(e.form_id);
      setForm(f);
      const ps = await fetchParticipants(f.study_id).catch(() => []);
      setParticipant(ps.find((pp) => pp.id === e.participant_id) ?? null);
      const h = await fetchEdcEntryHistory(e.id).catch(() => []);
      setHistory(h);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  function setVal(fieldId: string, value: unknown) {
    setDraft((d) => ({
      ...d,
      [fieldId]: {
        value,
        reason: d[fieldId]?.reason ?? "",
        source: "manual",
        ref: null,
      },
    }));
  }

  function setReason(fieldId: string, reason: string) {
    setDraft((d) => ({
      ...d,
      [fieldId]: { ...(d[fieldId] ?? { value: "", source: "manual", ref: null }), reason },
    }));
  }

  async function saveAll() {
    if (!entry) return;
    setBusy(true);
    setError(null);
    try {
      const values: NonNullable<Parameters<typeof updateEdcEntry>[1]["values"]> = [];
      for (const f of form?.fields ?? []) {
        const d = draft[f.id];
        if (d === undefined) continue;
        const original = entry.values.find((v) => v.field_id === f.id);
        if (original && JSON.stringify(original.value) === JSON.stringify(d.value)) continue;
        values.push({
          field_id: f.id,
          value: d.value,
          source: "manual",
          reason_for_change: d.reason || undefined,
        });
      }
      if (values.length === 0) { setBusy(false); return; }
      const updated = await updateEdcEntry(entry.id, { values });
      setEntry(updated);
      setDraft(initDraft(updated));
      const h = await fetchEdcEntryHistory(entry.id).catch(() => []);
      setHistory(h);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function markComplete() {
    if (!entry) return;
    setBusy(true);
    try {
      const updated = await updateEdcEntry(entry.id, { values: [], status: "complete" });
      setEntry(updated);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function pullAll() {
    if (!entry) return;
    setBusy(true);
    setError(null);
    try {
      const results = await pullEdcEntry(entry.id);
      const errs = results.filter((r) => r.error);
      if (errs.length > 0) setError(`${errs.length} field(s) failed: ${errs.map((e) => e.field_key).join(", ")}`);
      const refreshed = await fetchEdcEntry(entry.id);
      setEntry(refreshed);
      setDraft(initDraft(refreshed));
      const h = await fetchEdcEntryHistory(entry.id).catch(() => []);
      setHistory(h);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function sign() {
    if (!entry) return;
    const phrase = window.prompt("Type 'I agree' to sign this entry:");
    if (phrase === null) return;
    setBusy(true);
    try {
      await signEdcEntry(entry.id, { meaning: "author", confirmation: phrase });
      const refreshed = await fetchEdcEntry(entry.id);
      setEntry(refreshed);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  const fieldsById = useMemo(() => {
    const m: Record<string, EdcField> = {};
    for (const f of form?.fields ?? []) m[f.id] = f;
    return m;
  }, [form]);

  if (loading) return <main className="container"><div className="card">Loading…</div></main>;
  if (!entry || !form) return <main className="container"><div className="card">Not found.</div></main>;

  const locked = entry.status === "locked";

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>{form.name}</h1>
          <p style={{ color: "#475569", margin: 0 }}>
            {participant ? `Subject ${participant.subject_id} (patient ${participant.patient_id})` : entry.participant_id}
          </p>
          <p style={{ color: "#94a3b8", margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
            Status: {entry.status} · v{form.version}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <Link href={`/edc/forms/${encodeURIComponent(form.id)}`} className="button">Back</Link>
          <button className="button" onClick={pullAll} disabled={busy || locked}>Pull from EMR</button>
          <button className="button" onClick={saveAll} disabled={busy || locked}>Save</button>
          {entry.status === "in_progress" && (
            <button className="button" onClick={markComplete} disabled={busy}>Mark complete</button>
          )}
          {(entry.status === "complete" || entry.status === "locked") && entry.signatures.length === 0 && (
            <button className="button" onClick={sign} disabled={busy}>Sign &amp; lock</button>
          )}
        </div>
      </div>

      {error && <div className="card" style={{ marginBottom: "1rem", color: "#b91c1c" }}>{error}</div>}

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2>Data points</h2>
        {form.fields.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No fields defined.</p>
        ) : (
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {form.fields.map((f) => {
              const d = draft[f.id];
              const original = entry.values.find((v) => v.field_id === f.id);
              const changed = d !== undefined && original && JSON.stringify(original.value) !== JSON.stringify(d.value);
              return (
                <div key={f.id} style={{ display: "grid", gap: "0.25rem" }}>
                  <label style={{ fontWeight: 500 }}>
                    {f.label} {f.required && <span style={{ color: "#b91c1c" }}>*</span>}
                    <span style={{ color: "#94a3b8", marginLeft: "0.5rem", fontSize: "0.8rem" }}>{f.item_type}</span>
                  </label>
                  <FieldInput field={f} value={d?.value} disabled={locked}
                              onChange={(v) => setVal(f.id, v)} />
                  {original?.source === "fhir_pull" && (
                    <p style={{ color: "#0369a1", fontSize: "0.75rem", margin: 0 }}>
                      pulled from {original.fhir_source_ref}
                    </p>
                  )}
                  {original && changed && (
                    <input className="input" placeholder="Reason for change (required for audit)"
                           value={d?.reason ?? ""} disabled={locked}
                           onChange={(e) => setReason(f.id, e.target.value)} />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {entry.signatures.length > 0 && (
        <section className="card" style={{ marginBottom: "1rem" }}>
          <h2>Signatures</h2>
          <ul style={{ margin: 0, paddingLeft: "1rem" }}>
            {entry.signatures.map((s) => (
              <li key={s.id} style={{ fontSize: "0.85rem", color: "#475569" }}>
                <strong>{s.meaning}</strong> · {new Date(s.signed_at).toLocaleString()} · hash {s.signature_hash.slice(0, 12)}…
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h2>Change history ({history.length})</h2>
        {history.length === 0 ? (
          <p style={{ color: "#94a3b8" }}>No changes recorded.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Field</th>
                <th>Old → New</th>
                <th>Source</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td style={{ fontSize: "0.8rem", color: "#475569" }}>{new Date(h.changedAt).toLocaleString()}</td>
                  <td>{fieldsById[h.fieldId]?.label ?? h.fieldKey}</td>
                  <td style={{ fontSize: "0.85rem" }}>
                    <code>{JSON.stringify(h.oldValue)}</code> → <code>{JSON.stringify(h.newValue)}</code>
                  </td>
                  <td style={{ fontSize: "0.8rem" }}>{h.oldSource ?? "—"} → {h.newSource ?? "—"}</td>
                  <td style={{ fontSize: "0.85rem" }}>{h.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function FieldInput({ field, value, disabled, onChange }: {
  field: EdcField;
  value: unknown;
  disabled: boolean;
  onChange: (v: unknown) => void;
}) {
  const t = field.item_type;
  if (t === "boolean") {
    return (
      <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <input type="checkbox" checked={!!value} disabled={disabled}
               onChange={(e) => onChange(e.target.checked)} />
        <span>{value ? "Yes" : "No"}</span>
      </label>
    );
  }
  if (t === "text") {
    return (
      <textarea className="input" rows={3} value={(value as string) ?? ""}
                disabled={disabled} onChange={(e) => onChange(e.target.value)} />
    );
  }
  if (t === "integer" || t === "decimal" || t === "quantity") {
    return (
      <input type="number" className="input" value={(value as number | string | undefined) ?? ""}
             disabled={disabled}
             onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
             step={t === "integer" ? 1 : "any"} />
    );
  }
  if (t === "date") {
    return (
      <input type="date" className="input" value={(value as string) ?? ""} disabled={disabled}
             onChange={(e) => onChange(e.target.value)} />
    );
  }
  if (t === "dateTime") {
    return (
      <input type="datetime-local" className="input" value={(value as string) ?? ""} disabled={disabled}
             onChange={(e) => onChange(e.target.value)} />
    );
  }
  if (t === "time") {
    return (
      <input type="time" className="input" value={(value as string) ?? ""} disabled={disabled}
             onChange={(e) => onChange(e.target.value)} />
    );
  }
  if (t === "choice" || t === "open-choice") {
    const opts = (field.options_json as { choices?: string[] } | null)?.choices ?? [];
    if (opts.length === 0) {
      return (
        <input className="input" value={(value as string) ?? ""} disabled={disabled}
               onChange={(e) => onChange(e.target.value)}
               placeholder="No choices configured (open-choice fallback)" />
      );
    }
    return (
      <select className="select" value={(value as string) ?? ""} disabled={disabled}
              onChange={(e) => onChange(e.target.value)}>
        <option value="">— Select —</option>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  if (t === "display") {
    return <p style={{ color: "#475569" }}>{field.label}</p>;
  }
  // string, attachment, group, fallback
  return (
    <input className="input" value={(value as string) ?? ""} disabled={disabled}
           onChange={(e) => onChange(e.target.value)} />
  );
}
