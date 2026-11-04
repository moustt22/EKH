import logging
import uuid

logger = logging.getLogger(__name__)


def enqueue_ingestion(job_id: uuid.UUID) -> None:
    from app.workers.tasks import ingest_document

    ingest_document.delay(str(job_id))


def enqueue_ingestion_quietly(job_id: uuid.UUID) -> None:
    try:
        enqueue_ingestion(job_id)
    except Exception:
        logger.exception("Could not enqueue ingestion job %s", job_id)
