# CritMatch

CritMatch is an EHR-embedded cohort identification application for research and related operational use cases.

## Modules
- Cohort Builder
- Results
- Feasibility
- EDC
- Finance (CTFMS)
- Research Opportunity Intelligence Engine (ROIE)

### ROIE functions
- Study Discovery: Continuously searches ClinicalTrials.gov for relevant studies.
- Site Matching: Identifies studies aligned with site populations.
- Feasibility Prediction: Predicts enrollment potential.
- Sponsor Targeting: Suggests sponsors likely to benefit from site participation.
- Geographic Analysis: Identifies underserved research regions.
- Diversity Forecasting: Predicts enrollment diversity potential.

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
