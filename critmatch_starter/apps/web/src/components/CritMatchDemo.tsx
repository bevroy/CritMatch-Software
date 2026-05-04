"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { runMatchLocal, DEMO_PRESETS, SAMPLE_PATIENTS } from "../lib/critmatch-mock";
import type { MatchRequest, MatchResponse, PatientMatch } from "../lib/critmatch-types";

function splitCsv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

const CONFIDENCE_BG: Record<PatientMatch["confidence"], string> = {
  High: "#d8efe0",
  Moderate: "#fef3c7",
  Low: "#e2e8f0",
  Excluded: "#fee2e2",
};
const CONFIDENCE_FG: Record<PatientMatch["confidence"], string> = {
  High: "#0f3a3a",
  Moderate: "#92400e",
  Low: "#475569",
  Excluded: "#991b1b",
};

function ConfidenceBadge({ tone }: { tone: PatientMatch["confidence"] }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "0.25rem 0.7rem",
        borderRadius: "999px",
        background: CONFIDENCE_BG[tone],
        color: CONFIDENCE_FG[tone],
        fontWeight: 700,
        fontSize: "0.78rem",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      {tone}
    </span>
  );
}

function Bullets({ items, fallback }: { items: string[]; fallback: string }) {
  const data = items.length ? items : [fallback];
  return (
    <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.1rem", fontSize: "0.88rem", color: "var(--cm-text)" }}>
      {data.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}

function PatientCard({ match }: { match: PatientMatch }) {
  return (
    <div className="card" style={{ marginTop: "0.85rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", marginBottom: "0.65rem" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "1.1rem", color: "var(--cm-teal)" }}>{match.patient_id}</h3>
          <p style={{ margin: "0.15rem 0 0", color: "var(--cm-muted)", fontSize: "0.85rem" }}>
            Age {match.age ?? "\u2014"} \u00b7 {match.sex ?? "\u2014"}
          </p>
        </div>
        <ConfidenceBadge tone={match.confidence} />
      </div>
      <p style={{ margin: "0 0 0.85rem", fontSize: "0.92rem", color: "var(--cm-text)" }}>{match.recommendation}</p>
      <div style={{ display: "grid", gap: "0.85rem", gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        <div>
          <p style={{ margin: 0, fontSize: "0.7rem", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 700, color: "var(--cm-teal-3)" }}>Matched</p>
          <Bullets items={match.matched_criteria} fallback="None" />
        </div>
        <div>
          <p style={{ margin: 0, fontSize: "0.7rem", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 700, color: "var(--cm-teal-3)" }}>Exclusions</p>
          <Bullets items={match.exclusion_flags} fallback="None" />
        </div>
        <div>
          <p style={{ margin: 0, fontSize: "0.7rem", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 700, color: "var(--cm-teal-3)" }}>Missing / unresolved</p>
          <Bullets items={match.missing_data} fallback="None" />
        </div>
      </div>
    </div>
  );
}

export default function CritMatchDemo() {
  const [activePreset, setActivePreset] = useState<string>(DEMO_PRESETS[0].id);
  const initial = DEMO_PRESETS[0].request;

  const [trialName, setTrialName] = useState(initial.trial_name);
  const [ageMin, setAgeMin] = useState(initial.inclusion.age_min?.toString() ?? "");
  const [ageMax, setAgeMax] = useState(initial.inclusion.age_max?.toString() ?? "");
  const [inclusionDx, setInclusionDx] = useState(initial.inclusion.diagnoses.join(", "));
  const [exclusionDx, setExclusionDx] = useState(initial.exclusion.diagnoses.join(", "));
  const [exclusionMeds, setExclusionMeds] = useState(initial.exclusion.medications.join(", "));
  const [exclusionConditions, setExclusionConditions] = useState(initial.exclusion.conditions.join(", "));
  const [hba1c, setHba1c] = useState(initial.inclusion.labs[0]?.value?.toString() ?? "");
  const [egfr, setEgfr] = useState(initial.exclusion.labs[0]?.value?.toString() ?? "");
  const [result, setResult] = useState<MatchResponse | null>(null);
  const [showFilter, setShowFilter] = useState<"all" | "candidates">("all");

  function applyPreset(id: string) {
    const preset = DEMO_PRESETS.find((p) => p.id === id);
    if (!preset) return;
    setActivePreset(id);
    const r = preset.request;
    setTrialName(r.trial_name);
    setAgeMin(r.inclusion.age_min?.toString() ?? "");
    setAgeMax(r.inclusion.age_max?.toString() ?? "");
    setInclusionDx(r.inclusion.diagnoses.join(", "));
    setExclusionDx(r.exclusion.diagnoses.join(", "));
    setExclusionMeds(r.exclusion.medications.join(", "));
    setExclusionConditions(r.exclusion.conditions.join(", "));
    setHba1c(r.inclusion.labs[0]?.value?.toString() ?? "");
    setEgfr(r.exclusion.labs[0]?.value?.toString() ?? "");
    setResult(null);
  }

  const request = useMemo<MatchRequest>(
    () => ({
      trial_name: trialName,
      inclusion: {
        age_min: ageMin ? Number(ageMin) : undefined,
        age_max: ageMax ? Number(ageMax) : undefined,
        diagnoses: splitCsv(inclusionDx),
        medications: [],
        icd10: [],
        labs: hba1c ? [{ name: "HbA1c", operator: ">", value: Number(hba1c) }] : [],
      },
      exclusion: {
        diagnoses: splitCsv(exclusionDx),
        medications: splitCsv(exclusionMeds),
        conditions: splitCsv(exclusionConditions),
        icd10: [],
        labs: egfr ? [{ name: "eGFR", operator: "<", value: Number(egfr) }] : [],
      },
    }),
    [trialName, ageMin, ageMax, inclusionDx, exclusionDx, exclusionMeds, exclusionConditions, hba1c, egfr],
  );

  function handleRun() {
    setResult(runMatchLocal(request));
  }

  const visibleMatches = useMemo(() => {
    if (!result) return [] as PatientMatch[];
    if (showFilter === "candidates") {
      return result.matches.filter((m) => m.confidence === "High" || m.confidence === "Moderate");
    }
    return result.matches;
  }, [result, showFilter]);

  const counts = useMemo(() => {
    const base = { High: 0, Moderate: 0, Low: 0, Excluded: 0 };
    if (!result) return base;
    for (const m of result.matches) base[m.confidence] += 1;
    return base;
  }, [result]);

  return (
    <main className="container">
      <section className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <p style={{ margin: 0, fontSize: "0.7rem", letterSpacing: "0.22em", textTransform: "uppercase", fontWeight: 800, color: "var(--cm-teal-3)" }}>
            Public sample &middot; No sign-in required
          </p>
          <h2 style={{ margin: 0 }}>Try the matching engine</h2>
          <p style={{ margin: 0, color: "var(--cm-muted)" }}>
            Pick a sample trial, tweak the criteria, and run it against {SAMPLE_PATIENTS.length} bundled patient records. Everything runs in your browser &mdash; nothing is sent to a server.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "1rem" }}>
          {DEMO_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`chip${activePreset === p.id ? " active" : ""}`}
              onClick={() => applyPreset(p.id)}
              title={p.description}
            >
              {p.label}
            </button>
          ))}
          <Link href="/cohort" className="chip" style={{ marginLeft: "auto", borderColor: "var(--cm-teal-3)", color: "var(--cm-teal)" }}>
            Full Cohort Builder &rarr;
          </Link>
        </div>
      </section>

      <div className="grid demo-grid" style={{ gap: "1rem" }}>
        <section className="card">
          <h3 style={{ marginTop: 0, fontSize: "1.1rem" }}>Cohort Criteria</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Trial name
              <input className="input" style={{ marginTop: "0.25rem" }} value={trialName} onChange={(e) => setTrialName(e.target.value)} />
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
                Age min
                <input className="input" style={{ marginTop: "0.25rem" }} value={ageMin} onChange={(e) => setAgeMin(e.target.value)} />
              </label>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
                Age max
                <input className="input" style={{ marginTop: "0.25rem" }} value={ageMax} onChange={(e) => setAgeMax(e.target.value)} />
              </label>
            </div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Required diagnoses (comma separated)
              <input className="input" style={{ marginTop: "0.25rem" }} value={inclusionDx} onChange={(e) => setInclusionDx(e.target.value)} />
            </label>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Require HbA1c greater than
              <input className="input" style={{ marginTop: "0.25rem" }} value={hba1c} onChange={(e) => setHba1c(e.target.value)} />
            </label>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Excluded diagnoses
              <input className="input" style={{ marginTop: "0.25rem" }} value={exclusionDx} onChange={(e) => setExclusionDx(e.target.value)} />
            </label>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Excluded medications
              <input className="input" style={{ marginTop: "0.25rem" }} value={exclusionMeds} onChange={(e) => setExclusionMeds(e.target.value)} />
            </label>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Excluded conditions
              <input className="input" style={{ marginTop: "0.25rem" }} value={exclusionConditions} onChange={(e) => setExclusionConditions(e.target.value)} />
            </label>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
              Exclude eGFR less than
              <input className="input" style={{ marginTop: "0.25rem" }} value={egfr} onChange={(e) => setEgfr(e.target.value)} />
            </label>
            <button onClick={handleRun} className="button" style={{ marginTop: "0.25rem" }}>Run Match</button>
          </div>
        </section>

        <section>
          <div className="card" style={{ marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Match Results</h3>
                <p style={{ margin: "0.2rem 0 0", color: "var(--cm-muted)", fontSize: "0.9rem" }}>
                  {result
                    ? `${result.total_patients_screened} patients screened for "${result.trial_name}"`
                    : "Adjust criteria and run a match to see candidates."}
                </p>
              </div>
              {result && (
                <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                  <span className="chip" style={{ cursor: "default" }}>High ({counts.High})</span>
                  <span className="chip" style={{ cursor: "default" }}>Moderate ({counts.Moderate})</span>
                  <span className="chip" style={{ cursor: "default" }}>Low ({counts.Low})</span>
                  <span className="chip" style={{ cursor: "default" }}>Excluded ({counts.Excluded})</span>
                </div>
              )}
            </div>
            {result && (
              <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.85rem" }}>
                <button type="button" className={`chip${showFilter === "all" ? " active" : ""}`} onClick={() => setShowFilter("all")}>
                  All ({result.matches.length})
                </button>
                <button type="button" className={`chip${showFilter === "candidates" ? " active" : ""}`} onClick={() => setShowFilter("candidates")}>
                  Candidates only ({counts.High + counts.Moderate})
                </button>
              </div>
            )}
          </div>
          {visibleMatches.map((m) => (
            <PatientCard key={m.patient_id} match={m} />
          ))}
        </section>
      </div>
    </main>
  );
}
