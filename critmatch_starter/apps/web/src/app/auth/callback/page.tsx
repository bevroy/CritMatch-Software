"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { smartAuthorize, smartCallback, ApiError } from "../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<string>("Connecting to your EHR…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const iss = params.get("iss");
    const launch = params.get("launch");
    const code = params.get("code");
    const state = params.get("state");
    const err = params.get("error");

    if (err) {
      setError(`EHR returned: ${err} ${params.get("error_description") || ""}`);
      return;
    }

    // Phase 2: returning from EHR with auth code → exchange for session
    if (code && state) {
      setStatus("Completing sign-in…");
      smartCallback(code, state)
        .then(() => router.replace("/studies"))
        .catch((e: unknown) => setError(describeError(e)));
      return;
    }

    // Phase 1: initial EHR launch → start authorization
    if (iss) {
      setStatus("Starting SMART launch…");
      smartAuthorize(iss, launch)
        .then((res) => window.location.replace(res.authorize_url))
        .catch((e: unknown) => setError(describeError(e)));
      return;
    }

    setError("Missing launch parameters. Open CritMatch from your EHR.");
  }, [params, router]);

  return (
    <main className="container">
      <div className="card">
        <h1>SMART on FHIR</h1>
        {error ? (
          <p style={{ color: "#b91c1c" }}>{error}</p>
        ) : (
          <p>{status}</p>
        )}
      </div>
    </main>
  );
}

export default function SmartCallbackPage() {
  return (
    <Suspense fallback={<main className="container"><div className="card">Loading…</div></main>}>
      <CallbackInner />
    </Suspense>
  );
}
