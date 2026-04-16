const studies = [
  { id: "1", name: "NSTEMI Registry", updatedAt: "2026-04-16" },
  { id: "2", name: "Heart Failure Feasibility", updatedAt: "2026-04-15" },
];

export default function StudiesPage() {
  return (
    <main className="container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h1>Studies</h1>
          <p style={{ color: "#475569" }}>Saved cohort definitions and study workspaces.</p>
        </div>
        <button className="button">New Study</button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Last Updated</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {studies.map((study) => (
              <tr key={study.id}>
                <td>{study.name}</td>
                <td>{study.updatedAt}</td>
                <td>Active</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
