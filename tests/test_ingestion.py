import io
import uuid

import pymupdf
from docx import Document as DocxDocument
from sqlalchemy import create_engine, select
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.documents import DocumentStatus, JobStatus
from app.database.base import Base
from app.database.models import Chunk, Document, IngestionJob, User
from app.database.seed import seed_database
from app.ingestion.chunking import chunk_units
from app.ingestion.embeddings import HashEmbedder
from app.ingestion.extract import TextUnit
from app.ingestion.pipeline import process_ingestion_job
from app.services.documents import create_document, delete_document, retry_ingestion
from app.services.storage import MemoryObjectStore
from app.services.vectors import MemoryVectorIndex


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    seed_database(session)
    return session


def _manager(session):
    return session.scalar(
        select(User)
        .where(User.email == "hr.manager@northwind.example")
        .options(selectinload(User.roles), selectinload(User.department))
    )


def _pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    if text:
        page.insert_text((72, 72), text, fontsize=16)
        page.insert_text((72, 110), "Engineers are paid from the published annual band.", fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def _docx() -> bytes:
    document = DocxDocument()
    document.add_heading("Leave policy", level=1)
    document.add_paragraph("Employees accrue leave each month and request it in writing.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_chunks_overlap_and_keep_page_order():
    units = [TextUnit(text="one two three four five six", page=2, section="Pay")]
    drafts = chunk_units(units, size=4, overlap=1)
    assert [draft.content for draft in drafts] == ["one two three four", "four five six"]
    assert drafts[0].page_start == 2
    assert drafts[0].section == "Pay"


def test_pdf_and_docx_become_active_and_delete_removes_points():
    session = _session()
    manager = _manager(session)
    store = MemoryObjectStore()
    index = MemoryVectorIndex()
    pdf, pdf_job = create_document(
        session,
        store,
        manager,
        title="Salary bands",
        department_id=manager.department_id,
        classification="confidential",
        access_scope="department",
        filename="salary.pdf",
        file_type="pdf",
        content_type="application/pdf",
        data=_pdf("Salary bands"),
    )
    process_ingestion_job(session, pdf_job.id, store, HashEmbedder(), index, chunk_size=12, chunk_overlap=2)
    stored_pdf = session.get(Document, pdf.id)
    assert stored_pdf.status == DocumentStatus.ACTIVE.value
    assert session.get(IngestionJob, pdf_job.id).status == JobStatus.INDEXED.value
    pdf_points = [point for point in index.points.values() if point.payload["document_id"] == str(pdf.id)]
    assert pdf_points
    assert pdf_points[0].payload["department_id"] == str(manager.department_id)
    assert pdf_points[0].payload["is_active"] is True
    assert session.scalars(select(Chunk).where(Chunk.document_id == pdf.id)).all()

    docx, docx_job = create_document(
        session,
        store,
        manager,
        title="Leave policy",
        department_id=manager.department_id,
        classification="internal",
        access_scope="restricted",
        filename="leave.docx",
        file_type="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=_docx(),
    )
    process_ingestion_job(session, docx_job.id, store, HashEmbedder(), index, chunk_size=20, chunk_overlap=4)
    docx_chunks = list(session.scalars(select(Chunk).where(Chunk.document_id == docx.id)))
    assert session.get(Document, docx.id).status == DocumentStatus.ACTIVE.value
    assert any(chunk.section == "Leave policy" for chunk in docx_chunks)

    delete_document(session, store, index, manager, pdf.id)
    assert session.get(Document, pdf.id).status == DocumentStatus.DELETED.value
    assert not any(point.payload["document_id"] == str(pdf.id) for point in index.points.values())
    session.close()


def test_failed_extraction_can_be_retried_and_new_version_retires_old_points():
    session = _session()
    manager = _manager(session)
    store = MemoryObjectStore()
    index = MemoryVectorIndex()
    blank, blank_job = create_document(
        session,
        store,
        manager,
        title="Blank",
        department_id=manager.department_id,
        classification="internal",
        access_scope="department",
        filename="blank.pdf",
        file_type="pdf",
        content_type="application/pdf",
        data=_pdf(""),
    )
    process_ingestion_job(session, blank_job.id, store, HashEmbedder(), index, chunk_size=20, chunk_overlap=4)
    failed = session.get(Document, blank.id)
    failed_job = session.get(IngestionJob, blank_job.id)
    assert failed.status == DocumentStatus.FAILED.value
    assert failed_job.status == JobStatus.FAILED.value
    assert failed_job.error == "No text could be extracted"
    retried = retry_ingestion(session, manager, blank.id)
    assert retried.status == JobStatus.QUEUED.value
    assert session.get(Document, blank.id).status == DocumentStatus.PROCESSING.value

    original, original_job = create_document(
        session,
        store,
        manager,
        title="Bands",
        department_id=manager.department_id,
        classification="internal",
        access_scope="department",
        filename="bands.pdf",
        file_type="pdf",
        content_type="application/pdf",
        data=_pdf("Salary bands"),
    )
    process_ingestion_job(session, original_job.id, store, HashEmbedder(), index, chunk_size=30, chunk_overlap=0)
    from app.services.documents import add_version

    updated, updated_job = add_version(
        session,
        store,
        manager,
        original.id,
        filename="bands-v2.pdf",
        file_type="pdf",
        content_type="application/pdf",
        data=_pdf("Revised salary bands for the new year"),
    )
    process_ingestion_job(session, updated_job.id, store, HashEmbedder(), index, chunk_size=30, chunk_overlap=0)
    points = [point for point in index.points.values() if point.payload["document_id"] == str(original.id)]
    assert updated.current_version == 2
    assert any(point.payload["version"] == 1 and point.payload["is_active"] is False for point in points)
    assert any(point.payload["version"] == 2 and point.payload["is_active"] is True for point in points)
    assert uuid.UUID(points[0].point_id)
    session.close()
