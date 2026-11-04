import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import User
from app.database.session import get_db
from app.ingestion.embeddings import Embedder, IngestionError, TransientIngestionError, get_embedder
from app.schemas.conversations import ConversationCreate, ConversationDetail, ConversationOut, MessageCreate, MessageOut
from app.services.audit import record_audit
from app.services.chat import ChatClient, ChatError, get_chat_client
from app.services.conversations import (
    ConversationServiceError,
    ask,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    serialize_conversation,
    serialize_detail,
    serialize_message,
)
from app.services.vectors import VectorIndex, VectorIndexError, get_vector_index

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
def get_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    return [serialize_conversation(conversation) for conversation in list_conversations(db, user)]


@router.post("", response_model=ConversationOut, status_code=201)
def post_conversation(
    payload: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    return serialize_conversation(create_conversation(db, user, payload.title))


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_one(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    try:
        conversation = get_conversation(db, user, conversation_id)
    except ConversationServiceError as exc:
        _audit_conversation_denial(db, user, conversation_id)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return serialize_detail(db, conversation)


@router.delete("/{conversation_id}", status_code=204)
def remove_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_conversation(db, user, conversation_id)
    except ConversationServiceError as exc:
        _audit_conversation_denial(db, user, conversation_id)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{conversation_id}/messages", response_model=MessageOut)
def post_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    index: VectorIndex = Depends(get_vector_index),
    chat: ChatClient = Depends(get_chat_client),
) -> MessageOut:
    try:
        message = ask(db, user, conversation_id, payload.content, embedder, index, chat)
    except ConversationServiceError as exc:
        _audit_conversation_denial(db, user, conversation_id)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except VectorIndexError as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
    except (IngestionError, TransientIngestionError, ChatError) as exc:
        db.rollback()
        detail = getattr(exc, "detail", None) or str(exc)
        raise HTTPException(status_code=503, detail=detail) from exc
    citations = serialize_message(message).citations
    record_audit(
        db,
        action="assistant_response",
        outcome="allowed",
        actor=user,
        resource_type="conversation",
        resource_id=conversation_id,
        metadata={
            "message_id": str(message.id),
            "source_document_ids": [str(item.document_id) for item in citations],
            "citation_count": len(citations),
        },
    )
    return serialize_message(message)


def _audit_conversation_denial(db: Session, user: User, conversation_id: uuid.UUID) -> None:
    db.rollback()
    record_audit(
        db,
        action="conversation_access",
        outcome="denied",
        actor=user,
        resource_type="conversation",
        resource_id=conversation_id,
    )
