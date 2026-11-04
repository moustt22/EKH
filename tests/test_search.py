import uuid
from datetime import date, timedelta

import pymupdf
from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import User
from app.database.seed import DEMO_PASSWORD
from app.ingestion.embeddings import HashEmbedder
from app.ingestion.pipeline import process_ingestion_job
from app.services.documents import create_document
from app.services.vectors import IndexPoint, QdrantVectorIndex, SearchScope


def _login(client, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def _pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def _user(session, email: str) -> User:
    return session.scalar(
        select(User).where(User.email == email).options(selectinload(User.roles), selectinload(User.department))
    )


def test_search_requires_authentication(client):
    assert client.get("/search", params={"q": "salary"}).status_code == 401


def test_engineer_search_excludes_hr_chunks(client):
    session = client.app.state.session_factory()
    manager = _user(session, "hr.manager@northwind.example")
    hr_department_id = str(manager.department_id)
    document, job = create_document(
        session,
        client.app.state.memory_store,
        manager,
        title="Salary bands",
        department_id=manager.department_id,
        classification="confidential",
        access_scope="department",
        filename="salary.pdf",
        file_type="pdf",
        content_type="application/pdf",
        data=_pdf("Confidential salary bands for annual compensation."),
    )
    document_id = str(document.id)
    process_ingestion_job(
        session,
        job.id,
        client.app.state.memory_store,
        HashEmbedder(),
        client.app.state.memory_index,
        chunk_size=40,
        chunk_overlap=5,
    )
    session.close()

    engineer = _login(client, "eng.employee@northwind.example")
    hidden = client.get("/search", params={"q": "salary bands"}, headers={"Authorization": f"Bearer {engineer}"})
    assert hidden.status_code == 200
    assert hidden.json() == []
    bypass = client.get(
        "/search",
        params={"q": "salary bands", "department_id": hr_department_id},
        headers={"Authorization": f"Bearer {engineer}"},
    )
    assert bypass.status_code == 200
    assert bypass.json() == []

    hr = _login(client, "hr.manager@northwind.example")
    found = client.get("/search", params={"q": "salary bands"}, headers={"Authorization": f"Bearer {hr}"})
    assert found.status_code == 200
    hits = found.json()
    assert hits
    assert hits[0]["document_id"] == document_id
    assert hits[0]["title"] == "Salary bands"
    assert "salary" in hits[0]["snippet"].lower()
    assert hits[0]["page"] == 1
    assert hits[0]["version"] == 1

    future = (date.today() + timedelta(days=1)).isoformat()
    dated = client.get(
        "/search",
        params={"q": "salary bands", "date_from": future},
        headers={"Authorization": f"Bearer {hr}"},
    )
    assert dated.status_code == 200
    assert dated.json() == []


def test_qdrant_access_filter_drops_other_departments():
    index = QdrantVectorIndex()
    index.client = QdrantClient(":memory:")
    index.collection = "search_probe"
    index.dimensions = 4
    index._ready = False
    hr_department = str(uuid.uuid4())
    engineering = str(uuid.uuid4())
    engineer = str(uuid.uuid4())
    index.upsert(
        [
            IndexPoint(
                point_id=str(uuid.uuid4()),
                dense=[0.2, 0.1, 0.0, 0.4],
                sparse_indices=[3],
                sparse_values=[1.0],
                payload={
                    "document_id": str(uuid.uuid4()),
                    "department_id": hr_department,
                    "access_scope": "department",
                    "owner_id": str(uuid.uuid4()),
                    "allowed_user_ids": [],
                    "is_active": True,
                    "file_type": "pdf",
                    "classification": "confidential",
                    "version": 1,
                    "text": "salary",
                },
            ),
            IndexPoint(
                point_id=str(uuid.uuid4()),
                dense=[0.2, 0.1, 0.0, 0.4],
                sparse_indices=[3],
                sparse_values=[1.0],
                payload={
                    "document_id": str(uuid.uuid4()),
                    "department_id": engineering,
                    "access_scope": "department",
                    "owner_id": engineer,
                    "allowed_user_ids": [],
                    "is_active": True,
                    "file_type": "pdf",
                    "classification": "internal",
                    "version": 1,
                    "text": "deploy",
                },
            ),
        ]
    )
    hits = index.search(
        [0.2, 0.1, 0.0, 0.4],
        [3],
        [1.0],
        SearchScope(user_id=engineer, department_id=engineering, is_admin=False),
        limit=10,
    )
    assert hits
    assert {hit.payload["department_id"] for hit in hits} == {engineering}
