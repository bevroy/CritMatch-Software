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

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ marginBottom: "0.45rem" }}>What&apos;s New in CritMatch CRAN</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
          Updated today with new infrastructure for equitable participation across the
          Community Research Access Network.
        </p>
        <div className="grid grid-3" style={{ marginTop: "0.35rem" }}>
          <article className="card">
            <h3 style={{ marginBottom: "0.35rem" }}>Community Research Access</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)" }}>
              Added Community Network and Navigator Workspace modules for partner referrals
              and barrier-resolution coordination.
            </p>
          </article>
          <article className="card">
            <h3 style={{ marginBottom: "0.35rem" }}>Equity & Readiness Intelligence</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)" }}>
              Added Equity Scorecards plus the RWD Readiness Engine for site readiness,
              care-gap visibility, and sponsor-ready profile generation.
            </p>
          </article>
          <article className="card">
            <h3 style={{ marginBottom: "0.35rem" }}>ROIE Expansion</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)" }}>
              Expanded ROIE with NCT IDs, study links, recruiting status, and study contact
              fields in the opportunity feed.
            </p>
          </article>
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
        <Link className="card" href="/roie">
          <h2>🛰️ ROIE</h2>
          <p>Research Opportunity Intelligence Engine for study, site, sponsor, and diversity intelligence.</p>
        </Link>
        <Link className="card" href="/readiness">
          <h2>🧠 RWD Readiness</h2>
          <p>Assess research readiness, estimate eligible populations, and build sponsor-ready site profiles.</p>
        </Link>
        <Link className="card" href="/community">
          <h2>🤝 Community Network</h2>
          <p>Coordinate partner referrals from community organizations and safety-net sites.</p>
        </Link>
        <Link className="card" href="/navigator">
          <h2>🧭 Navigator Workspace</h2>
          <p>Track and resolve participant barriers like transportation, language, and childcare.</p>
        </Link>
        <Link className="card" href="/equity">
          <h2>⚖️ Equity Scorecards</h2>
          <p>Monitor subgroup conversion and receive recommendations for equitable enrollment.</p>
        </Link>
      </div>
    </main>
  );
}
