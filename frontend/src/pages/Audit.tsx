import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import type { AuditEvent } from "../types";

export function Audit() {
  const { token, user } = useAuth();
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const admin = user.role === "administrator";

  useEffect(() => {
    if (!admin) {
      return;
    }
    void api<AuditEvent[]>("/audit?limit=100", {}, token)
      .then(setRows)
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : "Audit log unavailable"));
  }, [token, admin]);

  if (!admin) {
    return <Navigate to="/documents" replace />;
  }

  return (
    <section className="page">
      <h1>Audit</h1>
      <p className="lede">Security-sensitive actions. Rows keep ids and outcomes, not document text or answers.</p>
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Who</th>
            <th>Action</th>
            <th>Outcome</th>
            <th>Resource</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>{row.actor_email || "unknown"}</td>
              <td>{row.action}</td>
              <td>
                <span className={`badge outcome-${row.outcome}`}>{row.outcome}</span>
              </td>
              <td className="muted">
                {row.resource_type} {row.resource_id ? row.resource_id.slice(0, 8) : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
