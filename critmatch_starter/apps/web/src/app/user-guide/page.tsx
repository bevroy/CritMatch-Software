type GuideSection = {
  title: string;
  id: string;
  steps: string[];
  notes?: string;
};

const GUIDE_SECTIONS: GuideSection[] = [
  {
    title: "Home",
    id: "home",
    steps: [
      "Open the Home page to access the full module catalog.",
      "Use Build a Cohort to jump directly to cohort definition.",
      "Use View Studies to open existing studies and workspaces.",
      "Select any feature tile to navigate to that module.",
    ],
  },
  {
    title: "Studies",
    id: "studies",
    steps: [
      "Open Studies to review the list of saved studies.",
      "Select New Study, enter study name and optional description, then create the study.",
      "Open a study to review details, runs, and collaboration panels.",
      "Use study-level actions to run saved criteria and compare run outputs.",
      "Review recent run history for execution status and timing.",
    ],
  },
  {
    title: "Cohort Builder",
    id: "cohort-builder",
    steps: [
      "Choose a study from the selector to attach cohort criteria.",
      "Set logic to AND or OR based on matching requirements.",
      "Add inclusion or exclusion criteria using condition, observation, or demographic fields.",
      "Use terminology expansion where available to broaden matching terms.",
      "Save Only to store criteria, or Save and Run Query to execute immediately.",
    ],
  },
  {
    title: "Feasibility",
    id: "feasibility",
    steps: [
      "Open Feasibility and create a questionnaire with a name and optional description.",
      "Attach the questionnaire to a study when needed.",
      "Add questions by type, term, and demographic filters.",
      "Use term expansion for clinical concepts when needed.",
      "Run Questionnaire and review generated counts and run history.",
    ],
  },
  {
    title: "ROIE",
    id: "roie",
    steps: [
      "Open ROIE to review opportunity intelligence cards.",
      "Check study, site, sponsor, geographic, and diversity opportunity previews.",
      "Use Refresh to reload current opportunity snapshots.",
      "Review latest opportunities and prioritize follow-up targets.",
    ],
    notes: "ROIE is currently a read-only intelligence view.",
  },
  {
    title: "Readiness",
    id: "readiness",
    steps: [
      "Open Readiness to view real-world data readiness indicators.",
      "Review readiness score, eligible population estimate, and completion metrics.",
      "Use Refresh to request updated values.",
      "Use results to support site and sponsor readiness planning.",
    ],
    notes: "Readiness is currently a read-only dashboard.",
  },
  {
    title: "Community",
    id: "community",
    steps: [
      "Open Community to review partner network activity.",
      "Check summary metrics for partners, referrals, and enrollments.",
      "Use Refresh to update current network data.",
      "Review partner table details including location, language coverage, and activity.",
    ],
    notes: "Community is currently a read-only dashboard.",
  },
  {
    title: "Navigator",
    id: "navigator",
    steps: [
      "Open Navigator Workspace to review open participant barrier tasks.",
      "Review summary metrics for open, in-progress, and recently resolved tasks.",
      "Use Refresh to load the latest queue and ownership details.",
      "Review task attributes such as barrier type, priority, status, and due date.",
    ],
    notes: "Navigator is currently a read-only queue view.",
  },
  {
    title: "Equity",
    id: "equity",
    steps: [
      "Open Equity Scorecards to monitor subgroup performance.",
      "Review screened and enrolled values by category and subgroup.",
      "Check conversion percentages and compare across groups.",
      "Review Equity Alerts and associated recommendations.",
      "Use Refresh to update scorecard and alert data.",
    ],
    notes: "Equity is currently a read-only dashboard.",
  },
  {
    title: "EDC",
    id: "edc",
    steps: [
      "Open EDC and create a new form linked to a study.",
      "Add form fields with key, label, and item type, then save field definitions.",
      "Activate the form when ready for entry collection.",
      "Start participant entries from the form detail page.",
      "Open existing entries to review status and collected data.",
      "Lock the form when collection is complete.",
    ],
  },
  {
    title: "Finance",
    id: "finance",
    steps: [
      "Open Finance (CTFMS) to review study-level financial summaries.",
      "Open a study workspace to manage budget versions and line items.",
      "Review accruals generated from study activity.",
      "Create and track invoices, then record payments.",
      "Manage participant stipends and outstanding balances.",
    ],
  },
  {
    title: "Results",
    id: "results",
    steps: [
      "Open Results and load a run by run ID.",
      "Review run status, match count, and execution timing.",
      "Cancel or retry runs when those actions are available.",
      "Review matched patient rows and matched rule reasons.",
      "Use Export CSV for completed runs.",
    ],
  },
];

export default function UserGuidePage() {
  return (
    <main className="container">
      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginBottom: "0.5rem" }}>CritMatch User Guide</h2>
        <p style={{ margin: 0, color: "var(--cm-muted)" }}>
          This guide is organized in the same order as the navigation bar modules.
          Use each section as a quick step-by-step workflow for day-to-day operations.
        </p>
        <div
          style={{
            marginTop: "0.9rem",
            display: "flex",
            flexWrap: "wrap",
            gap: "0.45rem",
          }}
        >
          {GUIDE_SECTIONS.map((section) => (
            <a key={section.id} href={`#${section.id}`} className="chip">
              {section.title}
            </a>
          ))}
        </div>
      </section>

      <div className="grid" style={{ gap: "1rem" }}>
        {GUIDE_SECTIONS.map((section) => (
          <section key={section.id} id={section.id} className="card">
            <h3 style={{ marginBottom: "0.55rem" }}>{section.title}</h3>
            <ol style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
              {section.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            {section.notes ? (
              <p style={{ margin: "0.85rem 0 0", color: "var(--cm-muted)", fontWeight: 700 }}>
                Note: {section.notes}
              </p>
            ) : null}
          </section>
        ))}
      </div>
    </main>
  );
}
