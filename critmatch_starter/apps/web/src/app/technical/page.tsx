const MODULES = [
  { name: "Studies", api: "/api/studies" },
  { name: "Cohort Builder", api: "/api/query + /api/terminology" },
  { name: "Feasibility", api: "/api/feasibility + /api/terminology" },
  { name: "ROIE", api: "/api/roie" },
  { name: "Readiness", api: "/api/readiness" },
  { name: "Navigator", api: "/api/navigator" },
  { name: "Equity", api: "/api/equity" },
  { name: "EDC", api: "/api/edc" },
  { name: "Finance (CTFMS)", api: "/api/ctfms" },
  { name: "Results", api: "/api/runs" },
  { name: "Auth + Session", api: "/api/auth" },
  { name: "Audit + Notifications", api: "/api/audit + /api/notifications" },
  { name: "FHIR", api: "/api/fhir" },
];

const API_TECH = [
  "FastAPI 0.115.12",
  "SQLAlchemy 2.0.40",
  "psycopg 3.2.6",
  "Alembic migrations",
  "HTTPX 0.28.1",
  "PyJWT 2.10.1",
  "Sentry SDK 2.28.0",
];

const WEB_TECH = [
  "Next.js 15.5",
  "React 19",
  "TypeScript 5.8",
  "Tailwind CSS 4",
  "Sentry Next.js SDK",
];

const WORKER_TECH = [
  "Python worker service",
  "SQLAlchemy + psycopg",
  "HTTPX",
  "Sentry SDK",
];

const MERMAID_DIAGRAM = `flowchart LR
    U[Users and EHR]\nSMART launch context --> W[Web App\nNext.js on Netlify]
    W --> A[API\nFastAPI on Render]
    A <--> DB[(Render Postgres)]
    A <--> WK[Worker\nPython on Render]
    A <--> F[FHIR Services]
    W --> S[Sentry]
    A --> S
    WK --> S`;

export default function TechnicalPage() {
  return (
    <main className="container">
      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginBottom: "0.5rem" }}>CritMatch Technical Overview</h2>
        <p style={{ margin: 0, color: "var(--cm-muted)" }}>
          CritMatch is a three-tier platform with a Next.js web application, a
          FastAPI backend, and a Python worker service. The platform supports
          cohort discovery workflows, EHR-aligned operations, and SMART on FHIR
          integration.
        </p>
      </section>

      <div className="grid" style={{ gap: "1rem" }}>
        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>System Architecture</h3>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
            <li>Web: Next.js frontend deployed on Netlify.</li>
            <li>API: FastAPI service deployed on Render.</li>
            <li>Worker: Python background service deployed on Render.</li>
            <li>Database: Render Postgres used by API and worker services.</li>
            <li>Observability: Sentry instrumentation on web, API, and worker.</li>
          </ul>
        </section>

        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>Architecture Diagram</h3>
          <p style={{ marginTop: 0, color: "var(--cm-muted)" }}>
            High-level flow of user traffic, service interactions, persistence, and monitoring.
          </p>
          <div
            style={{
              border: "1px solid var(--cm-mint-100)",
              borderRadius: 14,
              background: "linear-gradient(180deg, #ffffff 0%, var(--cm-mint-50) 100%)",
              padding: "1rem",
            }}
          >
            <div className="grid grid-3" style={{ alignItems: "stretch", gap: "0.75rem" }}>
              <div style={{ border: "1px solid var(--cm-mint-200)", borderRadius: 12, padding: "0.8rem", background: "white" }}>
                <h4 style={{ marginBottom: "0.35rem" }}>Users and EHR</h4>
                <p style={{ margin: 0, color: "var(--cm-muted)" }}>
                  Browser sessions and SMART launch context originate from health system workflows.
                </p>
              </div>
              <div style={{ border: "1px solid var(--cm-mint-200)", borderRadius: 12, padding: "0.8rem", background: "white" }}>
                <h4 style={{ marginBottom: "0.35rem" }}>Web App (Netlify)</h4>
                <p style={{ margin: 0, color: "var(--cm-muted)" }}>
                  Next.js UI routes requests to API endpoints and renders module workspaces.
                </p>
              </div>
              <div style={{ border: "1px solid var(--cm-mint-200)", borderRadius: 12, padding: "0.8rem", background: "white" }}>
                <h4 style={{ marginBottom: "0.35rem" }}>FastAPI (Render)</h4>
                <p style={{ margin: 0, color: "var(--cm-muted)" }}>
                  Auth, studies, query, FHIR, EDC, CTFMS, and operational module APIs.
                </p>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "center", margin: "0.75rem 0", color: "var(--cm-teal-3)", fontWeight: 800 }}>
              {"Users/EHR -> Web App -> API"}
            </div>

            <div className="grid grid-3" style={{ alignItems: "stretch", gap: "0.75rem" }}>
              <div style={{ border: "1px solid var(--cm-mint-200)", borderRadius: 12, padding: "0.8rem", background: "white" }}>
                <h4 style={{ marginBottom: "0.35rem" }}>Worker (Render)</h4>
                <p style={{ margin: 0, color: "var(--cm-muted)" }}>
                  Background processing and asynchronous tasks shared with API data models.
                </p>
              </div>
              <div style={{ border: "1px solid var(--cm-mint-200)", borderRadius: 12, padding: "0.8rem", background: "white" }}>
                <h4 style={{ marginBottom: "0.35rem" }}>Postgres (Render)</h4>
                <p style={{ margin: 0, color: "var(--cm-muted)" }}>
                  Primary persistence layer for studies, runs, forms, finance, and system state.
                </p>
              </div>
              <div style={{ border: "1px solid var(--cm-mint-200)", borderRadius: 12, padding: "0.8rem", background: "white" }}>
                <h4 style={{ marginBottom: "0.35rem" }}>Sentry + FHIR</h4>
                <p style={{ margin: 0, color: "var(--cm-muted)" }}>
                  Cross-service telemetry and SMART on FHIR data access/integration.
                </p>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "center", marginTop: "0.75rem", color: "var(--cm-teal-3)", fontWeight: 800 }}>
              {"API <-> Worker <-> Postgres | Web/API/Worker -> Sentry | API <-> FHIR"}
            </div>
          </div>

          <details style={{ marginTop: "0.9rem" }}>
            <summary style={{ cursor: "pointer", fontWeight: 700, color: "var(--cm-teal)" }}>
              Mermaid Source (copy for docs/export)
            </summary>
            <p style={{ margin: "0.6rem 0 0.5rem", color: "var(--cm-muted)" }}>
              Paste this into any Mermaid-enabled markdown document.
            </p>
            <pre
              style={{
                margin: 0,
                overflowX: "auto",
                background: "#0f3a3a",
                color: "#eef9f1",
                borderRadius: 10,
                padding: "0.8rem",
                fontSize: "0.84rem",
                lineHeight: 1.5,
              }}
            >
              {MERMAID_DIAGRAM}
            </pre>
          </details>
        </section>

        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>Technology Stack</h3>
          <div className="grid grid-3" style={{ gap: "0.75rem" }}>
            <div style={{ background: "var(--cm-mint-50)", border: "1px solid var(--cm-mint-100)", borderRadius: 12, padding: "0.85rem" }}>
              <h4 style={{ marginBottom: "0.45rem" }}>Web</h4>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", lineHeight: 1.6 }}>
                {WEB_TECH.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div style={{ background: "var(--cm-mint-50)", border: "1px solid var(--cm-mint-100)", borderRadius: 12, padding: "0.85rem" }}>
              <h4 style={{ marginBottom: "0.45rem" }}>API</h4>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", lineHeight: 1.6 }}>
                {API_TECH.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div style={{ background: "var(--cm-mint-50)", border: "1px solid var(--cm-mint-100)", borderRadius: 12, padding: "0.85rem" }}>
              <h4 style={{ marginBottom: "0.45rem" }}>Worker</h4>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", lineHeight: 1.6 }}>
                {WORKER_TECH.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>Module API Surface</h3>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Primary API Routes</th>
                </tr>
              </thead>
              <tbody>
                {MODULES.map((module) => (
                  <tr key={module.name}>
                    <td>{module.name}</td>
                    <td style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>{module.api}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>Security and Integration</h3>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
            <li>Session and auth endpoints are exposed through the API auth router.</li>
            <li>CORS is configured at API startup using allowed origin settings.</li>
            <li>SMART on FHIR launch variables support EHR context workflows.</li>
            <li>FHIR base URL and issuer allow-list are environment controlled.</li>
            <li>Signed export and secret management rely on deployment environment variables.</li>
          </ul>
        </section>

        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>Deployment Topology</h3>
          <ol style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.65 }}>
            <li>Netlify builds and serves the web app from apps/web.</li>
            <li>Render deploys the API service from apps/api.</li>
            <li>Render deploys the worker service from apps/worker.</li>
            <li>Render Postgres provides managed persistence.</li>
            <li>Environment values connect frontend, API, SMART on FHIR, and monitoring.</li>
          </ol>
        </section>

        <section className="card">
          <h3 style={{ marginBottom: "0.6rem" }}>Operational Endpoints</h3>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
            <li><span style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>/health</span> returns basic API liveness.</li>
            <li><span style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>/ready</span> validates configured secrets and database connectivity.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
