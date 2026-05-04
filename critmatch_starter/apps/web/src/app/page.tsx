import Link from "next/link";
import Image from "next/image";

export default function HomePage() {
  return (
    <main className="container">
      {/* Brand hero — large centered logo on the mint background, no card */}
      <section className="brand-hero">
        <Image
          src="/critmatch-logo-mark.png"
          alt="CritMatch"
          width={216}
          height={110}
          priority
          className="brand-hero-logo"
        />
        <div className="brand-hero-tagline">
          Smarter Matches. Better Trials. Real Impact.
        </div>
      </section>

      {/* Primary CTA card */}
      <section className="card hero-card">
        <h2>Start Cohort Discovery</h2>
        <p className="hero-card-lead">
          Define inclusion and exclusion criteria, expand them with terminology
          services, and run them against the EHR to surface candidate participants
          for your trial.
        </p>
        <div className="hero-card-actions">
          <Link href="/cohort" className="button">🧩 Build a Cohort</Link>
          <Link href="/studies" className="button-secondary">📋 View Studies</Link>
        </div>
      </section>

      {/* Feature tiles */}
      <div className="grid grid-3" style={{ marginTop: "1.25rem" }}>
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
