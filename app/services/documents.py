import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.documents import AccessScope, DocumentStatus, JobStatus
from app.core.roles import RoleName
from app.database.models import Chunk, Department, Document, DocumentGrant, DocumentVersion, IngestionJob, User
from app.ingestion.files import content_hash
from app.schemas.documents import DocumentOut
from app.services.access import can_manage, can_read, can_upload_to
from app.services.storage import ObjectStore
from app.services.vectors import VectorIndex


class DocumentServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def list_documents(db: Session, user: User) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.status != DocumentStatus.DELETED.value)
        .options(selectinload(Document.department))
        .order_by(Document.created_at.desc())
    )
    if user.role_name != RoleName.ADMINISTRATOR.value:
        grant_ids = select(DocumentGrant.document_id).where(DocumentGrant.user_id == user.id)
        statement = statement.where(
            or_(
                Document.owner_id == user.id,
                Document.id.in_(grant_ids),
                and_(
                    Document.access_scope == AccessScope.DEPARTMENT.value,
                    Document.department_id == user.department_id,
                ),
            )
        )
    return list(db.scalars(statement))


def get_readable_document(db: Session, user: User, document_id: uuid.UUID) -> Document:
    document = _load_document(db, document_id)
    if not can_read(user, document, _grant_ids(db, document.id)):
        raise DocumentServiceError(403, "Not allowed")
    return document


def create_document(
    db: Session,
    store: ObjectStore,
    user: User,
    *,
    title: str,
    department_id: uuid.UUID,
    classification: str,
    access_scope: str,
    filename: str,
    file_type: str,
    content_type: str,
    data: bytes,
) -> tuple[Document, IngestionJob]:
    if not title.strip():
        raise DocumentServiceError(400, "A title is required")
    if not can_upload_to(user, department_id):
        raise DocumentServiceError(403, "Not allowed")
    if db.get(Department, department_id) is None:
        raise DocumentServiceError(404, "Department not found")
    digest = content_hash(data)
    _reject_duplicate(db, digest)
    return _store_new_version(
        db,
        store,
        user,
        document=None,
        title=title.strip(),
        department_id=department_id,
        classification=classification,
        access_scope=access_scope,
        filename=filename,
        file_type=file_type,
        content_type=content_type,
        data=data,
        digest=digest,
    )


def add_version(
    db: Session,
    store: ObjectStore,
    user: User,
    document_id: uuid.UUID,
    *,
    filename: str,
    file_type: str,
    content_type: str,
    data: bytes,
) -> tuple[Document, IngestionJob]:
    document = _load_document(db, document_id)
    if not can_manage(user, document):
        raise DocumentServiceError(403, "Not allowed")
    if file_type != document.file_type:
        raise DocumentServiceError(400, "The new version must use the same file type")
    digest = content_hash(data)
    _reject_duplicate(db, digest)
    return _store_new_version(
        db,
        store,
        user,
        document=document,
        title=document.title,
        department_id=document.department_id,
        classification=document.classification,
        access_scope=document.access_scope,
        filename=filename,
        file_type=file_type,
        content_type=content_type,
        data=data,
        digest=digest,
    )


def download_document(db: Session, store: ObjectStore, user: User, document_id: uuid.UUID) -> tuple[Document, bytes]:
    document = get_readable_document(db, user, document_id)
    version = _current_version(db, document)
    return document, store.get_object(version.storage_key)


def delete_document(
    db: Session,
    store: ObjectStore,
    index: VectorIndex,
    user: User,
    document_id: uuid.UUID,
) -> None:
    document = _load_document(db, document_id)
    if not can_manage(user, document):
        raise DocumentServiceError(403, "Not allowed")
    versions = list(db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document.id)))
    index.delete_document(str(document.id))
    for version in versions:
        store.delete_object(version.storage_key)
    db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    document.status = DocumentStatus.DELETED.value
    document.updated_at = datetime.now(timezone.utc)
    db.commit()


def list_grants(db: Session, user: User, document_id: uuid.UUID) -> list[tuple[DocumentGrant, User]]:
    document = _load_document(db, document_id)
    if not can_manage(user, document):
        raise DocumentServiceError(403, "Not allowed")
    grants = list(db.scalars(select(DocumentGrant).where(DocumentGrant.document_id == document.id)))
    if not grants:
        return []
    people = {
        person.id: person
        for person in db.scalars(select(User).where(User.id.in_([grant.user_id for grant in grants])))
    }
    return [(grant, people[grant.user_id]) for grant in grants if grant.user_id in people]


def grant_read(
    db: Session,
    index: VectorIndex,
    actor: User,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    document = _load_document(db, document_id)
    if not can_manage(actor, document):
        raise DocumentServiceError(403, "Not allowed")
    target = db.get(User, user_id)
    if target is None or not target.is_active:
        raise DocumentServiceError(404, "User not found")
    existing = db.get(DocumentGrant, {"document_id": document.id, "user_id": target.id})
    if existing is not None:
        raise DocumentServiceError(409, "That user already has access")
    db.add(
        DocumentGrant(
            document_id=document.id,
            user_id=target.id,
            permission="read",
            created_by=actor.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    index.set_allowed_users(str(document.id), [str(item) for item in _grant_ids(db, document.id)])


def revoke_grant(
    db: Session,
    index: VectorIndex,
    actor: User,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    document = _load_document(db, document_id)
    if not can_manage(actor, document):
        raise DocumentServiceError(403, "Not allowed")
    grant = db.get(DocumentGrant, {"document_id": document.id, "user_id": user_id})
    if grant is None:
        raise DocumentServiceError(404, "Grant not found")
    db.delete(grant)
    db.commit()
    index.set_allowed_users(str(document.id), [str(item) for item in _grant_ids(db, document.id)])


def retry_ingestion(db: Session, user: User, document_id: uuid.UUID) -> IngestionJob:
    document = _load_document(db, document_id)
    if not can_manage(user, document):
        raise DocumentServiceError(403, "Not allowed")
    job = db.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.document_id == document.id,
            IngestionJob.version_number == document.current_version,
        )
        .order_by(IngestionJob.created_at.desc())
    )
    if job is None:
        raise DocumentServiceError(404, "Ingestion job not found")
    if job.status == JobStatus.INDEXED.value and document.status == DocumentStatus.ACTIVE.value:
        raise DocumentServiceError(409, "The document is already indexed")
    now = datetime.now(timezone.utc)
    job.status = JobStatus.QUEUED.value
    job.error = None
    job.updated_at = now
    document.status = DocumentStatus.PROCESSING.value
    document.updated_at = now
    db.commit()
    return job


def latest_job(db: Session, user: User, document_id: uuid.UUID) -> IngestionJob:
    document = get_readable_document(db, user, document_id)
    job = db.scalar(
        select(IngestionJob)
        .where(IngestionJob.document_id == document.id)
        .order_by(IngestionJob.created_at.desc())
    )
    if job is None:
        raise DocumentServiceError(404, "Ingestion job not found")
    return job


def serialize_document(document: Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        title=document.title,
        original_filename=document.original_filename,
        file_type=document.file_type,
        owner_id=document.owner_id,
        department_id=document.department_id,
        department_name=document.department.name,
        classification=document.classification,
        access_scope=document.access_scope,
        status=document.status,
        current_version=document.current_version,
        size_bytes=document.size_bytes,
        created_at=document.created_at,
    )


def _store_new_version(
    db: Session,
    store: ObjectStore,
    user: User,
    *,
    document: Document | None,
    title: str,
    department_id: uuid.UUID,
    classification: str,
    access_scope: str,
    filename: str,
    file_type: str,
    content_type: str,
    data: bytes,
    digest: str,
) -> tuple[Document, IngestionJob]:
    now = datetime.now(timezone.utc)
    version_number = 1 if document is None else document.current_version + 1
    document_id = uuid.uuid4() if document is None else document.id
    storage_key = f"documents/{document_id}/v{version_number}/{filename}"
    store.put_object(storage_key, data, content_type)
    try:
        if document is None:
            document = Document(
                id=document_id,
                title=title,
                original_filename=filename,
                file_type=file_type,
                owner_id=user.id,
                department_id=department_id,
                classification=classification,
                access_scope=access_scope,
                status=DocumentStatus.PROCESSING.value,
                current_version=1,
                content_hash=digest,
                size_bytes=len(data),
                created_at=now,
                updated_at=now,
            )
            db.add(document)
        else:
            document.original_filename = filename
            document.current_version = version_number
            document.content_hash = digest
            document.size_bytes = len(data)
            document.status = DocumentStatus.PROCESSING.value
            document.updated_at = now
        db.add(
            DocumentVersion(
                document_id=document_id,
                version_number=version_number,
                storage_key=storage_key,
                content_hash=digest,
                size_bytes=len(data),
                created_by=user.id,
                created_at=now,
            )
        )
        job = IngestionJob(
            document_id=document_id,
            version_number=version_number,
            status=JobStatus.QUEUED.value,
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        db.commit()
    except Exception:
        db.rollback()
        store.delete_object(storage_key)
        raise
    return _load_document(db, document_id), job


def _reject_duplicate(db: Session, digest: str) -> None:
    existing = db.scalar(
        select(Document.id).where(
            Document.content_hash == digest,
            Document.status != DocumentStatus.DELETED.value,
        )
    )
    if existing is not None:
        raise DocumentServiceError(409, "A document with the same content already exists")


def _load_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.department))
    )
    if document is None or document.status == DocumentStatus.DELETED.value:
        raise DocumentServiceError(404, "Document not found")
    return document


def _current_version(db: Session, document: Document) -> DocumentVersion:
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number == document.current_version,
        )
    )
    if version is None:
        raise DocumentServiceError(404, "Document file not found")
    return version


def _grant_ids(db: Session, document_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.scalars(select(DocumentGrant.user_id).where(DocumentGrant.document_id == document_id))
    return set(rows)
