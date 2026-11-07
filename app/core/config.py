from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Knowledge Hub"
    environment: str = "local"

    database_url: str = "postgresql+psycopg://ekh:ekh@localhost:5432/ekh"
    redis_url: str = "redis://localhost:6379/0"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "ekh_chunks"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "ekh"
    minio_secret_key: str = "ekhsecret"
    minio_bucket: str = "ekh-documents"
    minio_secure: bool = False
    minio_region: str = ""

    jwt_secret: str = "change-me-before-any-shared-deployment"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "google/gemini-2.5-flash-lite"
    openrouter_chat_fallback_model: str = ""
    openrouter_timeout_seconds: float = 60.0
    openrouter_max_retries: int = 2
    openrouter_embed_model: str = "openai/text-embedding-3-small"
    embed_dim: int = 1536
    chunk_size_tokens: int = 800
    chunk_overlap_tokens: int = 120

    langsmith_api_key: str = ""
    langsmith_tracing: bool = False
    langsmith_project: str = "ekh"

    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    rate_limit_enabled: bool = False
    rate_limit_window_seconds: int = 60
    login_rate_limit: int = 10
    api_rate_limit: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_runtime(self) -> None:
        if self.environment == "local":
            return
        if len(self.jwt_secret.encode("utf-8")) < 32 or self.jwt_secret.startswith("change-me"):
            raise RuntimeError("JWT_SECRET must be a random value of at least 32 bytes outside local mode")
        if not self.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required outside local mode")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origin_list):
            raise RuntimeError("CORS_ORIGINS must not contain localhost outside local mode")
        if not self.minio_secure:
            raise RuntimeError("MINIO_SECURE must be true outside local mode")


@lru_cache
def get_settings() -> Settings:
    return Settings()
