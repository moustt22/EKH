import json
import re
from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import get_settings
from app.schemas.search import SearchHit
from app.services.chat import ChatClient
from app.workflows.prompts import ANSWER_SYSTEM, INSUFFICIENT_ANSWER, RELEVANCE_SYSTEM, REWRITE_SYSTEM
from app.workflows.tracing import assistant_trace, emit_trace

SearchFn = Callable[[str], list[SearchHit]]
_INSTRUCTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|disregard .{0,40}instructions|you are now|system prompt",
    re.IGNORECASE,
)


class AssistantState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]
    search_query: str
    hits: list[dict]
    attempts: int
    relevant: bool
    answer: str
    citations: list[dict]
    insufficient: bool


def run_assistant(question: str, history: list[dict[str, str]], search: SearchFn, chat: ChatClient) -> AssistantState:
    graph = _compile(search, chat)
    model = get_settings().openrouter_chat_model
    result = graph.invoke(
        {
            "question": question,
            "history": history[-6:],
            "search_query": question.strip(),
            "hits": [],
            "attempts": 0,
            "relevant": False,
            "answer": "",
            "citations": [],
            "insufficient": False,
        },
        config={"run_name": "ekh.assistant", "metadata": {"model": model}},
    )
    trace = assistant_trace(model, result.get("hits") or [])
    emit_trace(trace)
    result["trace"] = trace
    return result


def _compile(search: SearchFn, chat: ChatClient):
    builder = StateGraph(AssistantState)
    builder.add_node("understand", _understand)
    builder.add_node("rewrite", lambda state: _rewrite(state, chat))
    builder.add_node("retrieve", lambda state: _retrieve(state, search))
    builder.add_node("check_relevance", lambda state: _check_relevance(state, chat))
    builder.add_node("answer", lambda state: _answer(state, chat))
    builder.add_node("validate_citations", _validate_citations)
    builder.set_entry_point("understand")
    builder.add_conditional_edges(
        "understand",
        lambda state: "validate_citations" if not state.get("question") else "rewrite",
        {"rewrite": "rewrite", "validate_citations": "validate_citations"},
    )
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("retrieve", "check_relevance")
    builder.add_conditional_edges(
        "check_relevance",
        _route_after_relevance,
        {"answer": "answer", "retry": "rewrite", "insufficient": "validate_citations"},
    )
    builder.add_edge("answer", "validate_citations")
    builder.add_edge("validate_citations", END)
    return builder.compile()


def _understand(state: AssistantState) -> AssistantState:
    question = state.get("question", "").strip()
    return {"question": question, "search_query": question}


def _rewrite(state: AssistantState, chat: ChatClient) -> AssistantState:
    question = state["question"]
    history = state.get("history", [])
    if history and not _needs_history_rewrite(question):
        return {"search_query": question}
    raw = chat.complete(
        [
            {"role": "system", "content": REWRITE_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"history": history, "question": question},
                    ensure_ascii=True,
                ),
            },
        ]
    )
    query = _parse_json(raw).get("query")
    if not isinstance(query, str) or not query.strip():
        query = state["question"]
    return {"search_query": query.strip()}


def _needs_history_rewrite(question: str) -> bool:
    words = question.lower().split()
    if len(words) < 6:
        return True
    follow_up_markers = {
        "also",
        "it",
        "same",
        "that",
        "these",
        "they",
        "this",
        "those",
    }
    return bool(follow_up_markers.intersection(words)) or question.lower().startswith(("and ", "how about ", "what about "))


def _retrieve(state: AssistantState, search: SearchFn) -> AssistantState:
    hits = search(state.get("search_query") or state["question"])
    return {
        "hits": [hit.model_dump(mode="json") for hit in hits],
        "attempts": state.get("attempts", 0) + 1,
    }


def _check_relevance(state: AssistantState, chat: ChatClient) -> AssistantState:
    hits = state.get("hits") or []
    if not hits:
        return {"relevant": False}
    raw = chat.complete(
        [
            {"role": "system", "content": RELEVANCE_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": state["question"], "passages": [_passage(hit) for hit in hits]},
                    ensure_ascii=True,
                ),
            },
        ]
    )
    # A malformed classifier response must fail closed. Treating it as relevant
    # allows an ungrounded answer to reach the user.
    relevant = _parse_json(raw).get("relevant")
    if not isinstance(relevant, bool):
        relevant = False
    if not relevant and _has_evidence_overlap(state["question"], hits):
        relevant = True
    return {"relevant": relevant}


def _answer(state: AssistantState, chat: ChatClient) -> AssistantState:
    raw = chat.complete(
        [
            {"role": "system", "content": ANSWER_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": state["question"], "passages": [_passage(hit) for hit in state.get("hits", [])]},
                    ensure_ascii=True,
                ),
            },
        ]
    )
    parsed = _parse_json(raw)
    answer = parsed.get("answer")
    citations = parsed.get("citations")
    return {
        "answer": answer.strip() if isinstance(answer, str) else "",
        "citations": citations if isinstance(citations, list) else [],
    }


def _validate_citations(state: AssistantState) -> AssistantState:
    if not state.get("relevant"):
        return {"answer": INSUFFICIENT_ANSWER, "citations": [], "insufficient": True}
    answer = state.get("answer")
    if not isinstance(answer, str) or not answer.strip() or _is_instruction(answer):
        return {"answer": INSUFFICIENT_ANSWER, "citations": [], "insufficient": True}
    valid: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for citation in state.get("citations") or []:
        if not isinstance(citation, dict):
            continue
        passage = citation.get("passage")
        document_id = citation.get("document_id")
        page = citation.get("page")
        if not isinstance(passage, str) or not isinstance(document_id, str) or isinstance(page, bool):
            continue
        try:
            page_number = int(page)
        except (TypeError, ValueError):
            continue
        if _is_instruction(passage):
            continue
        for hit in state.get("hits") or []:
            key = (document_id, page_number, _normalize(passage))
            if key in seen:
                break
            if hit.get("document_id") != document_id or hit.get("page") != page_number:
                continue
            if _normalize(passage) not in _normalize(str(hit.get("snippet", ""))):
                continue
            seen.add(key)
            valid.append(
                {
                    "document_id": document_id,
                    "title": hit.get("title", ""),
                    "page": page_number,
                    "version": hit.get("version"),
                    "passage": " ".join(passage.split()),
                }
            )
            break
    if not valid:
        return {"answer": INSUFFICIENT_ANSWER, "citations": [], "insufficient": True}
    return {"answer": answer.strip(), "citations": valid, "insufficient": False}


def _route_after_relevance(state: AssistantState) -> str:
    if state.get("relevant"):
        return "answer"
    if state.get("attempts", 0) < 2:
        return "retry"
    return "insufficient"


def _passage(hit: dict) -> dict:
    return {
        "document_id": hit.get("document_id"),
        "title": hit.get("title"),
        "page": hit.get("page"),
        "version": hit.get("version"),
        "text": hit.get("snippet"),
    }


def _parse_json(raw: str | None) -> dict:
    if not isinstance(raw, str):
        return {}
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip().strip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _is_instruction(text: str) -> bool:
    return _INSTRUCTION.search(text) is not None


def _has_evidence_overlap(question: str, hits: list[dict]) -> bool:
    question_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", question.lower())
        if len(term) >= 4
    }
    if len(question_terms) < 2:
        return False
    passage_terms = {
        term
        for hit in hits
        for term in re.findall(r"[a-z0-9]+", str(hit.get("snippet", "")).lower())
    }
    return len(question_terms & passage_terms) >= 2
