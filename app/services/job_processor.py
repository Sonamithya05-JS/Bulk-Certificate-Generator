"""Creating jobs and processing them in the background.

Status flow
-----------
Job:         PROCESSING -> COMPLETED | COMPLETED_WITH_ERRORS | FAILED
Certificate: PENDING    -> SUCCESS   | FAILED
"""
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Certificate, CertificateStatus, GenerationJob, JobStatus, utc_now
from app.schemas.job import JobCreateRequest
from app.services import certificate_generator

logger = logging.getLogger(__name__)


def create_job(db: Session, payload: JobCreateRequest) -> GenerationJob:
    """Save the job and one PENDING certificate row per recipient (single transaction)."""
    job = GenerationJob(
        event_name=payload.event_name,
        certificate_date=payload.certificate_date,
        total_recipients=len(payload.recipients),
        # The job starts working right away in the background, so it is PROCESSING from the start.
        status=JobStatus.PROCESSING.value,
    )
    job.certificates = [
        Certificate(name=recipient.name, email=recipient.email) for recipient in payload.recipients
    ]
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _process_one_certificate(
    db: Session, job: GenerationJob, certificate: Certificate, certificates_dir: Path
) -> None:
    """Generate one PDF. Any failure is recorded on THIS certificate only."""
    try:
        pdf_path = certificate_generator.generate_certificate_pdf(
            recipient_name=certificate.name,
            event_name=job.event_name,
            certificate_date=job.certificate_date,
            job_directory=certificates_dir / job.id,
        )
        certificate.status = CertificateStatus.SUCCESS.value
        certificate.certificate_path = (Path(job.id) / pdf_path.name).as_posix()
        job.successful_count += 1
    except certificate_generator.CertificateGenerationError as exc:
        certificate.status = CertificateStatus.FAILED.value
        certificate.error_message = str(exc)
        job.failed_count += 1
    except Exception as exc:  # noqa: BLE001 - on purpose: one bad recipient must never stop the job
        logger.exception("Unexpected error for certificate %s", certificate.id)
        certificate.status = CertificateStatus.FAILED.value
        certificate.error_message = f"Unexpected error while generating certificate ({type(exc).__name__})"
        job.failed_count += 1

    # Commit after every certificate so the status endpoint shows live progress.
    db.commit()


def _final_status(job: GenerationJob) -> JobStatus:
    if job.failed_count == 0:
        return JobStatus.COMPLETED
    if job.successful_count == 0:
        return JobStatus.FAILED
    return JobStatus.COMPLETED_WITH_ERRORS


def _mark_job_failed(session_factory: sessionmaker, job_id: str) -> None:
    """Last resort when processing itself crashed (e.g. database error)."""
    with session_factory() as db:
        job = db.get(GenerationJob, job_id)
        if job is not None:
            job.status = JobStatus.FAILED.value
            job.completed_at = utc_now()
            db.commit()


def process_job(job_id: str, session_factory: sessionmaker, certificates_dir: Path) -> None:
    """Background task: generate every certificate of a job.

    It opens its OWN database session, because the request's session is closed
    as soon as the HTTP response has been sent.
    """
    try:
        with session_factory() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:
                logger.error("Job %s not found; nothing to process", job_id)
                return

            job.status = JobStatus.PROCESSING.value
            db.commit()

            pending = db.scalars(
                select(Certificate)
                .where(
                    Certificate.job_id == job_id,
                    Certificate.status == CertificateStatus.PENDING.value,
                )
                .order_by(Certificate.id)
            ).all()

            for certificate in pending:
                _process_one_certificate(db, job, certificate, certificates_dir)

            job.status = _final_status(job).value
            job.completed_at = utc_now()
            db.commit()
            logger.info(
                "Job %s finished: %s (%s ok, %s failed)",
                job_id, job.status, job.successful_count, job.failed_count,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Job %s crashed", job_id)
        _mark_job_failed(session_factory, job_id)
