import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.documents import Classification
from app.database.models import User
from app.database.session import get_db
from app.ingestion.embeddings import Embedder, IngestionError, TransientIngestionError, get_embedder
from app.retrieval.search import search_documents
from app.schemas.search import SearchHit
from app.services.audit import record_audit
from app.services.vectors import VectorIndex, VectorIndexError, get_vector_index

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchHit])
def search(
    q: str = Query(min_length=1, max_length=500),
    department_id: uuid.UUID | None = None,
    file_type: str | None = Query(default=None, pattern="^(pdf|docx)$"),
    classification: Classification | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    index: VectorIndex = Depends(get_vector_index),
) -> list[SearchHit]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from is after date_to")
    try:
        hits = search_documents(
            db,
            user,
            q,
            embedder,
            index,
            department_id=department_id,
            file_type=file_type,
            classification=classification.value if classification else None,
            date_from=date_from,
            date_to=date_to,
        )
    except VectorIndexError as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
    except (IngestionError, TransientIngestionError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    record_audit(
        db,
        action="search",
        outcome="allowed",
        actor=user,
        resource_type="search",
        metadata={
            "query": q,
            "result_count": len(hits),
            "document_ids": [str(hit.document_id) for hit in hits],
        },
    )
    return hits
