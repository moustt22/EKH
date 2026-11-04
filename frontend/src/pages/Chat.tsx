import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import type { Conversation, ConversationDetail } from "../types";

export function Chat() {
  const { token } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  async function refreshList() {
    setConversations(await api<Conversation[]>("/conversations", {}, token));
  }

  useEffect(() => {
    void refreshList().catch((caught) => setError(messageOf(caught)));
  }, [token]);

  useEffect(() => {
    if (!id) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    api<ConversationDetail>(`/conversations/${id}`, {}, token)
      .then((next) => {
        if (!cancelled) {
          setDetail(next);
        }
      })
      .catch((caught) => setError(messageOf(caught)));
    return () => {
      cancelled = true;
    };
  }, [id, token]);

  async function startConversation() {
    setError("");
    const created = await api<Conversation>("/conversations", { method: "POST", body: "{}" }, token);
    await refreshList();
    navigate(`/chat/${created.id}`);
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!id || !draft.trim()) {
      return;
    }
    setSending(true);
    setError("");
    try {
      await api(`/conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ content: draft.trim() }) }, token);
      setDraft("");
      setDetail(await api<ConversationDetail>(`/conversations/${id}`, {}, token));
      await refreshList();
    } catch (caught) {
      setError(messageOf(caught));
      if (id) {
        setDetail(await api<ConversationDetail>(`/conversations/${id}`, {}, token).catch(() => detail));
      }
    } finally {
      setSending(false);
    }
  }

  async function removeConversation(conversationId: string) {
    await api(`/conversations/${conversationId}`, { method: "DELETE" }, token);
    if (conversationId === id) {
      navigate("/chat");
    }
    await refreshList();
  }

  return (
    <div className="split">
      <section className="pane list-pane">
        <div className="pane-head">
          <h1>Ask</h1>
          <button className="button" type="button" onClick={() => void startConversation()}>
            New
          </button>
        </div>
        <ul className="conversation-list">
          {conversations.map((conversation) => (
            <li key={conversation.id} className={conversation.id === id ? "selected" : ""}>
              <Link to={`/chat/${conversation.id}`}>{conversation.title}</Link>
              <button type="button" onClick={() => void removeConversation(conversation.id)} aria-label="Delete conversation">
                ×
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="pane thread">
        {!detail ? <p className="empty">Start a conversation. History is used only to understand follow-up questions.</p> : null}
        <div className="messages">
          {detail?.messages.map((message) => (
            <article key={message.id} className={`bubble ${message.role}`}>
              <p>{message.content}</p>
              {message.citations.length > 0 ? (
                <ul className="citations">
                  {message.citations.map((citation) => (
                    <li key={`${citation.document_id}-${citation.page}-${citation.passage}`}>
                      <Link to={`/documents/${citation.document_id}`}>
                        {citation.title}, page {citation.page}, version {citation.version}
                      </Link>
                      <blockquote>{citation.passage}</blockquote>
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
        {error ? <p className="error">{error}</p> : null}
        <form className="composer" onSubmit={(event) => void send(event)}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={id ? "Ask about a document you can read" : "Create a conversation first"}
            disabled={!id || sending}
          />
          <button className="button" type="submit" disabled={!id || sending}>
            {sending ? "Asking…" : "Ask"}
          </button>
        </form>
      </section>
    </div>
  );
}

function messageOf(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.message;
  }
  if (caught instanceof Error && caught.message) {
    return caught.message;
  }
  return "The conversation could not be loaded";
}
