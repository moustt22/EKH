import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def assistant_trace(model: str, hits: list[dict]) -> dict:
    source_ids: list[str] = []
    for hit in hits:
        document_id = str(hit.get("document_id", ""))
        if document_id and document_id not in source_ids:
            source_ids.append(document_id)
    return {"name": "ekh.assistant", "model": model, "source_document_ids": source_ids}


def emit_trace(trace: dict) -> None:
    settings = get_settings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return
    try:
        from langsmith import Client

        Client(api_key=settings.langsmith_api_key).create_run(
            name=trace["name"],
            run_type="chain",
            project_name=settings.langsmith_project,
            inputs={"model": trace["model"]},
            outputs={"source_document_ids": trace["source_document_ids"]},
            extra={"metadata": {"model": trace["model"], "source_document_ids": trace["source_document_ids"]}},
        )
    except Exception:
        logger.exception("LangSmith trace was not recorded")


def configure_tracing() -> None:
    import os

    settings = get_settings()
    os.environ["LANGSMITH_TRACING"] = "true" if settings.langsmith_tracing else "false"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
