import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class CitationOut(BaseModel):
    document_id: uuid.UUID
    title: str
    page: int
    version: int
    passage: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[CitationOut]
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
