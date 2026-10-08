"""ORM models: one GenerationJob has many Certificate rows (one per recipient)."""
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class CertificateStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def utc_now() -> datetime:
    """Current UTC time. SQLite does not store time zones, so we store naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_job_id() -> str:
    return uuid.uuid4().hex


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_job_id)
    event_name: Mapped[str] = mapped_column(String(200))
    certificate_date: Mapped[date] = mapped_column(Date)
    total_recipients: Mapped[int] = mapped_column(Integer)
    successful_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Certificate.id"
    )


class Certificate(Base):
    """One recipient of a job and the result of generating their certificate."""

    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(
        String(20), default=CertificateStatus.PENDING.value, index=True
    )
    # Path RELATIVE to the certificates directory, e.g. "<job_id>/sona_mithya_certificate.pdf".
    # Storing a relative path means the project can be moved without breaking old rows.
    certificate_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    job: Mapped[GenerationJob] = relationship(back_populates="certificates")
