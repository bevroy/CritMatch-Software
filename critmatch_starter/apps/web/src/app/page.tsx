import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container">
      <section className="hero">
        <div className="hero-tagline">EHR Cohort Identification Platform</div>
        <h1>Match the right patients to the right trials.</h1>
        <p className="lead">
          CritMatch turns EMR data into clinical-trial cohorts — define studies,
          run feasibility, capture EDC data points, and manage trial finances in one place.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/cohort" className="button">🧩 Build a Cohort</Link>
          <Link href="/studies" className="button-secondary">📋 View Studies</Link>
        </div>
      </section>

      <div className="grid grid-3" style={{ marginTop: "1.5rem" }}>
        <Link className="card" href="/studies">
          <h2>📋 Studies</h2>
          <p>Manage saved study definitions and cohort workspaces.</p>
        </Link>
        <Link className="card" href="/cohort">
          <h2>🧩 Cohort Builder</h2>
          <p>Define inclusion and exclusion rules with terminology expansion.</p>
        </Link>
        <Link className="card" href="/results">
          <h2>📊 Results</h2>
          <p>Review, filter, and export candidate patient cohorts.</p>
        </Link>
        <Link className="card" href="/feasibility">
          <h2>📈 Feasibility</h2>
          <p>Answer trial feasibility questionnaires from EMR data.</p>
        </Link>
        <Link className="card" href="/edc">
          <h2>📝 EDC</h2>
          <p>Build study forms, identify participants, and pull data points from the EMR.</p>
        </Link>
        <Link className="card" href="/ctfms">
          <h2>💳 Finance (CTFMS)</h2>
          <p>Track sponsor budgets, accruals, invoices, payments, and patient stipends.</p>
        </Link>
      </div>
    </main>
  );
}
