export default function BuilderPage() {
  return (
    <main className="container">
      <div className="grid grid-3">
        <section className="card">
          <h2>Criteria Builder</h2>
          <div style={{ display: "grid", gap: "1rem" }}>
            <div>
              <label>Criterion Type</label>
              <select className="select" defaultValue="Diagnosis">
                <option>Diagnosis</option>
                <option>Procedure</option>
                <option>Age</option>
                <option>Sex</option>
                <option>Encounter Date</option>
                <option>Site</option>
              </select>
            </div>
            <div>
              <label>Search Term or Code</label>
              <input className="input" placeholder="e.g. heart attack or I21" />
            </div>
            <label>
              <input type="checkbox" /> Include known variations / synonyms
            </label>
            <button className="button">Add Criterion</button>
          </div>
        </section>

        <section className="card">
          <h2>Expanded Terms</h2>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <div className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>myocardial infarction</div>
            <div className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>MI</div>
            <div className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>ICD-10-CM: I21</div>
            <div className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>SNOMED CT: 22298006</div>
          </div>
        </section>

        <section className="card">
          <h2>Logic Summary</h2>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <div className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>Include diagnosis: myocardial infarction</div>
            <div className="card" style={{ boxShadow: "none", border: "1px solid #e2e8f0" }}>Exclude age: &lt; 18</div>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
            <button className="button" style={{ background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}>Save</button>
            <button className="button">Run Query</button>
          </div>
        </section>
      </div>
    </main>
  );
}
