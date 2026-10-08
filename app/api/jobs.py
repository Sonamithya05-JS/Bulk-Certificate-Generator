"""Endpoints for creating jobs, checking progress and listing a job's certificates."""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_certificates_dir
from app.database.database import get_db, get_session_factory
from app.database.models import CertificateStatus, GenerationJob
from app.schemas.job import (
    CertificateItem,
    JobCertificatesResponse,
    JobCreatedResponse,
    JobCreateRequest,
    JobStatusResponse,
)
from app.services.job_processor import create_job, process_job

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def get_job_or_404(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.post("/", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
def create_generation_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
    certificates_dir: Path = Depends(get_certificates_dir),
) -> JobCreatedResponse:
    """Accept a bulk request, save it, and generate the PDFs in the background.

    202 Accepted = "request received, work still in progress".
    """
    job = create_job(db, payload)
    background_tasks.add_task(process_job, job.id, session_factory, certificates_dir)
    return JobCreatedResponse(
        job_id=job.id, status=job.status, total_recipients=job.total_recipients
    )


@router.get("/{job_id}/", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = get_job_or_404(db, job_id)
    completed_count = job.successful_count + job.failed_count
    # Integer division rounds down, so 100% is only reached when everything is done.
    progress = completed_count * 100 // job.total_recipients if job.total_recipients else 100
    return JobStatusResponse(
        job_id=job.id,
        event_name=job.event_name,
        status=job.status,
        total_recipients=job.total_recipients,
        successful_count=job.successful_count,
        failed_count=job.failed_count,
        completed_count=completed_count,
        progress_percentage=progress,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/{job_id}/certificates/", response_model=JobCertificatesResponse)
def list_job_certificates(job_id: str, db: Session = Depends(get_db)) -> JobCertificatesResponse:
    job = get_job_or_404(db, job_id)
    items = [
        CertificateItem(
            certificate_id=certificate.id,
            recipient_name=certificate.name,
            email=certificate.email,
            status=certificate.status,
            download_url=(
                f"/api/certificates/{certificate.id}/"
                if certificate.status == CertificateStatus.SUCCESS.value
                else None
            ),
            error_message=certificate.error_message,
        )
        for certificate in job.certificates
    ]
    return JobCertificatesResponse(job_id=job.id, certificates=items)
