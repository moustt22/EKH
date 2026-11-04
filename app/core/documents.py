from enum import Enum

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class AccessScope(str, Enum):
    DEPARTMENT = "department"
    RESTRICTED = "restricted"


class Classification(str, Enum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    ACTIVE = "active"
    FAILED = "failed"
    DELETED = "deleted"


class JobStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"
