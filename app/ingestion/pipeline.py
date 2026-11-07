import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.documents import DocumentStatus, JobStatus
from app.database.models import Chunk, Document, DocumentVersion, IngestionJob
from app.ingestion.chunking import chunk_units, sparse_term_vector
from app.ingestion.embeddings import Embedder, IngestionError, TransientIngestionError
from app.ingestion.extract import extract_text
from app.services.storage import ObjectStore, StorageError
from app.services.vectors import IndexPoint, VectorIndex, VectorIndexError


def process_ingestion_job(
    db: Session,
    job_id: uuid.UUID,
    store: ObjectStore,
    embedder: Embedder,
    index: VectorIndex,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> None:
    settings = get_settings()
    size = settings.chunk_size_tokens if chunk_size is None else chunk_size
    overlap = settings.chunk_overlap_tokens if chunk_overlap is None else chunk_overlap
    job = db.get(IngestionJob, job_id)
    if job is None:
        return
    document = _load_document(db, job.document_id)
    if document is None or not _is_current(document, job):
        _mark_failed(db, job_id, "A newer version replaced this job", fail_document=False)
        return
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number == job.version_number,
        )
    )
    if version is None:
        _mark_failed(db, job_id, "The document file is missing")
        return
    try:
        _set_status(db, job, JobStatus.EXTRACTING.value)
        units = extract_text(document.file_type, store.get_object(version.storage_key))
        drafts = chunk_units(units, size, overlap)
        if not drafts:
            raise IngestionError("No text could be extracted")
        _set_status(db, job, JobStatus.EMBEDDING.value)
        vectors = embedder.embed([draft.content for draft in drafts])
        if len(vectors) != len(drafts):
            raise TransientIngestionError("The embedding response did not match the chunks")
        db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        points: list[IndexPoint] = []
        grants = [str(grant.user_id) for grant in document.grants]
        department_ids = [str(item.department_id) for item in document.departments] or [str(document.department_id)]
        for draft, vector in zip(drafts, vectors, strict=True):
            chunk_id = uuid.uuid5(document.id, f"{job.version_number}:{draft.chunk_index}")
            db.add(
                Chunk(
                    id=chunk_id,
                    document_id=document.id,
                    version_number=job.version_number,
                    chunk_index=draft.chunk_index,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    section=draft.section,
                    content=draft.content,
                )
            )
            sparse_indices, sparse_values = sparse_term_vector(draft.content)
            points.append(
                IndexPoint(
                    point_id=str(chunk_id),
                    dense=vector,
                    sparse_indices=sparse_indices,
                    sparse_values=sparse_values,
                    payload={
                        "document_id": str(document.id),
                        "chunk_id": str(chunk_id),
                        "version": job.version_number,
                        "title": document.title,
                        "page": draft.page_start,
                        "section": draft.section,
                        "text": draft.content,
                        "department_id": str(document.department_id),
                        "department_ids": department_ids,
                        "access_scope": document.access_scope,
                        "allowed_user_ids": grants,
                        "classification": document.classification,
                        "file_type": document.file_type,
                        "owner_id": str(document.owner_id),
                        "is_active": True,
                    },
                )
            )
        db.flush()
        fresh = db.get(Document, document.id)
        if fresh is None or not _is_current(fresh, job):
            db.rollback()
            _mark_failed(db, job_id, "A newer version replaced this job", fail_document=False)
            return
        index.deactivate_other_versions(str(document.id), job.version_number)
        index.upsert(points)
        fresh.status = DocumentStatus.ACTIVE.value
        fresh.updated_at = datetime.now(timezone.utc)
        job.status = JobStatus.INDEXED.value
        job.error = None
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    except IngestionError as exc:
        db.rollback()
        _mark_failed(db, job_id, str(exc))
    except (TransientIngestionError, StorageError, VectorIndexError):
        db.rollback()
        _mark_failed(db, job_id, "Indexing failed and will be retried")
        raise TransientIngestionError("Indexing failed and will be retried")
    except Exception as exc:
        db.rollback()
        _mark_failed(db, job_id, "Indexing failed and will be retried")
        raise TransientIngestionError("Indexing failed and will be retried") from exc


def _load_document(db: Session, document_id: uuid.UUID) -> Document | None:
    return db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.grants), selectinload(Document.department))
    )


def _is_current(document: Document, job: IngestionJob) -> bool:
    return document.status != DocumentStatus.DELETED.value and document.current_version == job.version_number


def _set_status(db: Session, job: IngestionJob, status: str) -> None:
    job.status = status
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _mark_failed(db: Session, job_id: uuid.UUID, message: str, fail_document: bool = True) -> None:
    job = db.get(IngestionJob, job_id)
    if job is None:
        return
    job.status = JobStatus.FAILED.value
    job.error = message[:500]
    job.updated_at = datetime.now(timezone.utc)
    document = db.get(Document, job.document_id)
    if (
        fail_document
        and document is not None
        and document.current_version == job.version_number
        and document.status != DocumentStatus.DELETED.value
    ):
        document.status = DocumentStatus.FAILED.value
        document.updated_at = datetime.now(timezone.utc)
    db.commit()
