import uuid

from pydantic import BaseModel


class SearchHit(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    snippet: str
    page: int
    section: str
    version: int
    file_type: str
    classification: str
    department_name: str
    score: float
