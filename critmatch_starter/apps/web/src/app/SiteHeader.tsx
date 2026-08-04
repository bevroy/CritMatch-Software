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
  { href: "/login", label: "Account", icon: "👤" },
  { href: "/studies", label: "Studies", icon: "📋" },
  { href: "/cohort", label: "Cohort Builder", icon: "🧩" },
  { href: "/feasibility", label: "Feasibility", icon: "📈" },
  { href: "/roie", label: "ROIE", icon: "🛰️" },
  { href: "/readiness", label: "Readiness", icon: "🧠" },
  { href: "/navigator", label: "Navigator", icon: "🧭" },
  { href: "/equity", label: "Equity", icon: "⚖️" },
  { href: "/edc", label: "EDC", icon: "📝" },
  { href: "/ctfms", label: "Finance", icon: "💳" },
  { href: "/results", label: "Results", icon: "📊" },
  { href: "/user-guide", label: "User Guide", icon: "📘" },
  { href: "/technical", label: "Technical", icon: "⚙️" },
];

type PageInfo = { title: string; subtitle: string };

const PAGE_INFO: Record<string, PageInfo> = {
  "/studies": { title: "Studies", subtitle: "Manage saved study definitions and cohort workspaces." },
  "/cohort": { title: "Cohort Builder", subtitle: "Define inclusion and exclusion rules with terminology expansion." },
  "/results": { title: "Results", subtitle: "Review, filter, and export candidate patient cohorts." },
  "/feasibility": { title: "Feasibility", subtitle: "Answer trial feasibility questionnaires from EMR data." },
  "/roie": { title: "ROIE", subtitle: "Research Opportunity Intelligence Engine for sponsor, site, and study targeting." },
  "/readiness": { title: "RWD Readiness", subtitle: "Assess readiness, estimate eligible populations, and generate sponsor-ready site profiles." },
  "/navigator": { title: "Navigator Workspace", subtitle: "Resolve participant barriers with closed-loop navigation workflows." },
  "/equity": { title: "Equity Scorecards", subtitle: "Monitor subgroup conversion and recommended equity interventions." },
  "/edc": { title: "EDC", subtitle: "Forms, participants, and EMR data points." },
  "/ctfms": { title: "Finance (CTFMS)", subtitle: "Budgets, accruals, invoices, payments, and patient stipends." },
  "/user-guide": { title: "User Guide", subtitle: "Step-by-step module workflows in navigation order." },
  "/technical": { title: "Technical", subtitle: "Architecture, stack, integrations, and deployment details." },
  "/audit": { title: "Audit", subtitle: "Review audit log entries across the platform." },
  "/login": { title: "Sign In", subtitle: "Authenticate to access CritMatch." },
  "/launch": { title: "SMART Launch", subtitle: "Authenticate from your EHR context." },
  "/auth": { title: "Authentication", subtitle: "Completing sign in…" },
  "/builder": { title: "Cohort Builder", subtitle: "Define inclusion and exclusion rules with terminology expansion." },
};

function getPageInfo(pathname: string): PageInfo | null {
  if (pathname === "/") return null;
  // Match longest prefix.
  const keys = Object.keys(PAGE_INFO).sort((a, b) => b.length - a.length);
  for (const k of keys) {
    if (pathname === k || pathname.startsWith(k + "/")) return PAGE_INFO[k];
  }
  return null;
}

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
    ? [...NAV_ITEMS.slice(0, -1), { href: "/audit", label: "Audit", icon: "🔍" }, NAV_ITEMS[NAV_ITEMS.length - 1]]
    : NAV_ITEMS;

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  }

  const isHome = pathname === "/";
  const pageInfo = getPageInfo(pathname);

  return (
    <>
      <div className="nav-card">
        <div className="nav-card-inner">
          <div className="nav-bar">
            <button
              type="button"
              className="nav-toggle"
              onClick={() => setNavOpen((o) => !o)}
              aria-expanded={navOpen}
            >
              <span className="nav-toggle-icon">≡</span>
              <span>Navigation</span>
              <span className="nav-toggle-chevron">{navOpen ? "▲" : "▼"}</span>
            </button>
            <div className="nav-session">
              {session ? (
                <>
                  <NotificationsBell />
                  <span className="session-meta">
                    {session.role}
                    {session.patient_context ? ` · patient ${session.patient_context}` : ""}
                  </span>
                  <button
                    className="button-secondary"
                    style={{ padding: "0.35rem 0.85rem", fontSize: "0.82rem" }}
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
                    style={{ padding: "0.35rem 0.85rem", fontSize: "0.82rem" }}
                    onClick={() => handleDevSignIn("research_user")}
                    disabled={signingIn}
                  >
                    Researcher
                  </button>
                  <button
                    className="button-secondary"
                    style={{ padding: "0.35rem 0.85rem", fontSize: "0.82rem" }}
                    onClick={() => handleDevSignIn("admin")}
                    disabled={signingIn}
                  >
                    Admin
                  </button>
                  <button
                    className="button-secondary"
                    style={{ padding: "0.35rem 0.85rem", fontSize: "0.82rem" }}
                    onClick={() => handleDevSignIn("auditor")}
                    disabled={signingIn}
                  >
                    Auditor
                  </button>
                </>
              ) : (
                <Link
                  href="/login"
                  className="button-secondary"
                  style={{ padding: "0.35rem 0.85rem", fontSize: "0.82rem" }}
                >
                  Sign in
                </Link>
              ) : null}
            </div>
          </div>
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

      {pageInfo && (
        <div className="page-header">
          <div className="page-header-inner">
            <Image
              src="/critmatch-logo-mark.png"
              alt=""
              width={216}
              height={110}
              className="page-header-logo"
            />
            <div className="page-header-text">
              <h1 className="page-header-title">{pageInfo.title}</h1>
              <p className="page-header-subtitle">{pageInfo.subtitle}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
