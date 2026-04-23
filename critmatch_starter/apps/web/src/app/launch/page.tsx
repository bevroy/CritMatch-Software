"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { smartAuthorize, ApiError } from "../../lib/api";

function LaunchInner() {
  const params = useSearchParams();
  const [status, setStatus] = useState("Starting SMART launch…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const iss = params.get("iss");
    const launch = params.get("launch");
    if (!iss) {
      setError("Missing iss parameter. Launch CritMatch from your EHR.");
      return;
    }
    smartAuthorize(iss, launch)
      .then((res) => window.location.replace(res.authorize_url))
      .catch((e: unknown) => {
        if (e instanceof ApiError) {
          setError(`${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`);
        } else {
          setError((e as Error).message);
        }
      });
  }, [params]);

  return (
    <main className="container">
      <div className="card">
        <h1>CritMatch SMART Launch</h1>
        {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : <p>{status}</p>}
      </div>
    </main>
  );
}

export default function LaunchPage() {
  return (
    <Suspense fallback={<main className="container"><div className="card">Loading…</div></main>}>
      <LaunchInner />
    </Suspense>
  );
}
