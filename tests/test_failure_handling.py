"""One failing certificate must never stop the rest of the job."""
import pytest

from app.services import certificate_generator
from app.services.certificate_generator import CertificateGenerationError
from tests.conftest import make_payload


def fail_for(monkeypatch, names, error=None):
    """Make the real generator fail only for the given recipient names."""
    real_generator = certificate_generator.generate_certificate_pdf

    def flaky_generator(**kwargs):
        if kwargs["recipient_name"] in names:
            raise error or CertificateGenerationError("Simulated generation failure")
        return real_generator(**kwargs)

    monkeypatch.setattr(certificate_generator, "generate_certificate_pdf", flaky_generator)


def get_certificates(client, job_id):
    return client.get(f"/api/jobs/{job_id}/certificates/").json()["certificates"]


def test_one_failure_does_not_stop_other_certificates(client, certificates_dir, monkeypatch):
    fail_for(monkeypatch, {"Person 2"})
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=5)).json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}/").json()
    assert status["status"] == "COMPLETED_WITH_ERRORS"
    assert status["successful_count"] == 4
    assert status["failed_count"] == 1
    assert status["completed_count"] == 5
    assert status["progress_percentage"] == 100
    assert len(list((certificates_dir / job_id).glob("*.pdf"))) == 4


def test_failed_certificate_has_status_and_error_message(client, monkeypatch):
    fail_for(monkeypatch, {"Person 2"})
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=3)).json()["job_id"]

    by_name = {item["recipient_name"]: item for item in get_certificates(client, job_id)}

    assert by_name["Person 2"]["status"] == "FAILED"
    assert by_name["Person 2"]["error_message"] == "Simulated generation failure"
    assert by_name["Person 2"]["download_url"] is None
    assert by_name["Person 1"]["status"] == "SUCCESS"
    assert by_name["Person 3"]["status"] == "SUCCESS"


def test_recipients_after_the_failure_are_still_processed(client, monkeypatch):
    fail_for(monkeypatch, {"Person 1"})  # the very FIRST one fails
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=3)).json()["job_id"]

    statuses = [item["status"] for item in get_certificates(client, job_id)]
    assert statuses == ["FAILED", "SUCCESS", "SUCCESS"]


def test_unexpected_exception_is_contained_and_not_leaked(client, monkeypatch):
    fail_for(monkeypatch, {"Person 2"}, error=RuntimeError("secret /internal/path blew up"))
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=3)).json()["job_id"]

    failed = [c for c in get_certificates(client, job_id) if c["status"] == "FAILED"][0]
    assert "RuntimeError" in failed["error_message"]
    assert "secret" not in failed["error_message"]
    assert client.get(f"/api/jobs/{job_id}/").json()["status"] == "COMPLETED_WITH_ERRORS"


def test_job_fails_when_every_certificate_fails(client, monkeypatch):
    fail_for(monkeypatch, {"Person 1", "Person 2"})
    job_id = client.post("/api/jobs/", json=make_payload(recipient_count=2)).json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}/").json()
    assert status["status"] == "FAILED"
    assert status["successful_count"] == 0
    assert status["failed_count"] == 2
    assert status["progress_percentage"] == 100


def test_real_failure_for_unsupported_name_characters(client, certificates_dir):
    """No mocking: a Tamil name genuinely cannot be drawn with the built-in font."""
    payload = make_payload(recipient_count=0)
    payload["recipients"] = [
        {"name": "Sona Mithya", "email": "sona@example.com"},
        {"name": "சோனா", "email": "tamil@example.com"},
        {"name": "Priya", "email": "priya@example.com"},
    ]
    job_id = client.post("/api/jobs/", json=payload).json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}/").json()
    assert status["status"] == "COMPLETED_WITH_ERRORS"
    assert (status["successful_count"], status["failed_count"]) == (2, 1)

    failed = [c for c in get_certificates(client, job_id) if c["status"] == "FAILED"][0]
    assert failed["recipient_name"] == "சோனா"
    assert "cannot display" in failed["error_message"]
    assert len(list((certificates_dir / job_id).glob("*.pdf"))) == 2


def test_job_marked_failed_if_processing_crashes(session_factory, certificates_dir, monkeypatch):
    """If the database itself breaks mid-job, the job ends as FAILED instead of hanging."""
    from app.database.models import GenerationJob
    from app.schemas.job import JobCreateRequest
    from app.services import job_processor

    with session_factory() as db:
        job = job_processor.create_job(db, JobCreateRequest(**make_payload(2)))
        job_id = job.id

    def broken(*args, **kwargs):
        raise RuntimeError("database exploded")

    monkeypatch.setattr(job_processor, "_process_one_certificate", broken)
    job_processor.process_job(job_id, session_factory, certificates_dir)

    with session_factory() as db:
        job = db.get(GenerationJob, job_id)
        assert job.status == "FAILED"
        assert job.completed_at is not None
