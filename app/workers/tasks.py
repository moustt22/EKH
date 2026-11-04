import uuid

from celery.exceptions import MaxRetriesExceededError

from app.database.session import SessionLocal
from app.ingestion.embeddings import OpenRouterEmbedder, TransientIngestionError
from app.ingestion.pipeline import process_ingestion_job
from app.services.storage import MinioObjectStore
from app.services.vectors import QdrantVectorIndex
from app.workers.celery_app import celery_app


@celery_app.task(name="ekh.ping")
def ping() -> str:
    return "pong"


@celery_app.task(bind=True, name="ekh.ingest_document", max_retries=3)
def ingest_document(self, job_id: str) -> None:
    db = SessionLocal()
    try:
        process_ingestion_job(
            db,
            uuid.UUID(job_id),
            MinioObjectStore(),
            OpenRouterEmbedder(),
            QdrantVectorIndex(),
        )
    except TransientIngestionError as exc:
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        except MaxRetriesExceededError:
            return
    finally:
        db.close()
