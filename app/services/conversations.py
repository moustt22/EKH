import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Conversation, Message, User
from app.ingestion.embeddings import Embedder
from app.retrieval.search import search_documents
from app.schemas.conversations import CitationOut, ConversationDetail, ConversationOut, MessageOut
from app.services.chat import ChatClient
from app.services.vectors import VectorIndex
from app.workflows.assistant import run_assistant


class ConversationServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def create_conversation(db: Session, user: User, title: str | None) -> Conversation:
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        user_id=user.id,
        title=(title or "New conversation").strip()[:200] or "New conversation",
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user: User) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
        )
    )


def get_conversation(db: Session, user: User, conversation_id: uuid.UUID) -> Conversation:
    conversation = _owned(db, user, conversation_id)
    return conversation


def delete_conversation(db: Session, user: User, conversation_id: uuid.UUID) -> None:
    conversation = _owned(db, user, conversation_id)
    db.delete(conversation)
    db.commit()


def ask(
    db: Session,
    user: User,
    conversation_id: uuid.UUID,
    content: str,
    embedder: Embedder,
    index: VectorIndex,
    chat: ChatClient,
) -> Message:
    conversation = _owned(db, user, conversation_id)
    history = [
        {"role": message.role, "content": message.content}
        for message in _messages(db, conversation.id)[-6:]
    ]
    now = datetime.now(timezone.utc)
    db.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content=content.strip(),
            created_at=now,
        )
    )
    if conversation.title == "New conversation":
        conversation.title = content.strip()[:80]
    result = run_assistant(
        content,
        history,
        lambda query: search_documents(db, user, query, embedder, index),
        chat,
    )
    assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("answer") or "",
        citations=json.dumps(result.get("citations") or []),
        created_at=datetime.now(timezone.utc),
    )
    conversation.updated_at = assistant.created_at
    db.add(assistant)
    db.commit()
    db.refresh(assistant)
    return assistant


def serialize_conversation(conversation: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def serialize_detail(db: Session, conversation: Conversation) -> ConversationDetail:
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[serialize_message(message) for message in _messages(db, conversation.id)],
    )


def serialize_message(message: Message) -> MessageOut:
    raw = json.loads(message.citations) if message.citations else []
    citations = [CitationOut.model_validate(item) for item in raw]
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        citations=citations,
        created_at=message.created_at,
    )


def _owned(db: Session, user: User, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conversation is None:
        raise ConversationServiceError(404, "Conversation not found")
    return conversation


def _messages(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    return list(
        db.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
        )
    )
