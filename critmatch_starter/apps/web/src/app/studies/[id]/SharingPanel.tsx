"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  addCollaborator,
  fetchCollaborators,
  removeCollaborator,
  searchUsers,
  transferStudy,
  type CollaboratorList,
  type UserSearchResult,
} from "../../../lib/api";

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.message}${e.body ? ` – ${JSON.stringify(e.body)}` : ""}`;
  }
  return (e as Error).message ?? "Unknown error";
}

interface SharingPanelProps {
  studyId: string;
  onOwnerChanged?: () => void;
}

export default function SharingPanel({ studyId, onOwnerChanged }: SharingPanelProps) {
  const [data, setData] = useState<CollaboratorList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [results, setResults] = useState<UserSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [pendingRole, setPendingRole] = useState<"viewer" | "editor">("viewer");
  const [working, setWorking] = useState(false);

  async function load() {
    setError(null);
    try {
      setData(await fetchCollaborators(studyId));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyId]);

  // Debounced user search.
  useEffect(() => {
    const term = search.trim();
    if (term.length < 1) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        setResults(await searchUsers(term, 10));
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  if (loading) {
    return (
      <section className="card" style={{ marginTop: "1rem" }}>
        <h2>Sharing</h2>
        <p style={{ color: "#94a3b8" }}>Loading…</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="card" style={{ marginTop: "1rem" }}>
        <h2>Sharing</h2>
        <p style={{ color: "#b91c1c" }}>{error ?? "Could not load collaborators."}</p>
      </section>
    );
  }

  const canManage = data.myAccess === "owner" || data.myAccess === "admin";

  async function handleAdd(target: UserSearchResult) {
    if (!canManage) return;
    setWorking(true);
    setError(null);
    try {
      await addCollaborator(studyId, target.id, pendingRole);
      setSearch("");
      setResults([]);
      await load();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setWorking(false);
    }
  }

  async function handleRemove(userId: string) {
    if (!canManage) return;
    setWorking(true);
    setError(null);
    try {
      await removeCollaborator(studyId, userId);
      await load();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setWorking(false);
    }
  }

  async function handleTransfer(userId: string) {
    if (!canManage) return;
    if (!confirm("Transfer ownership? You will lose owner privileges on this study.")) return;
    setWorking(true);
    setError(null);
    try {
      await transferStudy(studyId, userId);
      await load();
      onOwnerChanged?.();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="card" style={{ marginTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ margin: 0 }}>Sharing</h2>
        <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Your access: <strong>{data.myAccess}</strong></span>
      </div>

      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}

      <div style={{ marginTop: "0.75rem" }}>
        <strong>Owner:</strong>{" "}
        {data.owner ? (
          <>
            {data.owner.name}
            {data.owner.email ? <span style={{ color: "#94a3b8" }}> · {data.owner.email}</span> : null}
          </>
        ) : (
          <span style={{ color: "#94a3b8" }}>none</span>
        )}
      </div>

      <h3 style={{ marginTop: "1rem", marginBottom: "0.25rem", fontSize: "0.95rem" }}>
        Collaborators ({data.items.length})
      </h3>
      {data.items.length === 0 ? (
        <p style={{ color: "#94a3b8", margin: 0 }}>No collaborators yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((c) => (
              <tr key={c.userId}>
                <td>
                  {c.name ?? c.userId.slice(0, 8) + "…"}
                  {c.email ? <span style={{ color: "#94a3b8" }}> · {c.email}</span> : null}
                </td>
                <td><code style={{ fontSize: "0.85rem" }}>{c.role}</code></td>
                <td style={{ color: "#475569", fontSize: "0.85rem" }}>{new Date(c.createdAt).toLocaleDateString()}</td>
                <td style={{ display: "flex", gap: "0.5rem" }}>
                  {canManage && (
                    <>
                      <button
                        onClick={() => handleTransfer(c.userId)}
                        disabled={working}
                        style={{ background: "transparent", border: "1px solid #cbd5e1", padding: "0.2rem 0.5rem", borderRadius: "0.5rem", cursor: "pointer", fontSize: "0.8rem" }}
                      >
                        Make owner
                      </button>
                      <button
                        onClick={() => handleRemove(c.userId)}
                        disabled={working}
                        style={{ background: "transparent", border: "1px solid #fecaca", color: "#b91c1c", padding: "0.2rem 0.5rem", borderRadius: "0.5rem", cursor: "pointer", fontSize: "0.8rem" }}
                      >
                        Remove
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {canManage && (
        <div style={{ marginTop: "1rem", borderTop: "1px solid #e2e8f0", paddingTop: "0.75rem" }}>
          <h3 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "0.95rem" }}>Add collaborator</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "0.5rem" }}>
            <input
              className="input"
              placeholder="Search by name, email, or EHR id"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select className="select" value={pendingRole} onChange={(e) => setPendingRole(e.target.value as "viewer" | "editor")}>
              <option value="viewer">viewer</option>
              <option value="editor">editor</option>
            </select>
          </div>
          {searching ? (
            <p style={{ color: "#94a3b8", margin: "0.5rem 0 0" }}>Searching…</p>
          ) : results.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0", border: "1px solid #e2e8f0", borderRadius: "0.5rem" }}>
              {results.map((u) => (
                <li
                  key={u.id}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.4rem 0.6rem", borderBottom: "1px solid #f1f5f9" }}
                >
                  <span>
                    {u.name}
                    {u.email ? <span style={{ color: "#94a3b8" }}> · {u.email}</span> : null}
                    <span style={{ color: "#94a3b8", marginLeft: "0.5rem", fontSize: "0.75rem" }}>({u.role})</span>
                  </span>
                  <button
                    className="button"
                    style={{ padding: "0.2rem 0.6rem", fontSize: "0.8rem" }}
                    disabled={working}
                    onClick={() => handleAdd(u)}
                  >
                    Add as {pendingRole}
                  </button>
                </li>
              ))}
            </ul>
          ) : search.trim() ? (
            <p style={{ color: "#94a3b8", margin: "0.5rem 0 0" }}>No matching users.</p>
          ) : null}
        </div>
      )}
    </section>
  );
}
