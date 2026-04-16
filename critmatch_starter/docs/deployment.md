# Deployment Notes

## Netlify
- Base directory: `critmatch_starter/apps/web`
- Build command: `npm run build`
- Publish directory: `.next`
- Node version: `20`
- Recommended env vars:
	- `NEXT_PUBLIC_API_BASE_URL` (example: `https://critmatch-api.onrender.com`)
	- `NEXT_PUBLIC_SENTRY_DSN` (optional)

If Netlify does not auto-detect settings, import the repo and keep the root `netlify.toml` file enabled.

## Render
- Use Blueprint file: `render.yaml` at repo root
- API service root: `critmatch_starter/apps/api`
- Worker service root: `critmatch_starter/apps/worker`
- Managed Postgres database

Recommended manual env vars in Render:
- `SENTRY_DSN`
- `SESSION_SECRET`
- `SMART_CLIENT_ID`
- `SMART_CLIENT_SECRET`
- `SMART_ISSUER_ALLOWLIST`
- `FHIR_BASE_URL`
- `EXPORT_SIGNING_KEY`

After first deploy, set `FRONTEND_BASE_URL` in Render to your Netlify site URL.
