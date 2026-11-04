from typing import Protocol

import httpx

from app.core.config import get_settings


class ChatError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ChatClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class OpenRouterChat:
    def complete(self, messages: list[dict[str, str]]) -> str:
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise ChatError("OPENROUTER_API_KEY is not configured")
        try:
            response = httpx.post(
                f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": settings.openrouter_chat_model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 800,
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )
        except httpx.HTTPError as exc:
            raise ChatError("The chat model could not be reached") from exc
        if response.status_code in {429, 500, 502, 503, 504}:
            raise ChatError("The chat model is unavailable")
        if response.status_code >= 400:
            raise ChatError("The chat request was rejected")
        try:
            message = response.json()["choices"][0]["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ChatError("The chat response was incomplete") from exc
        text = _message_text(message.get("content")) or _message_text(message.get("reasoning"))
        if not text:
            raise ChatError("The chat model returned an empty response")
        return text


def get_chat_client() -> ChatClient:
    return OpenRouterChat()


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(part.strip() for part in parts if part.strip())
    return ""
