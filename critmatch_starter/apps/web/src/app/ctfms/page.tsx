"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  fetchCtfmsFinanceSummary,
  fetchStudies,
  formatMoney,
  type CtfmsFinanceSummary,
  type Study,
} from "../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  return (e as Error).message ?? "Unknown error";
}

type Row = { study: Study; summary: CtfmsFinanceSummary | null; error?: string };

export default function CtfmsIndexPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const studies = await fetchStudies();
      const enriched = await Promise.all(
        studies.map(async (s) => {
          try {
            const summary = await fetchCtfmsFinanceSummary(s.id);
            return { study: s, summary } as Row;
          } catch (e) {
            return { study: s, summary: null, error: describeError(e) } as Row;
          }
        }),
      );
      setRows(enriched);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const totals = rows.reduce(
    (acc, r) => {
      if (!r.summary) return acc;
      acc.accruedOpen += r.summary.accruedOpen;
      acc.invoiceTotal += r.summary.invoiceTotal;
      acc.paid += r.summary.paid;
      acc.outstanding += r.summary.outstanding;
      acc.stipendsPending += r.summary.stipendsPending;
      return acc;
    },
    { accruedOpen: 0, invoiceTotal: 0, paid: 0, outstanding: 0, stipendsPending: 0 },
  );

  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <h1>Finance (CTFMS)</h1>
        <p style={{ color: "#475569" }}>
          Track sponsor budgets, accruals from EDC visits, invoicing and payments, and
          patient stipends across all of your studies.
        </p>
      </div>

      {error && <div className="error">{error}</div>}
      {loading ? <p>Loading…</p> : null}

      {!loading && rows.length === 0 && (
        <p style={{ color: "#475569" }}>
          No studies yet. <Link href="/studies">Create a study</Link> to start tracking finances.
        </p>
      )}

      {!loading && rows.length > 0 && (
        <>
          <section
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "0.75rem",
              marginBottom: "1.5rem",
            }}
          >
            <Card label="Accrued (open)" value={formatMoney(totals.accruedOpen)} />
            <Card label="Invoiced" value={formatMoney(totals.invoiceTotal)} />
            <Card label="Paid" value={formatMoney(totals.paid)} accent="#16a34a" />
            <Card label="Outstanding" value={formatMoney(totals.outstanding)} accent="#dc2626" />
            <Card label="Stipends pending" value={formatMoney(totals.stipendsPending)} />
          </section>

          <table className="table">
            <thead>
              <tr>
                <th>Study</th>
                <th style={{ textAlign: "right" }}>Accrued open</th>
                <th style={{ textAlign: "right" }}>Invoiced</th>
                <th style={{ textAlign: "right" }}>Paid</th>
                <th style={{ textAlign: "right" }}>Outstanding</th>
                <th style={{ textAlign: "right" }}>Stipends pending</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.study.id}>
                  <td>
                    <Link href={`/ctfms/studies/${r.study.id}`}>{r.study.name}</Link>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {r.summary ? formatMoney(r.summary.accruedOpen) : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {r.summary ? formatMoney(r.summary.invoiceTotal) : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {r.summary ? formatMoney(r.summary.paid) : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {r.summary ? formatMoney(r.summary.outstanding) : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {r.summary ? formatMoney(r.summary.stipendsPending) : "—"}
                  </td>
                  <td>
                    <Link href={`/ctfms/studies/${r.study.id}`} className="button button-secondary">
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: 8,
        padding: "0.75rem 1rem",
        background: "#fff",
      }}
    >
      <div style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "1.25rem", fontWeight: 600, color: accent ?? "#0f172a" }}>{value}</div>
    </div>
  );
}
