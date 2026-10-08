"""Database engine, session factory and the FastAPI session dependency."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

# SQLite needs check_same_thread=False because FastAPI handles requests and
# background tasks in different threads. Each thread still gets its OWN session.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Parent class of all ORM models."""


def get_db() -> Iterator[Session]:
    """Give each request its own session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> sessionmaker:
    """The background task creates its own session, so it needs the factory.

    Exposed as a dependency so tests can swap in a test database.
    """
    return SessionLocal


def init_db() -> None:
    """Create all tables if they do not exist yet (called on app startup)."""
    from app.database import models  # noqa: F401  (importing registers the tables)

    Base.metadata.create_all(bind=engine)
