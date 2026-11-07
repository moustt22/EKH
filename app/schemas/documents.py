import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.documents import AccessScope, Classification


class DocumentCreateFields(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    department_id: uuid.UUID
    classification: Classification = Classification.INTERNAL
    access_scope: AccessScope = AccessScope.DEPARTMENT


class GrantCreate(BaseModel):
    user_id: uuid.UUID | None = None
    email: EmailStr | None = None

    @model_validator(mode="after")
    def require_user(self) -> "GrantCreate":
        if self.user_id is None and self.email is None:
            raise ValueError("A user id or email is required")
        return self


class GrantOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    permission: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    file_type: str
    owner_id: uuid.UUID
    department_id: uuid.UUID
    department_name: str
    department_ids: list[uuid.UUID] = Field(default_factory=list)
    department_names: list[str] = Field(default_factory=list)
    classification: str
    access_scope: str
    status: str
    current_version: int
    size_bytes: int
    created_at: datetime


class UploadAccepted(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    version: int


class JobOut(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    version: int
    error: str | None
