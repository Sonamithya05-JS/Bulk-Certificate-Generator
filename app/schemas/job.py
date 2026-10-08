"""Pydantic models: validate incoming requests and shape outgoing responses."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.config import MAX_RECIPIENTS_PER_JOB
from app.utils.validators import clean_text

MAX_NAME_LENGTH = 80
MAX_EVENT_NAME_LENGTH = 150


class RecipientIn(BaseModel):
    name: str
    email: EmailStr

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = clean_text(value)
        if not value:
            raise ValueError("name must not be empty")
        if len(value) > MAX_NAME_LENGTH:
            raise ValueError(f"name must be at most {MAX_NAME_LENGTH} characters")
        return value


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_name": "Python Workshop",
                "certificate_date": "2026-10-08",
                "recipients": [
                    {"name": "Sona Mithya", "email": "sona@example.com"},
                    {"name": "Priya", "email": "priya@example.com"},
                ],
            }
        }
    )

    event_name: str
    certificate_date: date  # accepts "YYYY-MM-DD"; impossible dates such as 2026-02-30 are rejected
    recipients: list[RecipientIn]

    @field_validator("event_name")
    @classmethod
    def validate_event_name(cls, value: str) -> str:
        value = clean_text(value)
        if not value:
            raise ValueError("event_name must not be empty")
        if len(value) > MAX_EVENT_NAME_LENGTH:
            raise ValueError(f"event_name must be at most {MAX_EVENT_NAME_LENGTH} characters")
        return value

    @field_validator("recipients")
    @classmethod
    def validate_recipients(cls, value: list[RecipientIn]) -> list[RecipientIn]:
        if not value:
            raise ValueError("recipients must contain at least one recipient")
        if len(value) > MAX_RECIPIENTS_PER_JOB:
            raise ValueError(f"a single job can contain at most {MAX_RECIPIENTS_PER_JOB} recipients")
        return value


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str
    total_recipients: int


class JobStatusResponse(BaseModel):
    job_id: str
    event_name: str
    status: str
    total_recipients: int
    successful_count: int
    failed_count: int
    completed_count: int
    progress_percentage: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class CertificateItem(BaseModel):
    certificate_id: int
    recipient_name: str
    email: str
    status: str
    download_url: Optional[str] = None  # only set when status is SUCCESS
    error_message: Optional[str] = None  # only set when status is FAILED


class JobCertificatesResponse(BaseModel):
    job_id: str
    certificates: list[CertificateItem]
