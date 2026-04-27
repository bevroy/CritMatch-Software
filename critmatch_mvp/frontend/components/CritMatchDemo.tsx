'use client';

import { useMemo, useState } from 'react';
import { runMatch } from '../lib/api';
import type { MatchRequest, MatchResponse, PatientMatch } from '../lib/types';

const defaultRequest: MatchRequest = {
  trial_name: 'Heart Failure + Diabetes Trial',
  inclusion: {
    age_min: 18,
    age_max: 75,
    diagnoses: ['heart failure'],
    medications: [],
    icd10: [],
    labs: [{ name: 'HbA1c', operator: '>', value: 8 }],
  },
  exclusion: {
    diagnoses: ['stroke'],
    medications: ['warfarin'],
    conditions: ['pregnancy'],
    icd10: [],
    labs: [{ name: 'eGFR', operator: '<', value: 30 }],
  },
};

function splitCsv(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function Badge({ children, tone }: { children: React.ReactNode; tone: string }) {
  const base = 'inline-flex rounded-full px-3 py-1 text-xs font-semibold';
  const styles: Record<string, string> = {
    High: 'bg-emerald-100 text-emerald-800',
    Moderate: 'bg-amber-100 text-amber-800',
    Low: 'bg-slate-100 text-slate-700',
    Excluded: 'bg-red-100 text-red-800',
  };
  return <span className={`${base} ${styles[tone] || styles.Low}`}>{children}</span>;
}

function PatientCard({ match }: { match: PatientMatch }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{match.patient_id}</h3>
          <p className="text-sm text-slate-500">Age {match.age ?? '—'} · {match.sex ?? '—'}</p>
        </div>
        <Badge tone={match.confidence}>{match.confidence}</Badge>
      </div>
      <p className="mb-3 text-sm text-slate-700">{match.recommendation}</p>
      <div className="grid gap-3 md:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Matched</p>
          <ul className="mt-1 list-disc pl-4 text-sm text-slate-700">
            {(match.matched_criteria.length ? match.matched_criteria : ['None']).map((item, idx) => <li key={idx}>{item}</li>)}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Exclusions</p>
          <ul className="mt-1 list-disc pl-4 text-sm text-slate-700">
            {(match.exclusion_flags.length ? match.exclusion_flags : ['None']).map((item, idx) => <li key={idx}>{item}</li>)}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Missing / unresolved</p>
          <ul className="mt-1 list-disc pl-4 text-sm text-slate-700">
            {(match.missing_data.length ? match.missing_data : ['None']).map((item, idx) => <li key={idx}>{item}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function CritMatchDemo() {
  const [trialName, setTrialName] = useState(defaultRequest.trial_name);
  const [ageMin, setAgeMin] = useState(defaultRequest.inclusion.age_min?.toString() ?? '');
  const [ageMax, setAgeMax] = useState(defaultRequest.inclusion.age_max?.toString() ?? '');
  const [inclusionDx, setInclusionDx] = useState(defaultRequest.inclusion.diagnoses.join(', '));
  const [exclusionDx, setExclusionDx] = useState(defaultRequest.exclusion.diagnoses.join(', '));
  const [exclusionMeds, setExclusionMeds] = useState(defaultRequest.exclusion.medications.join(', '));
  const [exclusionConditions, setExclusionConditions] = useState(defaultRequest.exclusion.conditions.join(', '));
  const [hba1c, setHba1c] = useState('8');
  const [egfr, setEgfr] = useState('30');
  const [result, setResult] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = useMemo<MatchRequest>(() => ({
    trial_name: trialName,
    inclusion: {
      age_min: ageMin ? Number(ageMin) : undefined,
      age_max: ageMax ? Number(ageMax) : undefined,
      diagnoses: splitCsv(inclusionDx),
      medications: [],
      icd10: [],
      labs: hba1c ? [{ name: 'HbA1c', operator: '>', value: Number(hba1c) }] : [],
    },
    exclusion: {
      diagnoses: splitCsv(exclusionDx),
      medications: splitCsv(exclusionMeds),
      conditions: splitCsv(exclusionConditions),
      icd10: [],
      labs: egfr ? [{ name: 'eGFR', operator: '<', value: Number(egfr) }] : [],
    },
  }), [trialName, ageMin, ageMax, inclusionDx, exclusionDx, exclusionMeds, exclusionConditions, hba1c, egfr]);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const response = await runMatch(request);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-8 text-slate-900">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 rounded-3xl bg-slate-950 p-8 text-white shadow-sm">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-teal-300">Elionyx Health · CritMatch</p>
          <h1 className="text-4xl font-bold tracking-tight">Clinical trial matching infrastructure</h1>
          <p className="mt-3 max-w-3xl text-slate-300">Screen structured trial criteria against sample patient records and surface likely matches, exclusions, and missing data for coordinator review.</p>
        </header>

        <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-xl font-semibold">Trial Criteria Builder</h2>
            <div className="space-y-4">
              <label className="block text-sm font-medium">Trial name<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={trialName} onChange={(e) => setTrialName(e.target.value)} /></label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm font-medium">Age min<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={ageMin} onChange={(e) => setAgeMin(e.target.value)} /></label>
                <label className="block text-sm font-medium">Age max<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={ageMax} onChange={(e) => setAgeMax(e.target.value)} /></label>
              </div>
              <label className="block text-sm font-medium">Required diagnoses<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={inclusionDx} onChange={(e) => setInclusionDx(e.target.value)} /></label>
              <label className="block text-sm font-medium">HbA1c greater than<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={hba1c} onChange={(e) => setHba1c(e.target.value)} /></label>
              <label className="block text-sm font-medium">Excluded diagnoses<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={exclusionDx} onChange={(e) => setExclusionDx(e.target.value)} /></label>
              <label className="block text-sm font-medium">Excluded medications<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={exclusionMeds} onChange={(e) => setExclusionMeds(e.target.value)} /></label>
              <label className="block text-sm font-medium">Excluded conditions<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={exclusionConditions} onChange={(e) => setExclusionConditions(e.target.value)} /></label>
              <label className="block text-sm font-medium">Exclude eGFR less than<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={egfr} onChange={(e) => setEgfr(e.target.value)} /></label>
              <button onClick={handleRun} disabled={loading} className="w-full rounded-xl bg-teal-700 px-4 py-3 font-semibold text-white hover:bg-teal-800 disabled:opacity-60">{loading ? 'Matching...' : 'Run Match'}</button>
              {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Match Results</h2>
              <p className="mt-1 text-sm text-slate-500">{result ? `${result.total_patients_screened} patients screened for ${result.trial_name}` : 'Run a match to view candidate results.'}</p>
            </div>
            {result?.matches.map((match) => <PatientCard key={match.patient_id} match={match} />)}
          </section>
        </div>
      </div>
    </main>
  );
}
