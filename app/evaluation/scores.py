import re

from app.workflows.prompts import INSUFFICIENT_ANSWER


def score_case(case: dict, answer: str, citations: list[dict], prompt_text: str) -> dict[str, float]:
    visible = f"{answer}\n{json_citations(citations)}"
    forbidden_leaked = any(item.lower() in visible.lower() for item in case["forbidden"])
    hidden_leaked = any(item.lower() in prompt_text.lower() for item in case.get("hidden_from_prompt", []))
    if forbidden_leaked or hidden_leaked:
        return {"faithfulness": 0.0, "answer_relevance": 0.0, "citation_accuracy": 0.0}
    if case["expect_insufficient"]:
        grounded = answer == INSUFFICIENT_ANSWER and not citations
        value = 1.0 if grounded else 0.0
        return {"faithfulness": value, "answer_relevance": value, "citation_accuracy": value}
    contexts = " ".join(case["passages"])
    citation_ok = bool(citations) and all(_contained(item.get("passage", ""), contexts) for item in citations)
    faithful = 1.0 if citation_ok and _contained(answer, contexts) else 0.0
    return {
        "faithfulness": faithful,
        "answer_relevance": _token_f1(case["expected_answer"], answer),
        "citation_accuracy": 1.0 if citation_ok else 0.0,
    }


def json_citations(citations: list[dict]) -> str:
    return " ".join(str(item.get("passage", "")) for item in citations)


def _contained(needle: str, haystack: str) -> bool:
    return bool(needle.strip()) and _normalize(needle) in _normalize(haystack)


def _token_f1(expected: str, actual: str) -> float:
    expected_tokens = _tokens(expected)
    actual_tokens = _tokens(actual)
    if not expected_tokens or not actual_tokens:
        return 0.0
    overlap = sum(min(expected_tokens[token], actual_tokens[token]) for token in expected_tokens if token in actual_tokens)
    precision = overlap / sum(actual_tokens.values())
    recall = overlap / sum(expected_tokens.values())
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _tokens(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        counts[token] = counts.get(token, 0) + 1
    return counts


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
