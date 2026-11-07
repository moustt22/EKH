import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError, downloadDocument } from "../api";
import { canManageDocument, useAuth } from "../auth";
import type { DocumentItem, Grant, Job } from "../types";

export function DocumentDetail() {
  const { id = "" } = useParams();
  const { token, user } = useAuth();
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const manageable = document ? canManageDocument(user, document.department_id) : false;

  async function load() {
    const next = await api<DocumentItem>(`/documents/${id}`, {}, token);
    setDocument(next);
    setJob(await api<Job>(`/documents/${id}/jobs/latest`, {}, token).catch(() => null));
    if (canManageDocument(user, next.department_id)) {
      setGrants(await api<Grant[]>(`/documents/${id}/permissions`, {}, token));
    }
  }

  useEffect(() => {
    let cancelled = false;
    load()
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Document unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, token]);

  useEffect(() => {
    if (!document || document.status !== "processing") {
      return;
    }
    const timer = window.setInterval(() => {
      void load().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [document?.status, id, token]);

  async function onDownload() {
    if (!document) {
      return;
    }
    setError("");
    try {
      await downloadDocument(document.id, document.original_filename, token);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Download failed");
    }
  }

  async function onGrant(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/documents/${id}/permissions`, { method: "POST", body: JSON.stringify({ email }) }, token);
      setEmail("");
      setNotice("Read access granted.");
      setGrants(await api<Grant[]>(`/documents/${id}/permissions`, {}, token));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Grant failed");
    }
  }

  async function revoke(userId: string) {
    await api(`/documents/${id}/permissions/${userId}`, { method: "DELETE" }, token);
    setGrants(await api<Grant[]>(`/documents/${id}/permissions`, {}, token));
  }

  async function retry() {
    setError("");
    try {
      await api(`/documents/${id}/retry`, { method: "POST" }, token);
      setNotice("Indexing queued again.");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Retry failed");
    }
  }

  async function remove() {
    await api(`/documents/${id}`, { method: "DELETE" }, token);
    window.location.assign("/documents");
  }

  if (!document && error) {
    return (
      <section className="page">
        <p className="error">{error}</p>
        <Link to="/documents">Back to documents</Link>
      </section>
    );
  }

  if (!document) {
    return <p className="boot">Loading document…</p>;
  }

  return (
    <section className="page">
      <p className="eyebrow">
        <Link to="/documents">Documents</Link>
      </p>
      <h1>{document.title}</h1>
      <p className="muted">
        Team: {document.department_name} · version {document.current_version} · {document.file_type.toUpperCase()}
      </p>
      <div className="row">
        <span className={`badge status-${document.status}`}>{document.status}</span>
        {job ? <span className="muted">Indexing: {job.status}{job.error ? ` — ${job.error}` : ""}</span> : null}
      </div>
      <div className="row">
        <button className="button" type="button" onClick={() => void onDownload()}>
          Download
        </button>
        {manageable && (document.status === "failed" || job?.status === "failed") ? (
          <button className="button secondary" type="button" onClick={() => void retry()}>
            Retry indexing
          </button>
        ) : null}
        {manageable ? (
          <button className="button danger" type="button" onClick={() => void remove()}>
            Delete
          </button>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p className="notice">{notice}</p> : null}
      {manageable ? (
        <section className="card">
          <h2>Grants</h2>
          <p className="muted">A grant lets someone outside this department read the file.</p>
          <ul className="plain">
            {grants.map((grant) => (
              <li key={grant.user_id}>
                <span>
                  {grant.name} · {grant.email}
                </span>
                <button type="button" onClick={() => void revoke(grant.user_id)}>
                  Revoke
                </button>
              </li>
            ))}
          </ul>
          {grants.length === 0 ? <p className="empty">No extra readers.</p> : null}
          <form className="row" onSubmit={(event) => void onGrant(event)}>
            <input
              type="email"
              placeholder="person@northwind.example"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <button className="button" type="submit">
              Grant read
            </button>
          </form>
        </section>
      ) : null}
    </section>
  );
}
