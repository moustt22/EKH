import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api";
import { canUpload, useAuth } from "../auth";
import type { Department, DocumentItem } from "../types";

export function Documents() {
  const { token, user } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [departmentIds, setDepartmentIds] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const refreshSequence = useRef(0);

  const uploadAllowed = canUpload(user);
  const choices = user.role === "administrator" ? departments : departments.filter((item) => item.id === user.department_id);

  async function refresh() {
    const sequence = ++refreshSequence.current;
    try {
      const next = await api<DocumentItem[]>("/documents", {}, token);
      if (sequence === refreshSequence.current) {
        setDocuments(next);
        setError("");
      }
    } catch (caught) {
      if (sequence === refreshSequence.current) {
        setError(messageOf(caught));
      }
    }
  }

  useEffect(() => {
    void refresh();
    void api<Department[]>("/departments", {}, token)
      .then((items) => {
        setDepartments(items);
        const own = items.find((item) => item.id === user.department_id);
        setDepartmentIds(user.role === "administrator" ? (items[0]?.id ? [items[0].id] : []) : own?.id ? [own.id] : []);
        setError("");
      })
      .catch((caught) => setError(messageOf(caught)));
  }, [token, user.department_id, user.role]);

  useEffect(() => {
    if (!documents.some((document) => document.status === "processing")) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [documents, token]);

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    if (selected && !title.trim()) {
      setTitle(selected.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim());
    }
  }

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) {
      setError("Choose a PDF or DOCX file");
      return;
    }
    if (departmentIds.length === 0) {
      setError("Choose a department before uploading");
      return;
    }
    setError("");
    setUploading(true);
    const body = new FormData();
    body.set("title", title);
    for (const id of departmentIds) {
      body.append("department_ids", id);
    }
    body.set("file", file);
    try {
      await api("/documents", { method: "POST", body }, token);
      setTitle("");
      setFile(null);
      const input = form.elements.namedItem("document-file");
      if (input instanceof HTMLInputElement) {
        input.value = "";
      }
      await refresh();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="page">
      <h1>Documents</h1>
      <p className="lede">
        {user.role === "employee"
          ? "You can read documents shared with your department or granted to you."
          : user.role === "department_manager"
            ? `You manage documents for ${user.department_name}.`
            : "You manage every department."}
      </p>
      {uploadAllowed ? (
        <form className="card form-grid" onSubmit={(event) => void onUpload(event)}>
          <label>
            Document name <span className="muted">(optional)</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Leave blank to use the file name"
            />
          </label>
          {user.role === "administrator" ? (
            <label>
              Owning teams <span className="muted">(hold Ctrl to choose more than one)</span>
              <select
                multiple
                value={departmentIds}
                onChange={(event) =>
                  setDepartmentIds(Array.from(event.target.selectedOptions, (option) => option.value))
                }
              >
                {choices.map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p className="muted">This document will be available to the {user.department_name} team.</p>
          )}
          <label>
            PDF or DOCX file
            <input
              name="document-file"
              type="file"
              accept=".pdf,.docx,application/pdf"
              onChange={onFileChange}
            />
          </label>
          <button className="button" type="submit" disabled={uploading || departmentIds.length === 0}>
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </form>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Department</th>
            <th>Who can see it</th>
            <th>Status</th>
            <th>Version</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>
                <Link to={`/documents/${document.id}`}>{document.title}</Link>
              </td>
              <td>{document.department_names?.join(", ") || document.department_name}</td>
              <td>
                {document.access_scope === "restricted"
                  ? "Selected people"
                  : `${document.department_names?.join(", ") || document.department_name} team`}
              </td>
              <td>
                <span className={`badge status-${document.status}`}>{document.status}</span>
              </td>
              <td>{document.current_version}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {documents.length === 0 ? <p className="empty">No documents are visible to you yet.</p> : null}
    </section>
  );
}

function messageOf(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  if (caught instanceof Error && caught.message) {
    return caught.message;
  }
  return "Documents could not be loaded. Please try again.";
}
