"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationItem,
} from "../lib/api";

const POLL_MS = 60_000;

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  const s = Math.max(1, Math.round((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export default function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  async function refresh() {
    try {
      const page = await fetchNotifications({ limit: 20 });
      setItems(page.items);
      setUnread(page.unread);
    } catch {
      /* not signed in or offline – stay silent */
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  async function handleOpen() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      await refresh();
      setLoading(false);
    }
  }

  async function handleMarkAll() {
    await markAllNotificationsRead();
    setUnread(0);
    setItems((prev) => prev.map((n) => ({ ...n, readAt: n.readAt ?? new Date().toISOString() })));
  }

  async function handleClick(n: NotificationItem) {
    if (!n.readAt) {
      try {
        await markNotificationRead(n.id);
        setUnread((u) => Math.max(0, u - 1));
        setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, readAt: new Date().toISOString() } : x)));
      } catch { /* noop */ }
    }
    setOpen(false);
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        aria-label="Notifications"
        onClick={handleOpen}
        style={{
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: "0.25rem 0.4rem",
          fontSize: "1.1rem",
          position: "relative",
          color: "#0f172a",
        }}
      >
        <span aria-hidden>🔔</span>
        {unread > 0 && (
          <span
            style={{
              position: "absolute",
              top: 0,
              right: 0,
              minWidth: "1.1rem",
              height: "1.1rem",
              padding: "0 0.3rem",
              borderRadius: "999px",
              background: "#dc2626",
              color: "white",
              fontSize: "0.65rem",
              fontWeight: 700,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              lineHeight: 1,
            }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 0.5rem)",
            right: 0,
            width: "min(360px, calc(100vw - 2rem))",
            background: "white",
            border: "1px solid #cbd5e1",
            borderRadius: "0.5rem",
            boxShadow: "0 10px 25px rgba(0,0,0,0.08)",
            zIndex: 50,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0.8rem", borderBottom: "1px solid #e2e8f0" }}>
            <strong style={{ fontSize: "0.9rem" }}>Notifications</strong>
            <button
              onClick={handleMarkAll}
              disabled={unread === 0}
              style={{ background: "transparent", border: "none", color: unread === 0 ? "#94a3b8" : "#1d4ed8", cursor: unread === 0 ? "default" : "pointer", fontSize: "0.8rem" }}
            >
              Mark all read
            </button>
          </div>
          <div style={{ maxHeight: "60vh", overflow: "auto" }}>
            {loading ? (
              <div style={{ padding: "1rem", color: "#475569" }}>Loading…</div>
            ) : items.length === 0 ? (
              <div style={{ padding: "1rem", color: "#94a3b8" }}>No notifications yet.</div>
            ) : (
              items.map((n) => {
                const Wrapper = (props: { children: React.ReactNode }) =>
                  n.link ? (
                    <Link href={n.link} onClick={() => handleClick(n)} style={{ textDecoration: "none", color: "inherit" }}>
                      {props.children}
                    </Link>
                  ) : (
                    <div onClick={() => handleClick(n)}>{props.children}</div>
                  );
                return (
                  <Wrapper key={n.id}>
                    <div
                      style={{
                        padding: "0.6rem 0.8rem",
                        borderBottom: "1px solid #f1f5f9",
                        background: n.readAt ? "white" : "#eff6ff",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ fontSize: "0.85rem", fontWeight: n.readAt ? 400 : 600 }}>{n.title}</div>
                      {n.body && <div style={{ fontSize: "0.78rem", color: "#475569", marginTop: "0.15rem" }}>{n.body}</div>}
                      <div style={{ fontSize: "0.7rem", color: "#94a3b8", marginTop: "0.2rem" }}>{timeAgo(n.createdAt)}</div>
                    </div>
                  </Wrapper>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
