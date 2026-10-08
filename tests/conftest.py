"""Shared fixtures.

Every test gets:
  * its own temporary SQLite database file
  * its own temporary certificates folder
so tests never touch real data and never affect each other.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_certificates_dir
from app.database.database import Base, get_db, get_session_factory
from app.database import models  # noqa: F401  (registers the tables)
from app.main import app


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture
def certificates_dir(tmp_path):
    folder = tmp_path / "certificates"
    folder.mkdir()
    return folder


@pytest.fixture
def client(session_factory, certificates_dir):
    """TestClient wired to the temporary database and folder.

    TestClient runs FastAPI background tasks before returning the response,
    so after a POST the job is already finished and tests stay deterministic.
    """

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_certificates_dir] = lambda: certificates_dir
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


def make_payload(recipient_count: int = 2, event_name: str = "Python Workshop") -> dict:
    return {
        "event_name": event_name,
        "certificate_date": "2026-10-08",
        "recipients": [
            {"name": f"Person {number}", "email": f"person{number}@example.com"}
            for number in range(1, recipient_count + 1)
        ],
    }


@pytest.fixture
def valid_payload() -> dict:
    return {
        "event_name": "Python Workshop",
        "certificate_date": "2026-10-08",
        "recipients": [
            {"name": "Sona Mithya", "email": "sona@example.com"},
            {"name": "Priya", "email": "priya@example.com"},
        ],
    }
