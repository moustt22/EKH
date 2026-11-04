import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.seed import seed_database
from app.database.session import get_db
from app.ingestion.embeddings import HashEmbedder, get_embedder
from app.main import app
from app.services.storage import MemoryObjectStore, get_object_store
from app.services.vectors import MemoryVectorIndex, get_vector_index


@pytest.fixture(autouse=True)
def _skip_celery(monkeypatch):
    monkeypatch.setattr("app.api.documents.enqueue_ingestion_quietly", lambda job_id: None)


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as session:
        seed_database(session)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    store = MemoryObjectStore()
    index = MemoryVectorIndex()
    app.state.session_factory = session_factory
    app.state.memory_index = index
    app.state.memory_store = store
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_object_store] = lambda: store
    app.dependency_overrides[get_vector_index] = lambda: index
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
