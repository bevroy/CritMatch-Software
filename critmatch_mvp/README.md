# CritMatch MVP Starter

This is a repo-ready MVP architecture for CritMatch under Elionyx Health.

## What is included

- FastAPI backend with `POST /match`
- Sample patient JSON dataset
- Simple matching engine with inclusion/exclusion logic
- Terminology normalization for common synonyms
- Next.js-style demo page and React component

## Backend install

Copy these files into your repo:

```text
backend/main.py
backend/routers/match_router.py
backend/schemas/match.py
backend/services/matching_engine.py
backend/services/terminology.py
backend/data/sample_patients.json
```

Start backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

Test:

```text
/health
/docs
```

## Frontend install

Copy these files into your frontend:

```text
app/demo/page.tsx
components/CritMatchDemo.tsx
lib/api.ts
lib/types.ts
```

If your app uses `src/`, place them under `src/app`, `src/components`, and `src/lib`.

Set `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Run:

```bash
npm install
npm run dev
```

Open:

```text
/demo
```

## Demo trial

Default demo screens for a heart failure + diabetes study:

- Inclusion: age 18-75, heart failure, HbA1c > 8
- Exclusion: stroke, warfarin, pregnancy, eGFR < 30

## Next enhancements

- Upload CSV patient dataset
- Add FHIR Patient / Condition / Observation mapping
- Add study-specific saved trials
- Add coordinator review workflow
- Add EHR launch context for Epic / Oracle Health
