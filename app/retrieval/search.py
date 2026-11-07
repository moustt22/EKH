import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.documents import DocumentStatus
from app.core.roles import RoleName
from app.database.models import Chunk, Document, DocumentDepartment, User
from app.ingestion.chunking import sparse_term_vector
from app.ingestion.embeddings import Embedder
from app.schemas.search import SearchHit
from app.services.access import can_read
from app.services.vectors import SearchScope, VectorIndex

RESULT_LIMIT = 12
CANDIDATE_LIMIT = 24


def search_documents(
    db: Session,
    user: User,
    query: str,
    embedder: Embedder,
    index: VectorIndex,
    *,
    department_id: uuid.UUID | None = None,
    file_type: str | None = None,
    classification: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[SearchHit]:
    dense = embedder.embed([query])[0]
    sparse_indices, sparse_values = sparse_term_vector(query)
    scope = SearchScope(
        user_id=str(user.id),
        department_id=str(user.department_id),
        is_admin=user.role_name == RoleName.ADMINISTRATOR.value,
        file_type=file_type,
        classification=classification,
        department_filter=str(department_id) if department_id else None,
    )
    hits = index.search(dense, sparse_indices, sparse_values, scope, limit=CANDIDATE_LIMIT)
    results: list[SearchHit] = []
    for hit in hits:
        try:
            chunk_id = uuid.UUID(hit.point_id)
        except ValueError:
            continue
        chunk = db.get(Chunk, chunk_id)
        if chunk is None:
            continue
        document = db.scalar(
            select(Document)
            .where(Document.id == chunk.document_id)
            .options(selectinload(Document.department), selectinload(Document.grants))
            .options(selectinload(Document.departments).selectinload(DocumentDepartment.department))
        )
        if document is None or document.status != DocumentStatus.ACTIVE.value:
            continue
        if chunk.version_number != document.current_version:
            continue
        if not can_read(
            user,
            document,
            {grant.user_id for grant in document.grants},
            {item.department_id for item in document.departments},
        ):
            continue
        if department_id is not None and document.department_id != department_id:
            continue
        if file_type is not None and document.file_type != file_type:
            continue
        if classification is not None and document.classification != classification:
            continue
        if not _created_in_range(document.created_at, date_from, date_to):
            continue
        results.append(
            SearchHit(
                document_id=document.id,
                chunk_id=chunk.id,
                title=document.title,
                snippet=_snippet(chunk.content),
                page=chunk.page_start,
                section=chunk.section,
                version=document.current_version,
                file_type=document.file_type,
                classification=document.classification,
                department_name=document.department.name,
                score=round(hit.score, 4),
            )
        )
        if len(results) == RESULT_LIMIT:
            break
    return results


def _created_in_range(created_at: datetime, date_from: date | None, date_to: date | None) -> bool:
    created = created_at.date()
    if date_from is not None and created < date_from:
        return False
    if date_to is not None and created > date_to:
        return False
    return True


def _snippet(content: str) -> str:
    compact = " ".join(content.split())
    # Keep enough source text for the assistant to cite facts that appear
    # after a document's heading and metadata.
    if len(compact) <= 2000:
        return compact
    return compact[:1997] + "..."
