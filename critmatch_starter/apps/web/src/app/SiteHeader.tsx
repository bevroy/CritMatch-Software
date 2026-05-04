"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, usePathname } from "next/navigation";
import {
  devLogin,
  devLoginEnabled,
  getMe,
  logout,
  type SessionInfo,
} from "../lib/api";
import NotificationsBell from "./NotificationsBell";

type NavItem = { href: string; label: string; icon: string };

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: "🏠" },
  { href: "/studies", label: "Studies", icon: "📋" },
  { href: "/cohort", label: "Cohort Builder", icon: "🧩" },
  { href: "/feasibility", label: "Feasibility", icon: "📈" },
  { href: "/edc", label: "EDC", icon: "📝" },
  { href: "/ctfms", label: "Finance", icon: "💳" },
  { href: "/results", label: "Results", icon: "📊" },
];

export default function SiteHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [devAvailable, setDevAvailable] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    getMe()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    if (!loaded || session) return;
    devLoginEnabled()
      .then((r) => setDevAvailable(!!r.enabled))
      .catch(() => setDevAvailable(false));
  }, [loaded, session]);

  // Collapse the navigation tile grid whenever the route changes.
  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  async function handleLogout() {
    try { await logout(); } catch { /* noop */ }
    setSession(null);
    router.push("/");
  }

  async function handleDevSignIn(role: "research_user" | "admin" | "auditor") {
    setSigningIn(true);
    try {
      await devLogin(role);
      window.location.reload();
    } catch {
      setSigningIn(false);
    }
  }

  const showAudit = loaded && session && (session.role === "admin" || session.role === "auditor");
  const navItems: NavItem[] = showAudit
    ? [...NAV_ITEMS, { href: "/audit", label: "Audit", icon: "🔍" }]
    : NAV_ITEMS;

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <>
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
            <span style={{ display: "flex", flexDirection: "column" }}>
              <span className="brand-name">CritMatch</span>
              <span className="brand-tagline">EHR Cohort Identification</span>
            </span>
          </Link>
          <div className="session-controls">
            {loaded && session ? (
              <>
                <NotificationsBell />
                <span className="session-meta">
                  {session.role}
                  {session.patient_context ? ` · patient ${session.patient_context}` : ""}
                </span>
                <button
                  className="button-secondary"
                  style={{ padding: "0.4rem 0.95rem", fontSize: "0.85rem" }}
                  onClick={handleLogout}
                >
                  Sign out
                </button>
              </>
            ) : loaded && devAvailable ? (
              <>
                <span className="session-meta">Dev sign in:</span>
                <button
                  className="button"
                  style={{ padding: "0.4rem 0.95rem", fontSize: "0.85rem" }}
                  onClick={() => handleDevSignIn("research_user")}
                  disabled={signingIn}
                >
                  Researcher
                </button>
                <button
                  className="button-secondary"
                  style={{ padding: "0.4rem 0.95rem", fontSize: "0.85rem" }}
                  onClick={() => handleDevSignIn("admin")}
                  disabled={signingIn}
                >
                  Admin
                </button>
                <button
                  className="button-secondary"
                  style={{ padding: "0.4rem 0.95rem", fontSize: "0.85rem" }}
                  onClick={() => handleDevSignIn("auditor")}
                  disabled={signingIn}
                >
                  Auditor
                </button>
              </>
            ) : loaded ? (
              <Link href="/launch" className="button-secondary" style={{ padding: "0.4rem 0.95rem", fontSize: "0.85rem" }}>
                Sign in
              </Link>
            ) : null}
          </div>
        </div>
      </header>

      <div className="nav-card">
        <div className="nav-card-inner">
          <button
            type="button"
            className="nav-toggle"
            onClick={() => setNavOpen((o) => !o)}
            aria-expanded={navOpen}
          >
            <span className="nav-toggle-icon">≡</span>
            <span>Navigation</span>
            <span style={{ marginLeft: "auto", fontSize: "0.85rem", opacity: 0.7 }}>
              {navOpen ? "▲" : "▼"}
            </span>
          </button>
          {navOpen && (
            <div className="nav-tiles">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-tile${isActive(item.href) ? " active" : ""}`}
                >
                  <span className="nav-tile-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
