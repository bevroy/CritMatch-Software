"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { getMe, logout, type SessionInfo } from "../lib/api";

export default function SiteHeader() {
  const router = useRouter();
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getMe()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setLoaded(true));
  }, []);

  async function handleLogout() {
    try { await logout(); } catch { /* noop */ }
    setSession(null);
    router.push("/");
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
          <Link href="/builder">Builder</Link>
          <Link href="/results">Results</Link>
          {loaded && session ? (
            <>
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
          ) : loaded ? (
            <span style={{ color: "#94a3b8", fontSize: "0.875rem" }}>Not signed in</span>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
