# CritMatch

CritMatch is an EHR-embedded cohort identification application for research and related operational use cases.

## Modules
- Research Opportunity Intelligence Engine (ROIE)
- Real-World Data & Research Readiness Engine
- Community Partner Network
- Navigator Workspace
- Equity Scorecards
- Cohort Builder
- Results
- Feasibility
- EDC
- Finance (CTFMS)

## Competitive position
- Unified workflow: Moves teams from cohort identification through navigation and enrollment operations in one platform.
- Intelligence advantage: Combines ROIE opportunity discovery with readiness analytics to focus on winnable studies.
- Equity-native operations: Tracks subgroup conversion and intervention outcomes continuously, not only in retrospective reports.

### ROIE functions
- Study Discovery: Continuously searches ClinicalTrials.gov for relevant studies.
- Site Matching: Identifies studies aligned with site populations.
- Feasibility Prediction: Predicts enrollment potential.
- Sponsor Targeting: Suggests sponsors likely to benefit from site participation.
- Geographic Analysis: Identifies underserved research regions.
- Diversity Forecasting: Predicts enrollment diversity potential.

### Real-World Data & Research Readiness Engine functions
- Research Readiness Assessment: Scores site-level research readiness.
- Eligible Population Estimation: Estimates protocol-fit patient populations.
- Feasibility Support: Surfaces feasibility tiering for candidate studies.
- Care Gap Identification: Highlights operational and clinical care gaps.
- Sponsor-Ready Profiles: Generates sponsor-facing site summaries.

### Community Partner Network functions
- Partner Directory: Tracks participating CBO, FQHC, and health-system partners.
- Referral Visibility: Monitors active referrals and enrollment outcomes.
- Language Access Insights: Surfaces language needs across partner populations.

### Navigator Workspace functions
- Barrier Queue: Organizes participant-level barriers (transportation, language, childcare, digital access).
- Task Management: Assigns and tracks navigator actions by due date and status.
- Resolution Metrics: Summarizes throughput and median barrier resolution time.

### Equity Scorecard functions
- Subgroup Conversion Monitoring: Compares screened-to-enrolled outcomes by subgroup.
- Equity Alerts: Flags participation disparities and enrollment lag.
- Intervention Guidance: Recommends targeted equity remediation actions.

## Stack
- Frontend: Next.js
- Hosting: Netlify
- Backend: FastAPI
- API hosting: Render
- Database: Render Postgres
- Monitoring: Sentry
- Source control / CI: GitHub + GitHub Actions

## Repository layout
```text
apps/
  web/      # Next.js frontend
  api/      # FastAPI backend
  worker/   # background jobs
.github/
  workflows/
docs/
```

## Local development

### Frontend
```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

### Backend
```bash
cd apps/api
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Worker
```bash
cd apps/worker
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

## Deployment
- Netlify deploys the frontend from `critmatch_starter/apps/web`
- Render deploys the API from `critmatch_starter/apps/api`
- Render deploys the worker from `critmatch_starter/apps/worker`
- Render provisions the Postgres database
