const results = [
  { patientId: "patient-001", age: 67, sex: "Female", site: "Cardiology Clinic", matchReason: "Matched myocardial infarction" },
  { patientId: "patient-002", age: 58, sex: "Male", site: "General Medicine", matchReason: "Matched myocardial infarction" },
];

export default function ResultsPage() {
  return (
    <main className="container">
      <div style={{ marginBottom: "1rem" }}>
        <h1>Results</h1>
        <p style={{ color: "#475569" }}>Filter and review candidate patients.</p>
      </div>

      <div className="card" style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <input className="input" style={{ maxWidth: "200px" }} placeholder="Filter by site" />
        <input className="input" style={{ maxWidth: "200px" }} placeholder="Filter by age" />
        <input className="input" style={{ maxWidth: "200px" }} placeholder="Filter by sex" />
        <button className="button">Export CSV</button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Patient ID</th>
              <th>Age</th>
              <th>Sex</th>
              <th>Site</th>
              <th>Matched Rule</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row) => (
              <tr key={row.patientId}>
                <td>{row.patientId}</td>
                <td>{row.age}</td>
                <td>{row.sex}</td>
                <td>{row.site}</td>
                <td>{row.matchReason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
