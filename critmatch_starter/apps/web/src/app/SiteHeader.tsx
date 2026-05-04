"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  devLogin,
  devLoginEnabled,
  getMe,
  logout,
  type SessionInfo,
} from "../lib/api";
import NotificationsBell from "./NotificationsBell";

export default function SiteHeader() {
  const router = useRouter();
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [devAvailable, setDevAvailable] = useState(false);
  const [signingIn, setSigningIn] = useState(false);

  useEffect(() => {
    getMe()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setLoaded(true));
  }, []);

  // Probe dev login availability whenever we don't have a session.
  useEffect(() => {
    if (!loaded || session) return;
    devLoginEnabled()
      .then((r) => setDevAvailable(!!r.enabled))
      .catch(() => setDevAvailable(false));
  }, [loaded, session]);

  async function handleLogout() {
    try { await logout(); } catch { /* noop */ }
    setSession(null);
    router.push("/");
  }

  async function handleDevSignIn(role: "research_user" | "admin" | "auditor") {
    setSigningIn(true);
    try {
      await devLogin(role);
      // Reload to refresh server-side state (cookies, role-gated nav).
      window.location.reload();
    } catch {
      setSigningIn(false);
    }
  }

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/" className="brand">
          <Image
            src="/critmatch-logo.png"
            alt="CritMatch logo"
            width={552}
            height={138}
            priority
            className="brand-logo"
          />
        </Link>
        <nav style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <Link href="/studies">Studies</Link>
          <Link href="/cohort">Cohort Builder</Link>
          <Link href="/feasibility">Feasibility</Link>
          <Link href="/edc">EDC</Link>
          <Link href="/ctfms">Finance</Link>
          <Link href="/results">Results</Link>
          {loaded && session && (session.role === "admin" || session.role === "auditor") ? (
            <Link href="/audit">Audit</Link>
          ) : null}
          {loaded && session ? (
            <>
              <NotificationsBell />
              <span style={{ color: "#475569", fontSize: "0.875rem" }}>
                {session.role}
                {session.patient_context ? ` · patient ${session.patient_context}` : ""}
              </span>
              <button
                className="button"
                style={{ padding: "0.25rem 0.75rem" }}
                onClick={handleLogout}
              >
                Sign out
              </button>
            </>
          ) : loaded && devAvailable ? (
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Dev sign in:</span>
              <button
                className="button"
                style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
                onClick={() => handleDevSignIn("research_user")}
                disabled={signingIn}
              >
                Researcher
              </button>
              <button
                className="button"
                style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem", background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
                onClick={() => handleDevSignIn("admin")}
                disabled={signingIn}
              >
                Admin
              </button>
              <button
                className="button"
                style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem", background: "white", color: "#0f172a", border: "1px solid #cbd5e1" }}
                onClick={() => handleDevSignIn("auditor")}
                disabled={signingIn}
              >
                Auditor
              </button>
            </div>
          ) : loaded ? (
            <Link href="/launch" style={{ color: "#475569", fontSize: "0.875rem" }}>
              Sign in
            </Link>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
