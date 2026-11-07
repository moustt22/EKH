import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import type { SearchHit } from "../types";

export function Search() {
  const { token } = useAuth();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const params = new URLSearchParams({ q: query.trim() });
      setHits(await api<SearchHit[]>(`/search?${params}`, {}, token));
    } catch (caught) {
      setHits(null);
      setError(caught instanceof ApiError ? caught.message : "Search failed");
    }
  }

  return (
    <section className="page">
      <h1>Search</h1>
      <p className="lede">Results are limited to documents you can read. A department filter cannot widen that.</p>
      <form className="search-bar" onSubmit={(event) => void onSubmit(event)}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="salary bands, leave, on call" />
        <button className="button" type="submit">
          Search
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {hits && hits.length === 0 ? <p className="empty">No documents you can read matched that search.</p> : null}
      <ul className="hits">
        {hits?.map((hit) => (
          <li key={hit.chunk_id}>
            <div className="hit-title">
              <Link to={`/documents/${hit.document_id}`}>{hit.title}</Link>
              <span className="badge">{hit.department_name}</span>
            </div>
            <p className="muted">
              Page {hit.page}
              {hit.section ? ` · ${hit.section}` : ""} · version {hit.version}
            </p>
            <p>{hit.snippet}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
