# SMART on FHIR Notes

Required environment variables:
- SMART_CLIENT_ID
- SMART_CLIENT_SECRET
- SMART_ISSUER_ALLOWLIST
- FHIR_BASE_URL
- NEXT_PUBLIC_SMART_REDIRECT_URI

Expected flow:
1. EHR launches CritMatch with SMART context.
2. Frontend receives launch parameters.
3. Backend exchanges authorization code or validates token.
4. Backend stores session context.
5. Backend queries permitted FHIR resources.
