import { FormEvent, useEffect, useState } from "react";
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
  const [departmentId, setDepartmentId] = useState("");
  const [classification, setClassification] = useState("internal");
  const [accessScope, setAccessScope] = useState("department");
  const [file, setFile] = useState<File | null>(null);

  const uploadAllowed = canUpload(user);
  const choices = user.role === "administrator" ? departments : departments.filter((item) => item.id === user.department_id);

  async function refresh() {
    setDocuments(await api<DocumentItem[]>("/documents", {}, token));
  }

  useEffect(() => {
    void refresh().catch((caught) => setError(messageOf(caught)));
    void api<Department[]>("/departments", {}, token)
      .then((items) => {
        setDepartments(items);
        const own = items.find((item) => item.id === user.department_id);
        setDepartmentId(user.role === "administrator" ? items[0]?.id ?? "" : own?.id ?? "");
      })
      .catch((caught) => setError(messageOf(caught)));
  }, [token, user.department_id, user.role]);

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF or DOCX file");
      return;
    }
    setError("");
    const body = new FormData();
    body.set("title", title);
    body.set("department_id", departmentId);
    body.set("classification", classification);
    body.set("access_scope", accessScope);
    body.set("file", file);
    try {
      await api("/documents", { method: "POST", body }, token);
      setTitle("");
      setFile(null);
      await refresh();
    } catch (caught) {
      setError(messageOf(caught));
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
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label>
            Department
            <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              {choices.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Classification
            <select value={classification} onChange={(event) => setClassification(event.target.value)}>
              <option value="internal">internal</option>
              <option value="confidential">confidential</option>
            </select>
          </label>
          <label>
            Access
            <select value={accessScope} onChange={(event) => setAccessScope(event.target.value)}>
              <option value="department">department</option>
              <option value="restricted">restricted</option>
            </select>
          </label>
          <label>
            File
            <input
              type="file"
              accept=".pdf,.docx,application/pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="button" type="submit">
            Upload
          </button>
        </form>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Department</th>
            <th>Access</th>
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
              <td>{document.department_name}</td>
              <td>
                {document.access_scope} · {document.classification}
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
  return caught instanceof ApiError ? caught.message : "Documents could not be loaded";
}
