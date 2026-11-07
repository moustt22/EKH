import time
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
        models = [settings.openrouter_chat_model]
        if settings.openrouter_chat_fallback_model and settings.openrouter_chat_fallback_model not in models:
            models.append(settings.openrouter_chat_fallback_model)
        last_error: ChatError | None = None
        for model in models:
            for attempt in range(settings.openrouter_max_retries + 1):
                try:
                    response = httpx.post(
                        f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": 0,
                            "max_tokens": 800,
                            "response_format": {"type": "json_object"},
                        },
                        timeout=settings.openrouter_timeout_seconds,
                    )
                except httpx.HTTPError as exc:
                    last_error = ChatError("The chat model could not be reached")
                    if attempt < settings.openrouter_max_retries:
                        time.sleep(2**attempt)
                        continue
                    break
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = ChatError("The chat model is unavailable")
                    if attempt < settings.openrouter_max_retries:
                        time.sleep(2**attempt)
                        continue
                    break
                if response.status_code >= 400:
                    last_error = ChatError("The chat request was rejected")
                    break
                try:
                    message = response.json()["choices"][0]["message"]
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise ChatError("The chat response was incomplete") from exc
                text = _message_text(message.get("content")) or _message_text(message.get("reasoning"))
                if not text:
                    raise ChatError("The chat model returned an empty response")
                return text
        raise last_error or ChatError("The chat model is unavailable")


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
