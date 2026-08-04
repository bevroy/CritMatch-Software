"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, emailLogin, getMe, type SessionInfo } from "../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    const detail = (e.body as { detail?: string } | null)?.detail;
    return detail ? `${e.message} - ${detail}` : e.message;
  }
  return (e as Error).message ?? "Unknown error";
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [existingSession, setExistingSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((session) => {
        if (cancelled) {
          return;
        }
        setExistingSession(session);
        window.setTimeout(() => {
          router.replace("/studies");
        }, 1000);
      })
      .catch(() => {
        if (!cancelled) {
          // No active session, stay on sign-in page.
          setExistingSession(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCheckingSession(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await emailLogin(email.trim(), name.trim() || undefined);
      router.replace("/studies");
    } catch (err) {
      setError(describeError(err));
      setLoading(false);
    }
  }

  if (checkingSession) {
    return (
      <main className="container" style={{ maxWidth: 720 }}>
        <section className="card">
          <h1 style={{ marginBottom: "0.5rem" }}>Sign in to CritMatch</h1>
          <p style={{ color: "#5b7575", marginTop: 0 }}>Checking existing session...</p>
        </section>
      </main>
    );
  }

  if (existingSession) {
    return (
      <main className="container" style={{ maxWidth: 720 }}>
        <section className="card">
          <h1 style={{ marginBottom: "0.5rem" }}>You are already signed in</h1>
          <p style={{ color: "#5b7575", marginTop: 0 }}>
            Redirecting to studies as {existingSession.role}...
          </p>
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
            <button className="button" type="button" onClick={() => router.replace("/studies")}>
              Continue now
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="container" style={{ maxWidth: 720 }}>
      <section className="card">
        <h1 style={{ marginBottom: "0.5rem" }}>Sign in to CritMatch</h1>
        <p style={{ color: "#5b7575", marginTop: 0 }}>
          Access is restricted to organizational emails at
          {" "}<strong>critmatchresearch.com</strong> or <strong>elionyxhealth.com</strong>.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "grid", gap: "0.8rem", marginTop: "1rem" }}>
          <label style={{ display: "grid", gap: "0.35rem" }}>
            <span style={{ fontWeight: 700 }}>Work email</span>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(ev) => setEmail(ev.target.value)}
              placeholder="name@critmatchresearch.com"
              required
              autoComplete="email"
            />
          </label>

          <label style={{ display: "grid", gap: "0.35rem" }}>
            <span style={{ fontWeight: 700 }}>Display name (optional)</span>
            <input
              className="input"
              type="text"
              value={name}
              onChange={(ev) => setName(ev.target.value)}
              placeholder="Jane Doe"
              autoComplete="name"
            />
          </label>

          {error ? <div className="error">{error}</div> : null}

          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
            <button className="button" type="submit" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </button>
            <Link href="/launch" className="button-secondary">
              Sign in from EHR (SMART launch)
            </Link>
          </div>
        </form>
      </section>
    </main>
  );
}
