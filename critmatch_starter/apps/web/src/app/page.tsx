import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container">
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>CritMatch</h1>
        <p style={{ color: "#475569" }}>
          Launch-ready starter UI for an EHR-embedded cohort identification app.
        </p>
      </div>

      <div className="grid grid-3">
        <Link className="card" href="/studies">
          <h2>Studies</h2>
          <p>Manage saved study definitions and cohort workspaces.</p>
        </Link>
        <Link className="card" href="/builder">
          <h2>Criteria Builder</h2>
          <p>Define inclusion and exclusion rules with terminology expansion.</p>
        </Link>
        <Link className="card" href="/results">
          <h2>Results</h2>
          <p>Review, filter, and export candidate patient cohorts.</p>
        </Link>
      </div>
    </main>
  );
}
