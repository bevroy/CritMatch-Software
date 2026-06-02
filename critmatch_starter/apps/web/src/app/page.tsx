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

      {/* The Platform */}
      <section style={{ marginTop: "1.25rem" }}>
        <h2 style={{ marginBottom: "0.45rem" }}>The Platform</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
          Explore the full CritMatch CRAN platform, including the newest modules for
          equity, readiness, community access, and research opportunity intelligence.
        </p>
      </section>

      {/* Feature tiles */}
      <div className="grid grid-3" style={{ marginTop: "1.25rem" }}>
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

      <section className="card" style={{ marginTop: "1.25rem" }}>
        <h2 style={{ marginBottom: "0.45rem" }}>Competitive Position</h2>
        <p style={{ marginTop: 0, color: "var(--cm-muted)", lineHeight: 1.55 }}>
          CritMatch differentiates from point tools by combining cohort discovery, site readiness,
          community referral operations, and equity performance into one EHR-integrated platform.
        </p>
        <div className="grid grid-3" style={{ marginTop: "0.35rem" }}>
          <article className="card">
            <h3 style={{ marginBottom: "0.35rem" }}>From Identification to Enrollment</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)" }}>
              Move beyond candidate lists by coordinating navigators, referral partners, and barrier
              resolution in the same workflow.
            </p>
          </article>
          <article className="card">
            <h3 style={{ marginBottom: "0.35rem" }}>Readiness + Opportunity Intelligence</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)" }}>
              Match external opportunities with internal readiness signals to prioritize studies that
              are both operationally feasible and equitable.
            </p>
          </article>
          <article className="card">
            <h3 style={{ marginBottom: "0.35rem" }}>Equity by Design</h3>
            <p style={{ margin: 0, color: "var(--cm-muted)" }}>
              Track subgroup conversion and intervention impact continuously, rather than treating
              equity as a retrospective reporting step.
            </p>
          </article>
        </div>
      </section>
    </main>
  );
}
