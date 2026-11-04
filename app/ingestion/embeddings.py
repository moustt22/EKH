import hashlib
from typing import Protocol

import httpx

from app.core.config import get_settings

BATCH_SIZE = 64


class IngestionError(Exception):
    """A failure that will not succeed if the same file is processed again."""


class TransientIngestionError(Exception):
    """A failure Celery should retry."""


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([((digest[index % len(digest)] / 127.5) - 1.0) for index in range(self.dimensions)])
        return vectors


def get_embedder() -> Embedder:
    return OpenRouterEmbedder()


class OpenRouterEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise IngestionError("OPENROUTER_API_KEY is not configured")
        ordered: list[list[float] | None] = [None] * len(texts)
        with httpx.Client(timeout=60) as client:
            for start in range(0, len(texts), BATCH_SIZE):
                batch = texts[start : start + BATCH_SIZE]
                try:
                    response = client.post(
                        f"{settings.openrouter_base_url.rstrip('/')}/embeddings",
                        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                        json={"model": settings.openrouter_embed_model, "input": batch},
                    )
                except httpx.HTTPError as exc:
                    raise TransientIngestionError("The embedding service could not be reached") from exc
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise TransientIngestionError("The embedding service is unavailable")
                if response.status_code >= 400:
                    raise IngestionError("The embedding request was rejected")
                for item in response.json().get("data", []):
                    ordered[start + int(item["index"])] = item["embedding"]
        if any(vector is None for vector in ordered):
            raise TransientIngestionError("The embedding response was incomplete")
        vectors = [vector for vector in ordered if vector is not None]
        if len(vectors[0]) != settings.embed_dim:
            raise IngestionError("The embedding model returned an unexpected vector size")
        return vectors
