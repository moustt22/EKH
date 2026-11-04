import uuid
from typing import NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.documents import AccessScope, Classification
from app.database.models import User
from app.database.session import get_db
from app.ingestion.files import FileValidationError, read_limited, validate_upload
from app.schemas.documents import DocumentOut, GrantCreate, GrantOut, JobOut, UploadAccepted
from app.services.audit import record_audit
from app.services.documents import (
    DocumentServiceError,
    add_version,
    create_document,
    delete_document,
    download_document,
    get_readable_document,
    grant_read,
    latest_job,
    list_documents,
    list_grants,
    retry_ingestion,
    revoke_grant,
    serialize_document,
)
from app.services.storage import ObjectStore, StorageError, get_object_store
from app.services.vectors import VectorIndex, VectorIndexError, get_vector_index
from app.workers.queue import enqueue_ingestion_quietly

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def get_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    return [serialize_document(document) for document in list_documents(db, user)]


@router.post("", response_model=UploadAccepted, status_code=202)
async def post_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    department_id: uuid.UUID = Form(...),
    classification: Classification = Form(Classification.INTERNAL),
    access_scope: AccessScope = Form(AccessScope.DEPARTMENT),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
) -> UploadAccepted:
    data, file_type, content_type, filename = await _read_upload(file)
    try:
        document, job = create_document(
            db,
            store,
            user,
            title=title,
            department_id=department_id,
            classification=classification.value,
            access_scope=access_scope.value,
            filename=filename,
            file_type=file_type,
            content_type=content_type,
            data=data,
        )
    except DocumentServiceError as exc:
        _audit_denial(db, user, "upload", document_id=None, exc=exc)
    except StorageError as exc:
        _raise_service_error(exc)
    enqueue_ingestion_quietly(job.id)
    record_audit(
        db,
        action="upload",
        outcome="allowed",
        actor=user,
        resource_type="document",
        resource_id=document.id,
        metadata={
            "title": title,
            "file_type": file_type,
            "classification": classification.value,
            "access_scope": access_scope.value,
            "version": document.current_version,
        },
    )
    return UploadAccepted(
        document_id=document.id,
        job_id=job.id,
        status=document.status,
        version=document.current_version,
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    try:
        document = get_readable_document(db, user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return serialize_document(document)


@router.get("/{document_id}/download")
def get_document_file(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
) -> Response:
    try:
        document, data = download_document(db, store, user, document_id)
    except DocumentServiceError as exc:
        _audit_denial(db, user, "download", document_id=document_id, exc=exc)
    except StorageError as exc:
        _raise_service_error(exc)
    record_audit(
        db,
        action="download",
        outcome="allowed",
        actor=user,
        resource_type="document",
        resource_id=document.id,
        metadata={"version": document.current_version, "file_type": document.file_type},
    )
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{document.original_filename}"'},
    )


@router.post("/{document_id}/versions", response_model=UploadAccepted, status_code=202)
async def post_version(
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
) -> UploadAccepted:
    data, file_type, content_type, filename = await _read_upload(file)
    try:
        document, job = add_version(
            db,
            store,
            user,
            document_id,
            filename=filename,
            file_type=file_type,
            content_type=content_type,
            data=data,
        )
    except DocumentServiceError as exc:
        _audit_denial(db, user, "update", document_id=document_id, exc=exc)
    except StorageError as exc:
        _raise_service_error(exc)
    enqueue_ingestion_quietly(job.id)
    record_audit(
        db,
        action="update",
        outcome="allowed",
        actor=user,
        resource_type="document",
        resource_id=document.id,
        metadata={"version": document.current_version, "file_type": file_type},
    )
    return UploadAccepted(
        document_id=document.id,
        job_id=job.id,
        status=document.status,
        version=document.current_version,
    )


@router.get("/{document_id}/jobs/latest", response_model=JobOut)
def get_latest_job(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    try:
        job = latest_job(db, user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return JobOut(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status,
        version=job.version_number,
        error=job.error,
    )


@router.post("/{document_id}/retry", response_model=JobOut)
def post_retry(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    try:
        job = retry_ingestion(db, user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    enqueue_ingestion_quietly(job.id)
    return JobOut(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status,
        version=job.version_number,
        error=job.error,
    )


@router.get("/{document_id}/permissions", response_model=list[GrantOut])
def get_permissions(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GrantOut]:
    try:
        grants = list_grants(db, user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return [
        GrantOut(user_id=person.id, name=person.name, email=person.email, permission=grant.permission)
        for grant, person in grants
    ]


@router.post("/{document_id}/permissions", status_code=204)
def post_permission(
    document_id: uuid.UUID,
    payload: GrantCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    index: VectorIndex = Depends(get_vector_index),
) -> None:
    target_id = _grant_target(db, payload)
    try:
        grant_read(db, index, user, document_id, target_id)
    except DocumentServiceError as exc:
        _audit_denial(
            db,
            user,
            "permission_change",
            document_id=document_id,
            exc=exc,
            metadata={"operation": "grant", "target_user_id": str(target_id)},
        )
    except VectorIndexError as exc:
        _raise_service_error(exc)
    record_audit(
        db,
        action="permission_change",
        outcome="allowed",
        actor=user,
        resource_type="document",
        resource_id=document_id,
        metadata={"operation": "grant", "target_user_id": str(target_id)},
    )


@router.delete("/{document_id}/permissions/{user_id}", status_code=204)
def delete_permission(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    index: VectorIndex = Depends(get_vector_index),
) -> None:
    try:
        revoke_grant(db, index, user, document_id, user_id)
    except DocumentServiceError as exc:
        _audit_denial(
            db,
            user,
            "permission_change",
            document_id=document_id,
            exc=exc,
            metadata={"operation": "revoke", "target_user_id": str(user_id)},
        )
    except VectorIndexError as exc:
        _raise_service_error(exc)
    record_audit(
        db,
        action="permission_change",
        outcome="allowed",
        actor=user,
        resource_type="document",
        resource_id=document_id,
        metadata={"operation": "revoke", "target_user_id": str(user_id)},
    )


@router.delete("/{document_id}", status_code=204)
def remove_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
    index: VectorIndex = Depends(get_vector_index),
) -> None:
    try:
        delete_document(db, store, index, user, document_id)
    except DocumentServiceError as exc:
        _audit_denial(db, user, "deletion", document_id=document_id, exc=exc)
    except (StorageError, VectorIndexError) as exc:
        _raise_service_error(exc)
    record_audit(
        db,
        action="deletion",
        outcome="allowed",
        actor=user,
        resource_type="document",
        resource_id=document_id,
    )


async def _read_upload(file: UploadFile) -> tuple[bytes, str, str, str]:
    try:
        data = await read_limited(file)
        file_type, content_type, filename = validate_upload(file.filename, data)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return data, file_type, content_type, filename


def _grant_target(db: Session, payload: GrantCreate) -> uuid.UUID:
    if payload.user_id is not None:
        return payload.user_id
    found = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if found is None:
        raise HTTPException(status_code=404, detail="User not found")
    return found.id


def _audit_denial(
    db: Session,
    user: User,
    action: str,
    document_id: uuid.UUID | None,
    exc: DocumentServiceError,
    metadata: dict | None = None,
) -> NoReturn:
    db.rollback()
    record_audit(
        db,
        action=action,
        outcome="denied",
        actor=user,
        resource_type="document",
        resource_id=document_id,
        metadata={"status": exc.status_code, **(metadata or {})},
    )
    _raise_service_error(exc)


def _raise_service_error(exc: DocumentServiceError | StorageError | VectorIndexError) -> NoReturn:
    if isinstance(exc, DocumentServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise HTTPException(status_code=503, detail=exc.detail) from exc
