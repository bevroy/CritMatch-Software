# CritMatch-Software audit patches

This repository has been updated with the Claude-provided audit patch set, including:

- SMART issuer allowlist fail-closed behavior and id_token verification hardening.
- Query correctness fixes for demographic pagination truncation visibility, medication rules, and observation threshold handling.
- CSRF origin/referer guard for state-changing API calls.
- EDC signing fail-closed behavior when SESSION_SECRET is missing.
- EDC FHIR pull unit mismatch protection.
- CTFMS accrual enrollment status guard.
- ROIE preview observability header + production warning log.
- CI updates (frontend lint step + quoted sqlite URL).
- Non-root container users for API and worker images.
- Added .env.example files for API, web, and worker.
- Added index hints in ORM models (requires Alembic migration for existing DBs).

## Required frontend change

- GET /api/studies/_users/search now requires a study_id query parameter.

## Operational note

- The ORM index changes in app/db/models.py are schema intent only. Existing Postgres deployments must add a migration to create indexes in-place.

## Netlify note

- Root netlify.toml and critmatch_starter/apps/web/netlify.toml may differ; verify the active site base directory and remove unused duplication.
