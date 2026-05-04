"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createCtfmsAccrual,
  createCtfmsBudget,
  createCtfmsInvoice,
  createCtfmsStipend,
  fetchCtfmsAccruals,
  fetchCtfmsBudget,
  fetchCtfmsBudgets,
  fetchCtfmsFinanceSummary,
  fetchCtfmsInvoices,
  fetchCtfmsPayments,
  fetchCtfmsStipends,
  fetchEdcForms,
  fetchParticipants,
  formatMoney,
  recordCtfmsPayment,
  updateCtfmsBudget,
  updateCtfmsInvoice,
  updateCtfmsStipend,
  type CtfmsAccrual,
  type CtfmsBudget,
  type CtfmsBudgetItemInput,
  type CtfmsBudgetItemType,
  type CtfmsBudgetSummary,
  type CtfmsFinanceSummary,
  type CtfmsInvoice,
  type CtfmsPayment,
  type CtfmsStipend,
  type EdcForm,
  type EdcFormSummary,
  type Participant,
} from "../../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  return (e as Error).message ?? "Unknown error";
}

const ITEM_TYPES: CtfmsBudgetItemType[] = [
  "per_visit",
  "per_procedure",
  "fixed_milestone",
  "passthrough",
  "overhead",
  "patient_stipend",
];

type Tab = "budget" | "accruals" | "invoices" | "payments" | "stipends";

export default function CtfmsStudyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: studyId } = use(params);
  const [tab, setTab] = useState<Tab>("budget");
  const [summary, setSummary] = useState<CtfmsFinanceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadSummary() {
    try {
      setSummary(await fetchCtfmsFinanceSummary(studyId));
    } catch (e) {
      setError(describeError(e));
    }
  }
  useEffect(() => { loadSummary(); }, [studyId]);

  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <div>
          <p style={{ marginBottom: "0.25rem" }}>
            <Link href="/ctfms">← Finance</Link>
          </p>
          <h1>Study finance</h1>
        </div>
        <Link className="button button-secondary" href={`/studies/${studyId}`}>Open study</Link>
      </div>

      {summary && (
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: "0.5rem",
            marginBottom: "1rem",
          }}
        >
          <Card label="Accrued (open)" value={formatMoney(summary.accruedOpen)} />
          <Card label="Accrued (invoiced)" value={formatMoney(summary.accruedInvoiced)} />
          <Card label="Invoiced" value={formatMoney(summary.invoiceTotal)} />
          <Card label="Paid" value={formatMoney(summary.paid)} accent="#16a34a" />
          <Card label="Outstanding" value={formatMoney(summary.outstanding)} accent="#dc2626" />
          <Card label="Stipends pending" value={formatMoney(summary.stipendsPending)} />
        </section>
      )}

      {error && <div className="error">{error}</div>}

      <nav style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid #e2e8f0", marginBottom: "1rem" }}>
        {(["budget", "accruals", "invoices", "payments", "stipends"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "0.5rem 0.75rem",
              border: "none",
              background: "transparent",
              borderBottom: tab === t ? "2px solid #0f172a" : "2px solid transparent",
              fontWeight: tab === t ? 600 : 400,
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "budget" && <BudgetTab studyId={studyId} onChange={loadSummary} />}
      {tab === "accruals" && <AccrualsTab studyId={studyId} onChange={loadSummary} />}
      {tab === "invoices" && <InvoicesTab studyId={studyId} onChange={loadSummary} />}
      {tab === "payments" && <PaymentsTab studyId={studyId} onChange={loadSummary} />}
      {tab === "stipends" && <StipendsTab studyId={studyId} onChange={loadSummary} />}
    </main>
  );
}

// ---------------------------------------------------------------------------

function BudgetTab({ studyId, onChange }: { studyId: string; onChange: () => void }) {
  const [budgets, setBudgets] = useState<CtfmsBudgetSummary[]>([]);
  const [active, setActive] = useState<CtfmsBudget | null>(null);
  const [forms, setForms] = useState<EdcFormSummary[]>([]);
  const [formDetails, setFormDetails] = useState<Record<string, EdcForm | null>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCurrency, setNewCurrency] = useState("USD");

  async function load() {
    setErr(null);
    try {
      const [bs, fs] = await Promise.all([
        fetchCtfmsBudgets(studyId),
        fetchEdcForms(studyId).catch(() => [] as EdcFormSummary[]),
      ]);
      setBudgets(bs);
      setForms(fs);
      const first = bs.find((b) => b.status === "active") ?? bs[0];
      if (first) setActive(await fetchCtfmsBudget(first.id));
      else setActive(null);
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, [studyId]);

  async function loadFormDetail(formId: string) {
    if (formDetails[formId] !== undefined) return;
    try {
      const detail = await import("../../../../lib/api").then((m) => m.fetchEdcForm(formId));
      setFormDetails((prev) => ({ ...prev, [formId]: detail }));
    } catch {
      setFormDetails((prev) => ({ ...prev, [formId]: null }));
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    try {
      const created = await createCtfmsBudget({
        study_id: studyId, name: newName.trim(), currency: newCurrency, items: [],
      });
      setNewName("");
      setShowCreate(false);
      await load();
      setActive(await fetchCtfmsBudget(created.id));
    } catch (e) {
      setErr(describeError(e));
    }
  }

  async function saveBudget(updates: Partial<CtfmsBudget>) {
    if (!active) return;
    try {
      const next = await updateCtfmsBudget(active.id, updates as any);
      setActive(next);
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  return (
    <section>
      {err && <div className="error">{err}</div>}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <label>Budget version: </label>
          <select
            value={active?.id ?? ""}
            onChange={async (e) => setActive(e.target.value ? await fetchCtfmsBudget(e.target.value) : null)}
          >
            <option value="">— none —</option>
            {budgets.map((b) => (
              <option key={b.id} value={b.id}>v{b.version} · {b.name} ({b.status})</option>
            ))}
          </select>
        </div>
        <button className="button" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? "Cancel" : "New budget"}
        </button>
      </div>

      {showCreate && (
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
          <input placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <input placeholder="Currency" value={newCurrency} onChange={(e) => setNewCurrency(e.target.value)} style={{ width: 100 }} />
          <button className="button" onClick={handleCreate}>Create</button>
        </div>
      )}

      {loading ? <p>Loading…</p> : null}
      {!loading && !active && <p style={{ color: "#475569" }}>No budget yet.</p>}

      {active && (
        <BudgetEditor
          budget={active}
          forms={forms}
          formDetails={formDetails}
          loadFormDetail={loadFormDetail}
          onSave={saveBudget}
        />
      )}
    </section>
  );
}

function BudgetEditor({
  budget, forms, formDetails, loadFormDetail, onSave,
}: {
  budget: CtfmsBudget;
  forms: EdcFormSummary[];
  formDetails: Record<string, EdcForm | null>;
  loadFormDetail: (id: string) => void;
  onSave: (updates: any) => Promise<void>;
}) {
  const [items, setItems] = useState<CtfmsBudgetItemInput[]>(() =>
    budget.items.map((i) => ({
      name: i.name, code: i.code ?? undefined, description: i.description ?? undefined,
      item_type: i.item_type, unit_price: i.unit_price, currency: i.currency,
      edc_form_id: i.edc_form_id, edc_field_id: i.edc_field_id,
      auto_accrue: i.auto_accrue, active: i.active,
    })),
  );
  const [name, setName] = useState(budget.name);
  const [sponsor, setSponsor] = useState(budget.sponsor ?? "");
  const [contract, setContract] = useState(budget.contract_number ?? "");
  const [notes, setNotes] = useState(budget.notes ?? "");
  const [status, setStatus] = useState(budget.status);

  useEffect(() => {
    items.forEach((i) => i.edc_form_id && loadFormDetail(i.edc_form_id));
  }, [items, loadFormDetail]);

  function update(idx: number, patch: Partial<CtfmsBudgetItemInput>) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }
  function remove(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }
  function add() {
    setItems((prev) => [
      ...prev,
      { name: "New item", item_type: "per_visit", unit_price: 0, currency: budget.currency, auto_accrue: true, active: true },
    ]);
  }

  return (
    <div>
      <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", marginBottom: "0.75rem" }}>
        <label>Name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>Sponsor<input value={sponsor} onChange={(e) => setSponsor(e.target.value)} /></label>
        <label>Contract #<input value={contract} onChange={(e) => setContract(e.target.value)} /></label>
        <label>Status
          <select value={status} onChange={(e) => setStatus(e.target.value as any)}>
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="archived">archived</option>
          </select>
        </label>
      </div>
      <label style={{ display: "block", marginBottom: "0.5rem" }}>
        Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} style={{ width: "100%" }} />
      </label>

      <h3>Line items</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Code</th><th>Name</th><th>Type</th><th>Unit price (cents)</th><th>Currency</th>
            <th>EDC form</th><th>EDC field</th><th>Auto</th><th>Active</th><th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, idx) => {
            const form = it.edc_form_id ? formDetails[it.edc_form_id] : null;
            return (
              <tr key={idx}>
                <td><input value={it.code ?? ""} onChange={(e) => update(idx, { code: e.target.value })} style={{ width: 80 }} /></td>
                <td><input value={it.name} onChange={(e) => update(idx, { name: e.target.value })} /></td>
                <td>
                  <select value={it.item_type} onChange={(e) => update(idx, { item_type: e.target.value as CtfmsBudgetItemType })}>
                    {ITEM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </td>
                <td><input type="number" value={it.unit_price} onChange={(e) => update(idx, { unit_price: Number(e.target.value) })} style={{ width: 110 }} /></td>
                <td><input value={it.currency} onChange={(e) => update(idx, { currency: e.target.value })} style={{ width: 70 }} /></td>
                <td>
                  <select value={it.edc_form_id ?? ""} onChange={(e) => update(idx, { edc_form_id: e.target.value || null, edc_field_id: null })}>
                    <option value="">—</option>
                    {forms.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </td>
                <td>
                  <select
                    value={it.edc_field_id ?? ""}
                    onChange={(e) => update(idx, { edc_field_id: e.target.value || null })}
                    disabled={!form}
                  >
                    <option value="">—</option>
                    {form?.fields.map((fld) => <option key={fld.id} value={fld.id}>{fld.label}</option>)}
                  </select>
                </td>
                <td><input type="checkbox" checked={it.auto_accrue ?? true} onChange={(e) => update(idx, { auto_accrue: e.target.checked })} /></td>
                <td><input type="checkbox" checked={it.active ?? true} onChange={(e) => update(idx, { active: e.target.checked })} /></td>
                <td><button className="button button-secondary" onClick={() => remove(idx)}>×</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button className="button button-secondary" onClick={add} style={{ marginTop: "0.5rem" }}>+ Add line</button>

      <div style={{ marginTop: "1rem" }}>
        <button
          className="button"
          onClick={() =>
            onSave({
              name, sponsor: sponsor || null, contract_number: contract || null,
              notes: notes || null, status, items,
            })
          }
        >
          Save budget
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function AccrualsTab({ studyId, onChange }: { studyId: string; onChange: () => void }) {
  const [rows, setRows] = useState<CtfmsAccrual[]>([]);
  const [budgets, setBudgets] = useState<CtfmsBudget[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");

  // Add form
  const [budgetId, setBudgetId] = useState("");
  const [itemId, setItemId] = useState("");
  const [participantId, setParticipantId] = useState("");
  const [qty, setQty] = useState(1);

  const selectedBudget = useMemo(() => budgets.find((b) => b.id === budgetId), [budgets, budgetId]);

  async function load() {
    try {
      const [list, bs, pl] = await Promise.all([
        fetchCtfmsAccruals(studyId),
        fetchCtfmsBudgets(studyId).then((bs) => Promise.all(bs.map((b) => fetchCtfmsBudget(b.id)))),
        fetchParticipants(studyId).catch(() => [] as Participant[]),
      ]);
      setRows(list);
      setBudgets(bs);
      setParticipants(pl);
      if (!budgetId && bs.length > 0) setBudgetId(bs.find((b) => b.status === "active")?.id ?? bs[0].id);
    } catch (e) {
      setErr(describeError(e));
    }
  }
  useEffect(() => { load(); }, [studyId]);

  async function add() {
    if (!budgetId || !itemId) return;
    try {
      await createCtfmsAccrual(budgetId, {
        budget_item_id: itemId,
        participant_id: participantId || undefined,
        quantity: qty,
      });
      setItemId("");
      setQty(1);
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  const filtered = filter ? rows.filter((r) => r.status === filter) : rows;

  return (
    <section>
      {err && <div className="error">{err}</div>}

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
        <select value={budgetId} onChange={(e) => { setBudgetId(e.target.value); setItemId(""); }}>
          <option value="">— budget —</option>
          {budgets.map((b) => <option key={b.id} value={b.id}>v{b.version} · {b.name}</option>)}
        </select>
        <select value={itemId} onChange={(e) => setItemId(e.target.value)} disabled={!selectedBudget}>
          <option value="">— line item —</option>
          {selectedBudget?.items.filter((i) => i.active).map((i) => (
            <option key={i.id} value={i.id}>{i.name} · {formatMoney(i.unit_price, i.currency)}</option>
          ))}
        </select>
        <select value={participantId} onChange={(e) => setParticipantId(e.target.value)}>
          <option value="">— participant (optional) —</option>
          {participants.map((p) => <option key={p.id} value={p.id}>{p.subject_id}</option>)}
        </select>
        <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} style={{ width: 70 }} />
        <button className="button" onClick={add} disabled={!itemId}>Add accrual</button>
      </div>

      <div style={{ marginBottom: "0.5rem" }}>
        Filter:{" "}
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">all</option>
          <option value="accrued">accrued</option>
          <option value="invoiced">invoiced</option>
          <option value="void">void</option>
        </select>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>When</th><th>Item</th><th>Participant</th><th>Qty</th>
            <th style={{ textAlign: "right" }}>Amount</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((a) => {
            const item = budgets.flatMap((b) => b.items).find((i) => i.id === a.budget_item_id);
            const part = participants.find((p) => p.id === a.participant_id);
            return (
              <tr key={a.id}>
                <td>{new Date(a.accrued_at).toLocaleString()}</td>
                <td>{item?.name ?? a.budget_item_id.slice(0, 8)}</td>
                <td>{part?.subject_id ?? "—"}</td>
                <td>{a.quantity}</td>
                <td style={{ textAlign: "right" }}>{formatMoney(a.amount, a.currency)}</td>
                <td>{a.status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

// ---------------------------------------------------------------------------

function InvoicesTab({ studyId, onChange }: { studyId: string; onChange: () => void }) {
  const [invoices, setInvoices] = useState<CtfmsInvoice[]>([]);
  const [openAccruals, setOpenAccruals] = useState<CtfmsAccrual[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const [inv, acc] = await Promise.all([
        fetchCtfmsInvoices(studyId),
        fetchCtfmsAccruals(studyId, "accrued"),
      ]);
      setInvoices(inv);
      setOpenAccruals(acc);
    } catch (e) {
      setErr(describeError(e));
    }
  }
  useEffect(() => { load(); }, [studyId]);

  async function createInvoice() {
    if (selected.size === 0) return;
    try {
      await createCtfmsInvoice(studyId, { accrual_ids: Array.from(selected), notes: notes || undefined });
      setSelected(new Set());
      setNotes("");
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  async function setStatus(inv: CtfmsInvoice, status: CtfmsInvoice["status"]) {
    try {
      await updateCtfmsInvoice(inv.id, { status });
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const selectedTotal = openAccruals
    .filter((a) => selected.has(a.id))
    .reduce((s, a) => s + a.amount, 0);

  return (
    <section>
      {err && <div className="error">{err}</div>}

      <h3>Open accruals</h3>
      {openAccruals.length === 0 ? (
        <p style={{ color: "#475569" }}>No open accruals to invoice.</p>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr><th></th><th>When</th><th>Qty</th><th style={{ textAlign: "right" }}>Amount</th><th>Currency</th></tr>
            </thead>
            <tbody>
              {openAccruals.map((a) => (
                <tr key={a.id}>
                  <td><input type="checkbox" checked={selected.has(a.id)} onChange={() => toggle(a.id)} /></td>
                  <td>{new Date(a.accrued_at).toLocaleDateString()}</td>
                  <td>{a.quantity}</td>
                  <td style={{ textAlign: "right" }}>{formatMoney(a.amount, a.currency)}</td>
                  <td>{a.currency}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <strong>Selected total: {formatMoney(selectedTotal)}</strong>
            <input placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
            <button className="button" onClick={createInvoice} disabled={selected.size === 0}>
              Create invoice
            </button>
          </div>
        </>
      )}

      <h3 style={{ marginTop: "1.5rem" }}>Invoices</h3>
      <table className="table">
        <thead>
          <tr><th>#</th><th>Issued</th><th style={{ textAlign: "right" }}>Total</th><th style={{ textAlign: "right" }}>Paid</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id}>
              <td>{inv.number}</td>
              <td>{new Date(inv.issued_at).toLocaleDateString()}</td>
              <td style={{ textAlign: "right" }}>{formatMoney(inv.total, inv.currency)}</td>
              <td style={{ textAlign: "right" }}>{formatMoney(inv.amount_paid, inv.currency)}</td>
              <td>{inv.status}</td>
              <td>
                {inv.status === "draft" && (
                  <button className="button button-secondary" onClick={() => setStatus(inv, "sent")}>Mark sent</button>
                )}
                {inv.status !== "void" && inv.status !== "paid" && (
                  <button className="button button-secondary" onClick={() => setStatus(inv, "void")} style={{ marginLeft: 4 }}>
                    Void
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

// ---------------------------------------------------------------------------

function PaymentsTab({ studyId, onChange }: { studyId: string; onChange: () => void }) {
  const [payments, setPayments] = useState<CtfmsPayment[]>([]);
  const [invoices, setInvoices] = useState<CtfmsInvoice[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState("");
  const [amount, setAmount] = useState(0);
  const [currency, setCurrency] = useState("USD");
  const [reference, setReference] = useState("");

  async function load() {
    try {
      const [pl, inv] = await Promise.all([fetchCtfmsPayments(studyId), fetchCtfmsInvoices(studyId)]);
      setPayments(pl);
      setInvoices(inv);
    } catch (e) {
      setErr(describeError(e));
    }
  }
  useEffect(() => { load(); }, [studyId]);

  async function record() {
    try {
      await recordCtfmsPayment(studyId, {
        invoice_id: invoiceId || undefined,
        amount, currency, reference: reference || undefined,
      });
      setAmount(0);
      setReference("");
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  return (
    <section>
      {err && <div className="error">{err}</div>}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem", alignItems: "center" }}>
        <select value={invoiceId} onChange={(e) => {
          setInvoiceId(e.target.value);
          const inv = invoices.find((i) => i.id === e.target.value);
          if (inv) {
            setCurrency(inv.currency);
            setAmount(inv.total - inv.amount_paid);
          }
        }}>
          <option value="">— unallocated —</option>
          {invoices.map((i) => (
            <option key={i.id} value={i.id}>
              {i.number} · {formatMoney(i.total - i.amount_paid, i.currency)} due
            </option>
          ))}
        </select>
        <input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} placeholder="Amount (cents)" />
        <input value={currency} onChange={(e) => setCurrency(e.target.value)} style={{ width: 70 }} />
        <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Reference" />
        <button className="button" onClick={record} disabled={amount <= 0}>Record payment</button>
      </div>

      <table className="table">
        <thead>
          <tr><th>Paid at</th><th>Invoice</th><th style={{ textAlign: "right" }}>Amount</th><th>Reference</th></tr>
        </thead>
        <tbody>
          {payments.map((p) => {
            const inv = invoices.find((i) => i.id === p.invoice_id);
            return (
              <tr key={p.id}>
                <td>{new Date(p.paid_at).toLocaleString()}</td>
                <td>{inv?.number ?? "—"}</td>
                <td style={{ textAlign: "right" }}>{formatMoney(p.amount, p.currency)}</td>
                <td>{p.reference ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

// ---------------------------------------------------------------------------

function StipendsTab({ studyId, onChange }: { studyId: string; onChange: () => void }) {
  const [rows, setRows] = useState<CtfmsStipend[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [participantId, setParticipantId] = useState("");
  const [amount, setAmount] = useState(0);
  const [currency, setCurrency] = useState("USD");

  async function load() {
    try {
      const [list, pl] = await Promise.all([
        fetchCtfmsStipends(studyId),
        fetchParticipants(studyId).catch(() => [] as Participant[]),
      ]);
      setRows(list);
      setParticipants(pl);
    } catch (e) {
      setErr(describeError(e));
    }
  }
  useEffect(() => { load(); }, [studyId]);

  async function add() {
    if (!participantId || amount <= 0) return;
    try {
      await createCtfmsStipend(studyId, { participant_id: participantId, amount, currency });
      setAmount(0);
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  async function markPaid(id: string) {
    try {
      await updateCtfmsStipend(id, { status: "paid" });
      await load();
      onChange();
    } catch (e) {
      setErr(describeError(e));
    }
  }

  return (
    <section>
      {err && <div className="error">{err}</div>}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <select value={participantId} onChange={(e) => setParticipantId(e.target.value)}>
          <option value="">— participant —</option>
          {participants.map((p) => <option key={p.id} value={p.id}>{p.subject_id}</option>)}
        </select>
        <input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} placeholder="Amount (cents)" />
        <input value={currency} onChange={(e) => setCurrency(e.target.value)} style={{ width: 70 }} />
        <button className="button" onClick={add} disabled={!participantId || amount <= 0}>Add stipend</button>
      </div>

      <table className="table">
        <thead>
          <tr><th>Participant</th><th style={{ textAlign: "right" }}>Amount</th><th>Status</th><th>Paid at</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const part = participants.find((p) => p.id === s.participant_id);
            return (
              <tr key={s.id}>
                <td>{part?.subject_id ?? s.participant_id.slice(0, 8)}</td>
                <td style={{ textAlign: "right" }}>{formatMoney(s.amount, s.currency)}</td>
                <td>{s.status}</td>
                <td>{s.paid_at ? new Date(s.paid_at).toLocaleDateString() : "—"}</td>
                <td>
                  {s.status === "pending" && (
                    <button className="button button-secondary" onClick={() => markPaid(s.id)}>Mark paid</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

// ---------------------------------------------------------------------------

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: "0.5rem 0.75rem", background: "#fff" }}>
      <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "1.05rem", fontWeight: 600, color: accent ?? "#0f172a" }}>{value}</div>
    </div>
  );
}
